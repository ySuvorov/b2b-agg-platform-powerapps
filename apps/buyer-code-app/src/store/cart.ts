import { create } from 'zustand'

export interface CartItem {
  offerId: string
  canonicalProductId: string
  productName: string
  supplierId: string
  supplierName: string
  warehouse: string
  unitPrice: number
  qty: number
}

export interface SupplierGroup {
  supplierName: string
  items: CartItem[]
  subtotal: number
}

interface CartState {
  items: CartItem[]
  addItem: (item: Omit<CartItem, 'qty'> & { qty?: number }) => void
  removeItem: (offerId: string) => void
  updateQty: (offerId: string, qty: number) => void
  clearCart: () => void
  totalItems: () => number
  totalPrice: () => number
  // Per-supplier split — a multi-supplier cart becomes one order per supplier
  // at checkout (audit L-4). Keyed on supplierName because search offers don't
  // carry a supplierId. Mirrors the grouping in createOrder().
  groupsBySupplier: () => SupplierGroup[]
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  addItem: (item) => set((s) => {
    const existing = s.items.find(i => i.offerId === item.offerId)
    if (existing) {
      return { items: s.items.map(i => i.offerId === item.offerId ? { ...i, qty: i.qty + (item.qty ?? 1) } : i) }
    }
    return { items: [...s.items, { ...item, qty: item.qty ?? 1 }] }
  }),
  removeItem: (offerId) => set((s) => ({ items: s.items.filter(i => i.offerId !== offerId) })),
  updateQty: (offerId, qty) => set((s) => ({
    items: qty <= 0
      ? s.items.filter(i => i.offerId !== offerId)
      : s.items.map(i => i.offerId === offerId ? { ...i, qty } : i)
  })),
  clearCart: () => set({ items: [] }),
  totalItems: () => get().items.reduce((sum, i) => sum + i.qty, 0),
  totalPrice: () => get().items.reduce((sum, i) => sum + i.unitPrice * i.qty, 0),
  groupsBySupplier: () => {
    const byName = new Map<string, CartItem[]>()
    for (const item of get().items) {
      const key = item.supplierName || 'Unknown'
      const bucket = byName.get(key)
      if (bucket) bucket.push(item)
      else byName.set(key, [item])
    }
    return Array.from(byName.entries()).map(([supplierName, items]) => ({
      supplierName,
      items,
      subtotal: items.reduce((s, i) => s + i.unitPrice * i.qty, 0),
    }))
  },
}))
