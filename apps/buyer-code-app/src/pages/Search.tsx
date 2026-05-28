import { useState, useEffect, useMemo } from 'react'
import {
  makeStyles,
  tokens,
  mergeClasses,
  Input,
  Button,
  Badge,
  Spinner,
  Checkbox,
  RadioGroup,
  Radio,
  Title2,
  Body1Strong,
  Caption1,
} from '@fluentui/react-components'
import {
  SearchRegular,
  ChevronDownRegular,
  ChevronRightRegular,
  CartRegular,
} from '@fluentui/react-icons'
import { searchProducts } from '../services/dataverse'
import { useCartStore } from '../store/cart'
import type { ProductSearchRow, OfferRow } from '../types'
import { SEASON } from '../types'

const POPULAR_SIZES = [
  { label: '205/55 R16', width: 205, profile: 55, diameter: 16 },
  { label: '225/45 R17', width: 225, profile: 45, diameter: 17 },
  { label: '195/65 R15', width: 195, profile: 65, diameter: 15 },
  { label: '235/45 R18', width: 235, profile: 45, diameter: 18 },
  { label: '255/40 R19', width: 255, profile: 40, diameter: 19 },
  { label: '215/60 R16', width: 215, profile: 60, diameter: 16 },
]

const useStyles = makeStyles({
  root: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    height: '100%',
    overflowY: 'auto',
  },
  searchBar: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  searchInput: {
    flex: 1,
  },
  popularSizes: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    alignItems: 'center',
  },
  layout: {
    display: 'flex',
    gap: '24px',
    flex: 1,
  },
  filters: {
    width: '200px',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  results: {
    flex: 1,
  },
})

const useProductRowStyles = makeStyles({
  card: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    marginBottom: '8px',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    cursor: 'pointer',
    backgroundColor: tokens.colorNeutralBackground1,
    ':hover': { backgroundColor: tokens.colorNeutralBackground2 },
  },
  headerInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    flex: 1,
  },
  offersTable: {
    padding: '0 16px 12px',
  },
  offerRow: {
    display: 'grid',
    gridTemplateColumns: '2fr 2fr 1fr 1fr 1fr 1fr auto',
    gap: '8px',
    alignItems: 'center',
    padding: '6px 0',
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  offerHeader: {
    fontWeight: '600',
    fontSize: '12px',
    color: tokens.colorNeutralForeground2,
  },
})

interface ProductRowProps {
  product: ProductSearchRow
  expanded: boolean
  onToggle: () => void
  onAddToCart: (offer: OfferRow, productName: string) => void
}

function ProductRow({ product, expanded, onToggle, onAddToCart }: ProductRowProps) {
  const styles = useProductRowStyles()
  return (
    <div className={styles.card}>
      <div
        className={styles.header}
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
      >
        {expanded ? <ChevronDownRegular /> : <ChevronRightRegular />}
        <div className={styles.headerInfo}>
          <Body1Strong>{product.name}</Body1Strong>
          <Caption1>
            <Badge appearance="outline">{SEASON[product.season] ?? product.season}</Badge>
            {' '}{product.width}/{product.profile} R{product.diameter}
            {' · '}{product.supplierCount} supplier{product.supplierCount > 1 ? 's' : ''}
            {' · '}{product.totalStock} pcs
            {' · '}from ${product.minPrice.toFixed(2)}
          </Caption1>
        </div>
      </div>

      {expanded && (
        <div className={styles.offersTable}>
          <div className={mergeClasses(styles.offerRow, styles.offerHeader)}>
            <span>Supplier</span>
            <span>Warehouse</span>
            <span>Stock</span>
            <span>Price</span>
            <span>Year</span>
            <span>Lead</span>
            <span></span>
          </div>
          {product.offers.map((offer) => (
            <div key={offer.offerId} className={styles.offerRow}>
              <span>{offer.supplierName}</span>
              <span>{offer.warehouse}</span>
              <span>{offer.stock} pcs</span>
              <span>${offer.price.toFixed(2)}</span>
              <span>{offer.year ?? '—'}</span>
              <span>{offer.leadDays ? `${offer.leadDays}d` : '—'}</span>
              <Button
                size="small"
                icon={<CartRegular />}
                onClick={() => onAddToCart(offer, product.name)}
              >
                Add
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Search() {
  const styles = useStyles()
  const [query, setQuery] = useState('')
  const [products, setProducts] = useState<ProductSearchRow[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [filterSeason, setFilterSeason] = useState<number | null>(null)
  const [filterBrands, setFilterBrands] = useState<Set<string>>(new Set())
  const [filterDiameters, setFilterDiameters] = useState<Set<number>>(new Set())

  const addItem = useCartStore((s) => s.addItem)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    searchProducts('').then((rows) => {
      if (!cancelled) {
        setProducts(rows)
        setLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [])

  const availableBrands = useMemo(
    () => [...new Set(products.map((p) => p.brand))].sort(),
    [products],
  )

  const filteredProducts = useMemo(() => {
    const q = query.trim().toLowerCase()
    return products.filter((p) => {
      if (q && !p.name.toLowerCase().includes(q) && !p.brand.toLowerCase().includes(q) && !p.model.toLowerCase().includes(q)) return false
      if (filterSeason !== null && p.season !== filterSeason) return false
      if (filterBrands.size > 0 && !filterBrands.has(p.brand)) return false
      if (filterDiameters.size > 0 && !filterDiameters.has(p.diameter)) return false
      return true
    })
  }, [products, query, filterSeason, filterBrands, filterDiameters])

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const applySize = (size: { label: string; width: number; profile: number; diameter: number }) => {
    setQuery(`${size.width}/${size.profile}`)
    setFilterDiameters(new Set([size.diameter]))
  }

  const handleAddToCart = (offer: OfferRow, productName: string) => {
    addItem({
      offerId: offer.offerId,
      canonicalProductId: '',
      productName,
      supplierId: '',
      supplierName: offer.supplierName,
      unitPrice: offer.price,
      qty: 1,
    })
  }

  const toggleBrand = (brand: string, checked: boolean) => {
    setFilterBrands((prev) => {
      const next = new Set(prev)
      if (checked) next.add(brand)
      else next.delete(brand)
      return next
    })
  }

  const toggleDiameter = (d: number, checked: boolean) => {
    setFilterDiameters((prev) => {
      const next = new Set(prev)
      if (checked) next.add(d)
      else next.delete(d)
      return next
    })
  }

  const totalOffers = filteredProducts.reduce((sum, p) => sum + p.offers.length, 0)

  return (
    <div className={styles.root}>
      <Title2>Product Search</Title2>

      <div className={styles.searchBar}>
        <Input
          contentBefore={<SearchRegular />}
          placeholder="Search tires by brand, model or SKU..."
          value={query}
          onChange={(_, d) => setQuery(d.value)}
          className={styles.searchInput}
        />
        {query && (
          <Button onClick={() => setQuery('')}>Clear</Button>
        )}
      </div>

      <div className={styles.popularSizes}>
        <Caption1>Popular sizes:</Caption1>
        {POPULAR_SIZES.map((size) => (
          <Button
            key={size.label}
            size="small"
            appearance="outline"
            onClick={() => applySize(size)}
          >
            {size.label}
          </Button>
        ))}
      </div>

      <div className={styles.layout}>
        <aside className={styles.filters}>
          <Body1Strong>Season</Body1Strong>
          <RadioGroup
            value={filterSeason !== null ? filterSeason.toString() : 'all'}
            onChange={(_, d) => {
              setFilterSeason(d.value === 'all' ? null : parseInt(d.value, 10))
            }}
          >
            <Radio value="all" label="All seasons" />
            <Radio value="10000" label="Summer" />
            <Radio value="10002" label="Winter" />
            <Radio value="10003" label="All Season" />
          </RadioGroup>

          <Body1Strong>Brand</Body1Strong>
          {availableBrands.map((brand) => (
            <Checkbox
              key={brand}
              label={brand}
              checked={filterBrands.has(brand)}
              onChange={(_, d) => toggleBrand(brand, !!d.checked)}
            />
          ))}

          <Body1Strong>Diameter</Body1Strong>
          {[15, 16, 17, 18, 19, 20].map((d) => (
            <Checkbox
              key={d}
              label={`R${d}`}
              checked={filterDiameters.has(d)}
              onChange={(_, data) => toggleDiameter(d, !!data.checked)}
            />
          ))}
        </aside>

        <div className={styles.results}>
          <Caption1>
            {filteredProducts.length} product{filteredProducts.length !== 1 ? 's' : ''},{' '}
            {totalOffers} offer{totalOffers !== 1 ? 's' : ''}
          </Caption1>
          {loading ? (
            <Spinner label="Loading..." />
          ) : (
            filteredProducts.map((product) => (
              <ProductRow
                key={product.canonicalProductId}
                product={product}
                expanded={expanded.has(product.canonicalProductId)}
                onToggle={() => toggle(product.canonicalProductId)}
                onAddToCart={handleAddToCart}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
