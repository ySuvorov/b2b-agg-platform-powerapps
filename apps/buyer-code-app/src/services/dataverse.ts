import type { ProductSearchRow, OfferRow, Order, OrderLine } from '../types'
import { OrderStatus } from '../types'
import type { IOperationResult } from '@microsoft/power-apps/data'
import { B2b_supplieroffersService } from '../generated/services/B2b_supplieroffersService'
import { B2b_canonicalproductsService } from '../generated/services/B2b_canonicalproductsService'
import { B2b_suppliersService } from '../generated/services/B2b_suppliersService'
import { B2b_regionsService } from '../generated/services/B2b_regionsService'
import { B2b_ordersService } from '../generated/services/B2b_ordersService'
import { B2b_orderlinesService } from '../generated/services/B2b_orderlinesService'

// Explicit, opt-in mock escape hatch for local UI work without Dataverse.
// In every other case the generated SDK services run and their errors surface
// to the UI — no silent fallback that hides a broken integration (audit H-1).
const USE_MOCK = (import.meta.env.VITE_USE_MOCK as string | undefined) === 'true'

// ---------------------------------------------------------------------------
// SDK result helper
//
// H-2: data flows through the generated typed services over
// `@microsoft/power-apps/data` (the Power runtime brokers auth). The services
// expose select/filter/orderBy/top but no $expand — related rows are fetched
// per table and joined by GUID below (also: virtual `<lookup>name` fields are
// not OData-selectable, so we resolve display names from the joined records).
// ---------------------------------------------------------------------------

function unwrap<T>(result: IOperationResult<T>): T {
  if (!result.success) {
    throw result.error ?? new Error('Dataverse operation failed')
  }
  return result.data
}

// Generated create() payloads type autonumber/system columns (b2b_order_number,
// ownerid, statecode…) as required; we send only the writable fields and let
// the platform populate the rest, so the payload is cast to the param type.
type OrderCreate = Parameters<typeof B2b_ordersService.create>[0]
type OrderLineCreate = Parameters<typeof B2b_orderlinesService.create>[0]

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

export async function fetchStats(): Promise<{
  suppliers: number
  products: number
  offers: number
  regions: number
}> {
  if (USE_MOCK) return MOCK_STATS
  const [suppliers, products, offers, regions] = await Promise.all([
    B2b_suppliersService.getAll({ select: ['b2b_supplierid'], top: 5000 }),
    B2b_canonicalproductsService.getAll({ select: ['b2b_canonicalproductid'], top: 5000 }),
    B2b_supplieroffersService.getAll({ select: ['b2b_supplierofferid'], top: 5000 }),
    B2b_regionsService.getAll({ select: ['b2b_regionid'], top: 5000 }),
  ])
  return {
    suppliers: unwrap(suppliers).length,
    products: unwrap(products).length,
    offers: unwrap(offers).length,
    regions: unwrap(regions).length,
  }
}

// ---------------------------------------------------------------------------
// Suppliers
// ---------------------------------------------------------------------------

export async function fetchSuppliers(): Promise<{ b2b_supplierid: string; b2b_name: string }[]> {
  if (USE_MOCK) return MOCK_SUPPLIERS
  const res = await B2b_suppliersService.getAll({
    select: ['b2b_supplierid', 'b2b_name'],
    orderBy: ['b2b_name asc'],
    top: 5000,
  })
  return unwrap(res).map((s) => ({
    b2b_supplierid: s.b2b_supplierid,
    b2b_name: s.b2b_name ?? 'Unknown',
  }))
}

// ---------------------------------------------------------------------------
// Catalog load (shared by search + orders): offers + product/supplier lookups
// ---------------------------------------------------------------------------

interface OfferDetail {
  productName: string
  supplierName: string
  warehouse: string
}

async function loadCatalog() {
  const [offersR, productsR, suppliersR] = await Promise.all([
    B2b_supplieroffersService.getAll({
      select: [
        'b2b_supplierofferid',
        'b2b_raw_sku',
        'b2b_raw_name',
        'b2b_stock',
        'b2b_price',
        'b2b_warehouse_city',
        'b2b_lead_time_days',
        '_b2b_canonical_product_value',
        '_b2b_supplier_value',
      ],
      orderBy: ['b2b_price asc'],
      top: 5000,
    }),
    B2b_canonicalproductsService.getAll({
      select: [
        'b2b_canonicalproductid',
        'b2b_name',
        'b2b_brand',
        'b2b_model',
        'b2b_width',
        'b2b_profile',
        'b2b_diameter',
        'b2b_season',
      ],
      top: 5000,
    }),
    B2b_suppliersService.getAll({ select: ['b2b_supplierid', 'b2b_name'], top: 5000 }),
  ])

  const offers = unwrap(offersR)
  const productMap = new Map(unwrap(productsR).map((p) => [p.b2b_canonicalproductid, p]))
  const supplierMap = new Map(unwrap(suppliersR).map((s) => [s.b2b_supplierid, s.b2b_name ?? 'Unknown']))

  return { offers, productMap, supplierMap }
}

// ---------------------------------------------------------------------------
// Search — build ProductSearchRow[] from supplier offers joined to products
// ---------------------------------------------------------------------------

export async function searchProducts(query: string = ''): Promise<ProductSearchRow[]> {
  if (USE_MOCK) return filterMockProducts(query)

  const { offers, productMap, supplierMap } = await loadCatalog()
  const rows = new Map<string, ProductSearchRow>()

  for (const offer of offers) {
    const productId = offer._b2b_canonical_product_value
    if (!productId) continue
    const product = productMap.get(productId)
    if (!product) continue

    const offerRow: OfferRow = {
      offerId: offer.b2b_supplierofferid,
      rawSku: offer.b2b_raw_sku ?? '',
      supplierName: supplierMap.get(offer._b2b_supplier_value ?? '') ?? 'Unknown',
      warehouse: offer.b2b_warehouse_city ?? '—',
      stock: offer.b2b_stock ?? 0,
      price: offer.b2b_price ?? 0,
      leadDays: offer.b2b_lead_time_days,
    }

    const existing = rows.get(productId)
    if (existing) {
      existing.offers.push(offerRow)
      existing.totalStock += offerRow.stock
      if (offerRow.price < existing.minPrice) existing.minPrice = offerRow.price
      if (!existing.offers.slice(0, -1).some((o) => o.supplierName === offerRow.supplierName)) {
        existing.supplierCount++
      }
    } else {
      rows.set(productId, {
        canonicalProductId: productId,
        name: product.b2b_name ?? '',
        brand: product.b2b_brand ?? '',
        model: product.b2b_model ?? '',
        width: product.b2b_width ?? 0,
        profile: product.b2b_profile ?? 0,
        diameter: product.b2b_diameter ?? 0,
        season: product.b2b_season ?? 0,
        totalStock: offerRow.stock,
        minPrice: offerRow.price,
        supplierCount: 1,
        offers: [offerRow],
      })
    }
  }

  return Array.from(rows.values())
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export async function fetchOrders(): Promise<Order[]> {
  if (USE_MOCK) return MOCK_ORDERS

  const ordersR = await B2b_ordersService.getAll({
    select: ['b2b_orderid', 'b2b_order_number', 'b2b_total_amount', 'b2b_status', 'createdon'],
    orderBy: ['createdon desc'],
    top: 20,
  })
  const orders = unwrap(ordersR)
  if (orders.length === 0) return []

  // Lines for the visible orders + an offer→detail index for line display.
  const [linesR, catalog] = await Promise.all([
    B2b_orderlinesService.getAll({
      select: [
        'b2b_orderlineid',
        'b2b_line_ref',
        'b2b_qty',
        'b2b_unit_price',
        '_b2b_order_id_value',
        '_b2b_supplieroffer_id_value',
      ],
      orderBy: ['createdon desc'],
      top: 500,
    }),
    loadCatalog(),
  ])

  const offerDetail = new Map<string, OfferDetail>()
  for (const offer of catalog.offers) {
    const product = offer._b2b_canonical_product_value
      ? catalog.productMap.get(offer._b2b_canonical_product_value)
      : undefined
    offerDetail.set(offer.b2b_supplierofferid, {
      productName: product?.b2b_name ?? offer.b2b_raw_name ?? '—',
      supplierName: catalog.supplierMap.get(offer._b2b_supplier_value ?? '') ?? '—',
      warehouse: offer.b2b_warehouse_city ?? '—',
    })
  }

  const linesByOrder = new Map<string, OrderLine[]>()
  for (const line of unwrap(linesR)) {
    const orderId = line._b2b_order_id_value
    if (!orderId) continue
    const detail = line._b2b_supplieroffer_id_value
      ? offerDetail.get(line._b2b_supplieroffer_id_value)
      : undefined
    const mapped: OrderLine = {
      b2b_orderlineid: line.b2b_orderlineid,
      b2b_line_ref: line.b2b_line_ref,
      b2b_qty: line.b2b_qty ?? 0,
      b2b_unit_price: line.b2b_unit_price ?? 0,
      productName: detail?.productName,
      supplierName: detail?.supplierName,
      warehouse: detail?.warehouse,
    }
    const bucket = linesByOrder.get(orderId)
    if (bucket) bucket.push(mapped)
    else linesByOrder.set(orderId, [mapped])
  }

  return orders.map((o) => ({
    b2b_orderid: o.b2b_orderid,
    b2b_order_number: o.b2b_order_number,
    b2b_total_amount: o.b2b_total_amount ?? 0,
    b2b_status: o.b2b_status ?? OrderStatus.Draft,
    createdon: o.createdon ?? '',
    orderlines: linesByOrder.get(o.b2b_orderid) ?? [],
  }))
}

export interface OrderLineInput {
  offerId: string
  productName: string
  supplierName: string
  warehouse: string
  unitPrice: number
  qty: number
}

/**
 * Places one Dataverse order **per supplier** (audit L-4: a cart spanning
 * multiple suppliers must split — you cannot fulfil one PO across vendors).
 * Returns the created order id(s). `b2b_order_number` is autonumber → never
 * sent; `b2b_line_ref` is required & non-autonumber → generated per line.
 */
export async function createOrder(items: OrderLineInput[]): Promise<string[]> {
  const bySupplier = new Map<string, OrderLineInput[]>()
  for (const item of items) {
    const key = item.supplierName || 'Unknown'
    const bucket = bySupplier.get(key)
    if (bucket) bucket.push(item)
    else bySupplier.set(key, [item])
  }

  const orderIds: string[] = []
  for (const lines of bySupplier.values()) {
    const totalAmount = lines.reduce((s, i) => s + i.unitPrice * i.qty, 0)
    const orderRes = await B2b_ordersService.create({
      b2b_status: OrderStatus.Draft,
      b2b_total_amount: totalAmount,
    } as OrderCreate)
    const orderId = unwrap(orderRes).b2b_orderid

    await Promise.all(
      lines.map((item, idx) =>
        B2b_orderlinesService.create({
          b2b_line_ref: `L-${idx + 1}`,
          'b2b_order_id@odata.bind': `/b2b_orders(${orderId})`,
          'b2b_supplieroffer_id@odata.bind': `/b2b_supplieroffers(${item.offerId})`,
          b2b_qty: item.qty,
          b2b_unit_price: item.unitPrice,
        } as OrderLineCreate),
      ),
    )
    orderIds.push(orderId)
  }

  return orderIds
}

// ---------------------------------------------------------------------------
// Mock data — only used when VITE_USE_MOCK=true (explicit local dev opt-in)
// ---------------------------------------------------------------------------

const MOCK_STATS = { suppliers: 3, products: 36, offers: 201, regions: 7 }

const MOCK_SUPPLIERS = [
  { b2b_supplierid: 'sup-1', b2b_name: 'RosshinaOpt' },
  { b2b_supplierid: 'sup-2', b2b_name: 'TyreCenter SPB' },
  { b2b_supplierid: 'sup-3', b2b_name: 'Koleso.ru' },
]

export const MOCK_PRODUCTS: ProductSearchRow[] = [
  {
    canonicalProductId: 'cp-1',
    name: 'Michelin Pilot Sport 4 225/45R17',
    brand: 'Michelin',
    model: 'Pilot Sport 4',
    width: 225, profile: 45, diameter: 17, season: 10000,
    totalStock: 60, minPrice: 125.0, supplierCount: 2,
    offers: [
      { offerId: 'off-1', rawSku: 'MPS4-22545R17', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 48, price: 127.50, leadDays: 2 },
      { offerId: 'off-2', rawSku: 'MPS4-22545R17-B', supplierName: 'TyreCenter SPB', warehouse: 'Saint-Petersburg', stock: 12, price: 125.0, leadDays: 3 },
    ],
  },
  {
    canonicalProductId: 'cp-2',
    name: 'Michelin Pilot Sport 4 255/40R19',
    brand: 'Michelin',
    model: 'Pilot Sport 4',
    width: 255, profile: 40, diameter: 19, season: 10000,
    totalStock: 25, minPrice: 180.0, supplierCount: 2,
    offers: [
      { offerId: 'off-3', rawSku: 'MPS4-25540R19', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 18, price: 182.50, leadDays: 3 },
      { offerId: 'off-4', rawSku: 'MPS4-25540R19-MOW2', supplierName: 'TyreCenter SPB', warehouse: 'Moscow', stock: 7, price: 180.0, leadDays: 3 },
    ],
  },
  {
    canonicalProductId: 'cp-3',
    name: 'Michelin CrossClimate 2 205/55R16',
    brand: 'Michelin',
    model: 'CrossClimate 2',
    width: 205, profile: 55, diameter: 16, season: 10003,
    totalStock: 187, minPrice: 110.0, supplierCount: 3,
    offers: [
      { offerId: 'off-5', rawSku: 'MCC2-20555R16', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 65, price: 112.0, leadDays: 2 },
      { offerId: 'off-6', rawSku: 'MCC2-20555R16-KZN', supplierName: 'Koleso.ru', warehouse: 'Kazan', stock: 19, price: 110.0, leadDays: 3 },
      { offerId: 'off-7', rawSku: 'MCC2-20555R16-NSK', supplierName: 'TyreCenter SPB', warehouse: 'Novosibirsk', stock: 103, price: 111.0, leadDays: 4 },
    ],
  },
  {
    canonicalProductId: 'cp-4',
    name: 'Michelin Alpin 6 195/65R15',
    brand: 'Michelin',
    model: 'Alpin 6',
    width: 195, profile: 65, diameter: 15, season: 10002,
    totalStock: 110, minPrice: 88.5, supplierCount: 2,
    offers: [
      { offerId: 'off-8', rawSku: 'MA6-19565R15', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 74, price: 89.9, leadDays: 1 },
      { offerId: 'off-9', rawSku: 'MA6-19565R15-NSK', supplierName: 'Koleso.ru', warehouse: 'Novosibirsk', stock: 36, price: 88.5, leadDays: 4 },
    ],
  },
  {
    canonicalProductId: 'cp-5',
    name: 'Continental PremiumContact 6 225/45R17',
    brand: 'Continental',
    model: 'PremiumContact 6',
    width: 225, profile: 45, diameter: 17, season: 10000,
    totalStock: 63, minPrice: 119.0, supplierCount: 2,
    offers: [
      { offerId: 'off-10', rawSku: 'CPC6-22545R17', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 44, price: 121.0, leadDays: 2 },
      { offerId: 'off-11', rawSku: 'CPC6-22545R17-NSK', supplierName: 'Koleso.ru', warehouse: 'Novosibirsk', stock: 19, price: 119.0, leadDays: 4 },
    ],
  },
  {
    canonicalProductId: 'cp-6',
    name: 'Continental WinterContact TS860 195/65R15',
    brand: 'Continental',
    model: 'WinterContact TS860',
    width: 195, profile: 65, diameter: 15, season: 10002,
    totalStock: 119, minPrice: 83.5, supplierCount: 2,
    offers: [
      { offerId: 'off-12', rawSku: 'CWC-19565R15', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 77, price: 85.0, leadDays: 1 },
      { offerId: 'off-13', rawSku: 'CWC-19565R15-NSK', supplierName: 'TyreCenter SPB', warehouse: 'Novosibirsk', stock: 42, price: 83.5, leadDays: 4 },
    ],
  },
  {
    canonicalProductId: 'cp-7',
    name: 'Continental AllSeasonContact 2 205/55R16',
    brand: 'Continental',
    model: 'AllSeasonContact 2',
    width: 205, profile: 55, diameter: 16, season: 10003,
    totalStock: 104, minPrice: 93.0, supplierCount: 2,
    offers: [
      { offerId: 'off-14', rawSku: 'CAS2-20555R16', supplierName: 'Koleso.ru', warehouse: 'Yekaterinburg', stock: 63, price: 95.0, leadDays: 3 },
      { offerId: 'off-15', rawSku: 'CAS2-20555R16-MOW2', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 41, price: 93.0, leadDays: 2 },
    ],
  },
  {
    canonicalProductId: 'cp-8',
    name: 'Bridgestone Turanza T005 205/55R16',
    brand: 'Bridgestone',
    model: 'Turanza T005',
    width: 205, profile: 55, diameter: 16, season: 10000,
    totalStock: 88, minPrice: 98.0, supplierCount: 3,
    offers: [
      { offerId: 'off-16', rawSku: 'BS-TT005-20555R16-MOW', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 40, price: 101.0, leadDays: 2 },
      { offerId: 'off-17', rawSku: 'BS-TT005-20555R16-EKB', supplierName: 'TyreCenter SPB', warehouse: 'Yekaterinburg', stock: 28, price: 98.0, leadDays: 3 },
      { offerId: 'off-18', rawSku: 'BS-TT005-20555R16-KZN', supplierName: 'Koleso.ru', warehouse: 'Kazan', stock: 20, price: 99.5, leadDays: 3 },
    ],
  },
]

const MOCK_ORDERS: Order[] = [
  {
    b2b_orderid: 'ord-1',
    b2b_order_number: 'ORD-2026-0042',
    b2b_total_amount: 1016.0,
    b2b_status: OrderStatus.Confirmed,
    createdon: '2026-05-25T10:30:00Z',
    orderlines: [
      { b2b_orderlineid: 'ol-1', b2b_qty: 4, b2b_unit_price: 127.50, productName: 'Michelin Pilot Sport 4 225/45R17', supplierName: 'RosshinaOpt', warehouse: 'Moscow' },
      { b2b_orderlineid: 'ol-2', b2b_qty: 4, b2b_unit_price: 127.50, productName: 'Michelin Pilot Sport 4 225/45R17', supplierName: 'TyreCenter SPB', warehouse: 'Saint-Petersburg' },
    ],
  },
  {
    b2b_orderid: 'ord-2',
    b2b_order_number: 'ORD-2026-0041',
    b2b_total_amount: 380.0,
    b2b_status: OrderStatus.Shipped,
    createdon: '2026-05-20T08:15:00Z',
    orderlines: [
      { b2b_orderlineid: 'ol-3', b2b_qty: 4, b2b_unit_price: 95.0, productName: 'Continental AllSeasonContact 2 205/55R16', supplierName: 'Koleso.ru', warehouse: 'Yekaterinburg' },
    ],
  },
  {
    b2b_orderid: 'ord-3',
    b2b_order_number: 'ORD-2026-0038',
    b2b_total_amount: 718.0,
    b2b_status: OrderStatus.Draft,
    createdon: '2026-05-28T06:00:00Z',
    orderlines: [
      { b2b_orderlineid: 'ol-4', b2b_qty: 4, b2b_unit_price: 85.0, productName: 'Continental WinterContact TS860 195/65R15', supplierName: 'RosshinaOpt', warehouse: 'Moscow' },
      { b2b_orderlineid: 'ol-5', b2b_qty: 2, b2b_unit_price: 89.9, productName: 'Michelin Alpin 6 195/65R15', supplierName: 'RosshinaOpt', warehouse: 'Moscow' },
    ],
  },
]

function filterMockProducts(query: string): ProductSearchRow[] {
  if (!query) return MOCK_PRODUCTS
  const q = query.toLowerCase()
  return MOCK_PRODUCTS.filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      p.brand.toLowerCase().includes(q) ||
      p.model.toLowerCase().includes(q),
  )
}
