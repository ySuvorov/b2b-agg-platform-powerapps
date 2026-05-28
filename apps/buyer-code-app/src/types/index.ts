export interface CanonicalProduct {
  b2b_canonicalproductid: string
  b2b_name: string
  b2b_brand: string
  b2b_model: string
  b2b_width: number
  b2b_profile: number
  b2b_diameter: number
  b2b_season: number
  b2b_load_index?: number
  b2b_speed_index?: string
}

export interface SupplierOffer {
  b2b_supplierofferid: string
  b2b_raw_sku: string
  b2b_raw_name: string
  b2b_stock: number
  b2b_price: number
  b2b_warehouse: string
  b2b_year?: number
  b2b_country?: string
  b2b_lead_days?: number
  _b2b_canonical_product_value?: string
  _b2b_supplier_id_value?: string
  b2b_canonical_product?: CanonicalProduct
  b2b_supplier_id?: Supplier
}

export interface Supplier {
  b2b_supplierid: string
  b2b_name: string
}

export interface Order {
  b2b_orderid: string
  b2b_name: string
  b2b_total_amount: number
  b2b_status: number
  createdon: string
  orderlines?: OrderLine[]
}

export interface OrderLine {
  b2b_orderlineid: string
  b2b_qty: number
  b2b_unit_price: number
  productName?: string
  supplierName?: string
  warehouse?: string
}

// Picklist mappings (option prefix 10000)
export const SEASON: Record<number, string> = {
  10000: 'Summer',
  10001: 'WinterStudded',
  10002: 'WinterFriction',
  10003: 'AllSeason',
}

export const ORDER_STATUS: Record<number, string> = {
  10000: 'Draft',
  10001: 'Confirmed',
  10002: 'Shipped',
}

export const ORDER_STATUS_COLOR: Record<number, 'warning' | 'success' | 'informative'> = {
  10000: 'warning',
  10001: 'informative',
  10002: 'success',
}

// Aggregated view for Search page Level 1 rows
export interface ProductSearchRow {
  canonicalProductId: string
  name: string
  brand: string
  model: string
  width: number
  profile: number
  diameter: number
  season: number
  totalStock: number
  minPrice: number
  supplierCount: number
  offers: OfferRow[]
}

export interface OfferRow {
  offerId: string
  rawSku: string
  supplierName: string
  warehouse: string
  stock: number
  price: number
  year?: number
  country?: string
  leadDays?: number
}
