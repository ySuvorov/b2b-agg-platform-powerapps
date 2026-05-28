import type {
  SupplierOffer,
  Supplier,
  Order,
  ProductSearchRow,
  OfferRow,
} from '../types'

const BASE_URL =
  (import.meta.env.VITE_DATAVERSE_URL as string | undefined) ||
  'https://YOUR-DATAVERSE-ORG.crm.dynamics.com'

const DEV_TOKEN = import.meta.env.VITE_DEV_TOKEN as string | undefined

// ---------------------------------------------------------------------------
// OData helper
// ---------------------------------------------------------------------------

async function dvGet<T>(path: string): Promise<T[]> {
  const headers: Record<string, string> = {
    'OData-MaxVersion': '4.0',
    'OData-Version': '4.0',
    Accept: 'application/json',
    'Content-Type': 'application/json',
  }
  if (DEV_TOKEN) headers['Authorization'] = `Bearer ${DEV_TOKEN}`

  const res = await fetch(`${BASE_URL}/api/data/v9.2/${path}`, {
    headers,
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Dataverse ${res.status}: ${res.statusText}`)
  const json = await res.json()
  return (json.value ?? []) as T[]
}

async function dvPost(path: string, body: unknown): Promise<string> {
  const headers: Record<string, string> = {
    'OData-MaxVersion': '4.0',
    'OData-Version': '4.0',
    Accept: 'application/json',
    'Content-Type': 'application/json',
  }
  if (DEV_TOKEN) headers['Authorization'] = `Bearer ${DEV_TOKEN}`

  const res = await fetch(`${BASE_URL}/api/data/v9.2/${path}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Dataverse POST ${res.status}: ${text}`)
  }
  // Created record ID is in OData-EntityId header
  const entityId = res.headers.get('OData-EntityId') ?? ''
  const match = entityId.match(/\(([^)]+)\)$/)
  return match ? match[1] : ''
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

export async function fetchStats(): Promise<{
  suppliers: number
  products: number
  offers: number
  regions: number
}> {
  try {
    const [suppliers, products, offers, regions] = await Promise.all([
      dvGet<object>('b2b_suppliers?$select=b2b_supplierid&$top=1000'),
      dvGet<object>('b2b_canonicalproducts?$select=b2b_canonicalproductid&$top=1000'),
      dvGet<object>('b2b_supplieroffers?$select=b2b_supplierofferid&$top=1000'),
      dvGet<object>('b2b_regions?$select=b2b_regionid&$top=100'),
    ])
    return {
      suppliers: suppliers.length,
      products: products.length,
      offers: offers.length,
      regions: regions.length,
    }
  } catch {
    return MOCK_STATS
  }
}

// ---------------------------------------------------------------------------
// Suppliers
// ---------------------------------------------------------------------------

export async function fetchSuppliers(): Promise<Supplier[]> {
  try {
    return await dvGet<Supplier>(
      'b2b_suppliers?$select=b2b_supplierid,b2b_name&$orderby=b2b_name',
    )
  } catch {
    return MOCK_SUPPLIERS
  }
}

// ---------------------------------------------------------------------------
// Search — build ProductSearchRow[] from supplier offers
// ---------------------------------------------------------------------------

export async function searchProducts(query: string = ''): Promise<ProductSearchRow[]> {
  try {
    const filter = query
      ? `&$filter=contains(b2b_raw_name,'${encodeURIComponent(query)}')`
      : ''

    const offers = await dvGet<SupplierOffer>(
      `b2b_supplieroffers` +
        `?$select=b2b_supplierofferid,b2b_raw_sku,b2b_raw_name,b2b_stock,b2b_price,b2b_warehouse,b2b_year,b2b_country` +
        `&$expand=b2b_canonical_product($select=b2b_canonicalproductid,b2b_name,b2b_brand,b2b_model,b2b_width,b2b_profile,b2b_diameter,b2b_season),b2b_supplier_id($select=b2b_supplierid,b2b_name)` +
        `&$orderby=b2b_price` +
        filter,
    )

    return groupOffersByProduct(offers)
  } catch {
    return filterMockProducts(query)
  }
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export async function fetchOrders(): Promise<Order[]> {
  try {
    return await dvGet<Order>(
      'b2b_orders?$select=b2b_orderid,b2b_name,b2b_total_amount,b2b_status,createdon&$orderby=createdon desc&$top=20',
    )
  } catch {
    return MOCK_ORDERS
  }
}

export async function createOrder(
  items: Array<{ offerId: string; productName: string; supplierName: string; unitPrice: number; qty: number }>,
): Promise<string> {
  const totalAmount = items.reduce((s, i) => s + i.unitPrice * i.qty, 0)
  const orderId = await dvPost('b2b_orders', {
    b2b_total_amount: totalAmount,
    b2b_status: 10000, // Draft
  })

  await Promise.all(
    items.map((item) =>
      dvPost('b2b_orderlines', {
        'b2b_order_id@odata.bind': `/b2b_orders(${orderId})`,
        'b2b_supplieroffer_id@odata.bind': `/b2b_supplieroffers(${item.offerId})`,
        b2b_qty: item.qty,
        b2b_unit_price: item.unitPrice,
      }),
    ),
  )

  return orderId
}

// ---------------------------------------------------------------------------
// Group helper
// ---------------------------------------------------------------------------

function groupOffersByProduct(offers: SupplierOffer[]): ProductSearchRow[] {
  const map = new Map<string, ProductSearchRow>()

  for (const offer of offers) {
    const cp = offer.b2b_canonical_product
    if (!cp) continue

    const id = cp.b2b_canonicalproductid
    const offerRow: OfferRow = {
      offerId: offer.b2b_supplierofferid,
      rawSku: offer.b2b_raw_sku,
      supplierName: offer.b2b_supplier_id?.b2b_name ?? 'Unknown',
      warehouse: offer.b2b_warehouse,
      stock: offer.b2b_stock,
      price: offer.b2b_price,
      year: offer.b2b_year,
      country: offer.b2b_country,
      leadDays: offer.b2b_lead_days,
    }

    if (map.has(id)) {
      const row = map.get(id)!
      row.offers.push(offerRow)
      row.totalStock += offer.b2b_stock
      if (offer.b2b_price < row.minPrice) row.minPrice = offer.b2b_price
      if (!row.offers.some((o) => o.supplierName === offerRow.supplierName)) {
        row.supplierCount++
      }
    } else {
      map.set(id, {
        canonicalProductId: id,
        name: cp.b2b_name,
        brand: cp.b2b_brand,
        model: cp.b2b_model,
        width: cp.b2b_width,
        profile: cp.b2b_profile,
        diameter: cp.b2b_diameter,
        season: cp.b2b_season,
        totalStock: offer.b2b_stock,
        minPrice: offer.b2b_price,
        supplierCount: 1,
        offers: [offerRow],
      })
    }
  }

  return Array.from(map.values())
}

// ---------------------------------------------------------------------------
// Mock data (used when Dataverse not reachable in dev)
// ---------------------------------------------------------------------------

const MOCK_STATS = { suppliers: 3, products: 30, offers: 193, regions: 7 }

const MOCK_SUPPLIERS: Supplier[] = [
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
      { offerId: 'off-1', rawSku: 'MPS4-22545R17', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 48, price: 127.50, year: 2023, country: 'France', leadDays: 2 },
      { offerId: 'off-2', rawSku: 'MPS4-22545R17-B', supplierName: 'TyreCenter SPB', warehouse: 'Saint-Petersburg', stock: 12, price: 125.0, year: 2023, country: 'France', leadDays: 3 },
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
      { offerId: 'off-3', rawSku: 'MPS4-25540R19', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 18, price: 182.50, year: 2023, country: 'France', leadDays: 3 },
      { offerId: 'off-4', rawSku: 'MPS4-25540R19-MOW2', supplierName: 'TyreCenter SPB', warehouse: 'Moscow', stock: 7, price: 180.0, year: 2023, country: 'France', leadDays: 3 },
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
      { offerId: 'off-5', rawSku: 'MCC2-20555R16', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 65, price: 112.0, year: 2023, country: 'France', leadDays: 2 },
      { offerId: 'off-6', rawSku: 'MCC2-20555R16-KZN', supplierName: 'Koleso.ru', warehouse: 'Kazan', stock: 19, price: 110.0, year: 2023, country: 'France', leadDays: 3 },
      { offerId: 'off-7', rawSku: 'MCC2-20555R16-NSK', supplierName: 'TyreCenter SPB', warehouse: 'Novosibirsk', stock: 103, price: 111.0, year: 2023, country: 'France', leadDays: 4 },
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
      { offerId: 'off-8', rawSku: 'MA6-19565R15', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 74, price: 89.9, year: 2024, country: 'France', leadDays: 1 },
      { offerId: 'off-9', rawSku: 'MA6-19565R15-NSK', supplierName: 'Koleso.ru', warehouse: 'Novosibirsk', stock: 36, price: 88.5, year: 2024, country: 'France', leadDays: 4 },
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
      { offerId: 'off-10', rawSku: 'CPC6-22545R17', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 44, price: 121.0, year: 2023, country: 'Germany', leadDays: 2 },
      { offerId: 'off-11', rawSku: 'CPC6-22545R17-NSK', supplierName: 'Koleso.ru', warehouse: 'Novosibirsk', stock: 19, price: 119.0, year: 2023, country: 'Germany', leadDays: 4 },
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
      { offerId: 'off-12', rawSku: 'CWC-19565R15', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 77, price: 85.0, year: 2023, country: 'Germany', leadDays: 1 },
      { offerId: 'off-13', rawSku: 'CWC-19565R15-NSK', supplierName: 'TyreCenter SPB', warehouse: 'Novosibirsk', stock: 42, price: 83.5, year: 2023, country: 'Germany', leadDays: 4 },
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
      { offerId: 'off-14', rawSku: 'CAS2-20555R16', supplierName: 'Koleso.ru', warehouse: 'Yekaterinburg', stock: 63, price: 95.0, year: 2024, country: 'Germany', leadDays: 3 },
      { offerId: 'off-15', rawSku: 'CAS2-20555R16-MOW2', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 41, price: 93.0, year: 2024, country: 'Germany', leadDays: 2 },
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
      { offerId: 'off-16', rawSku: 'BS-TT005-20555R16-MOW', supplierName: 'RosshinaOpt', warehouse: 'Moscow', stock: 40, price: 101.0, year: 2023, country: 'Poland', leadDays: 2 },
      { offerId: 'off-17', rawSku: 'BS-TT005-20555R16-EKB', supplierName: 'TyreCenter SPB', warehouse: 'Yekaterinburg', stock: 28, price: 98.0, year: 2023, country: 'Poland', leadDays: 3 },
      { offerId: 'off-18', rawSku: 'BS-TT005-20555R16-KZN', supplierName: 'Koleso.ru', warehouse: 'Kazan', stock: 20, price: 99.5, year: 2023, country: 'Poland', leadDays: 3 },
    ],
  },
]

const MOCK_ORDERS: Order[] = [
  {
    b2b_orderid: 'ord-1',
    b2b_name: 'ORD-2026-0042',
    b2b_total_amount: 1016.0,
    b2b_status: 10001,
    createdon: '2026-05-25T10:30:00Z',
    orderlines: [
      { b2b_orderlineid: 'ol-1', b2b_qty: 4, b2b_unit_price: 127.50, productName: 'Michelin Pilot Sport 4 225/45R17', supplierName: 'RosshinaOpt', warehouse: 'Moscow' },
      { b2b_orderlineid: 'ol-2', b2b_qty: 4, b2b_unit_price: 127.50, productName: 'Michelin Pilot Sport 4 225/45R17', supplierName: 'TyreCenter SPB', warehouse: 'Saint-Petersburg' },
    ],
  },
  {
    b2b_orderid: 'ord-2',
    b2b_name: 'ORD-2026-0041',
    b2b_total_amount: 380.0,
    b2b_status: 10002,
    createdon: '2026-05-20T08:15:00Z',
    orderlines: [
      { b2b_orderlineid: 'ol-3', b2b_qty: 4, b2b_unit_price: 95.0, productName: 'Continental AllSeasonContact 2 205/55R16', supplierName: 'Koleso.ru', warehouse: 'Yekaterinburg' },
    ],
  },
  {
    b2b_orderid: 'ord-3',
    b2b_name: 'ORD-2026-0038',
    b2b_total_amount: 718.0,
    b2b_status: 10000,
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
