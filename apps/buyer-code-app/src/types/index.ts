// ---------------------------------------------------------------------------
// Option-set enums (named — no magic ints). Values mirror the live Dev
// environment exactly; see docs/schema-canonical.md. Do NOT renumber.
// ---------------------------------------------------------------------------

// `as const` objects (not TS `enum`) — the build runs with
// `erasableSyntaxOnly`, which forbids enums. Same call-site ergonomics
// (`Season.Summer`) but fully type-erasable.

/** b2b_canonicalproduct.b2b_season */
export const Season = {
  Summer: 10000,
  WinterStudded: 10001,
  WinterFriction: 10002,
  AllSeason: 10003,
} as const
export type Season = (typeof Season)[keyof typeof Season]

/** b2b_order.b2b_status — note the 100000000 series (NOT the 10000 series) */
export const OrderStatus = {
  Draft: 100000000,
  Confirmed: 100000001,
  Shipped: 100000002,
} as const
export type OrderStatus = (typeof OrderStatus)[keyof typeof OrderStatus]

/** b2b_supplieroffer.b2b_match_method */
export const MatchMethod = {
  Cache: 10000,
  ExactKey: 10001,
  Fuzzy: 10002,
  AI: 10003,
  Manual: 10004,
} as const
export type MatchMethod = (typeof MatchMethod)[keyof typeof MatchMethod]

/** b2b_canonicalproduct.b2b_homologation */
export const Homologation = {
  None: 10000,
  Star_BMW: 10001,
  MO_Mercedes: 10002,
  MOE_Mercedes: 10003,
  N0_Porsche: 10004,
  N1_Porsche: 10005,
  AO_Audi: 10006,
  LR_LandRover: 10007,
  VOL_Volvo: 10008,
  MGT_Maserati: 10009,
} as const
export type Homologation = (typeof Homologation)[keyof typeof Homologation]

export const SEASON: Record<number, string> = {
  [Season.Summer]: 'Summer',
  [Season.WinterStudded]: 'WinterStudded',
  [Season.WinterFriction]: 'WinterFriction',
  [Season.AllSeason]: 'AllSeason',
}

export const ORDER_STATUS: Record<number, string> = {
  [OrderStatus.Draft]: 'Draft',
  [OrderStatus.Confirmed]: 'Confirmed',
  [OrderStatus.Shipped]: 'Shipped',
}

export const ORDER_STATUS_COLOR: Record<number, 'warning' | 'success' | 'informative'> = {
  [OrderStatus.Draft]: 'warning',
  [OrderStatus.Confirmed]: 'informative',
  [OrderStatus.Shipped]: 'success',
}

// ---------------------------------------------------------------------------
// View models — entity shapes come from src/generated/models (typed SDK).
// These are the shapes the UI renders (Orders page + mock data).
// ---------------------------------------------------------------------------

export interface Order {
  b2b_orderid: string
  b2b_order_number: string
  b2b_total_amount: number
  b2b_status: number
  createdon: string
  orderlines?: OrderLine[]
}

export interface OrderLine {
  b2b_orderlineid: string
  b2b_line_ref?: string
  b2b_qty: number
  b2b_unit_price: number
  productName?: string
  supplierName?: string
  warehouse?: string
}

// ---------------------------------------------------------------------------
// View models (Search page aggregation)
// ---------------------------------------------------------------------------

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
  leadDays?: number
}
