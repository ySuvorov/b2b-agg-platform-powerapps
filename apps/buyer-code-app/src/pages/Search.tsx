import { useState, useEffect, useMemo, type ReactElement } from 'react'
import {
  makeStyles,
  tokens,
  mergeClasses,
  Input,
  Button,
  Badge,
  Spinner,
  Dropdown,
  Option,
  Title2,
  Body1Strong,
  Caption1,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
} from '@fluentui/react-components'
import {
  SearchRegular,
  ChevronDownRegular,
  ChevronRightRegular,
  CartRegular,
  WeatherSunnyRegular,
  WeatherSnowflakeRegular,
  CalendarLtrRegular,
} from '@fluentui/react-icons'
import { searchProducts } from '../services/dataverse'
import { useCartStore } from '../store/cart'
import type { ProductSearchRow, OfferRow } from '../types'
import { SEASON, Season } from '../types'

type SeasonGroup = 'summer' | 'winter' | 'allseason'

const SEASON_BUTTONS: { key: SeasonGroup; label: string; icon: ReactElement }[] = [
  { key: 'summer', label: 'Summer', icon: <WeatherSunnyRegular /> },
  { key: 'winter', label: 'Winter', icon: <WeatherSnowflakeRegular /> },
  { key: 'allseason', label: 'All-Season', icon: <CalendarLtrRegular /> },
]

function matchesSeason(group: SeasonGroup, season: number): boolean {
  switch (group) {
    case 'summer':
      return season === Season.Summer
    case 'winter':
      return season === Season.WinterStudded || season === Season.WinterFriction
    case 'allseason':
      return season === Season.AllSeason
  }
}

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
    width: '100%',
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
  // Horizontal filter bar across the top
  filterBar: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '16px',
    alignItems: 'flex-end',
    padding: '16px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    minWidth: '120px',
  },
  seasonField: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  seasonGroup: {
    display: 'flex',
    gap: '0',
  },
  seasonBtn: {
    borderRadius: '0',
  },
  seasonBtnFirst: {
    borderTopLeftRadius: tokens.borderRadiusMedium,
    borderBottomLeftRadius: tokens.borderRadiusMedium,
  },
  seasonBtnLast: {
    borderTopRightRadius: tokens.borderRadiusMedium,
    borderBottomRightRadius: tokens.borderRadiusMedium,
  },
  dropdown: {
    minWidth: '120px',
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
    gridTemplateColumns: '2fr 2fr 1fr 1fr 1fr auto',
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
            <span>Lead</span>
            <span></span>
          </div>
          {product.offers.map((offer) => (
            <div key={offer.offerId} className={styles.offerRow}>
              <span>{offer.supplierName}</span>
              <span>{offer.warehouse}</span>
              <span>{offer.stock} pcs</span>
              <span>${offer.price.toFixed(2)}</span>
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

// "All …" sentinel for single-select dropdowns.
const ALL = '__all'

export default function Search() {
  const styles = useStyles()
  const [query, setQuery] = useState('')
  const [products, setProducts] = useState<ProductSearchRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const [season, setSeason] = useState<SeasonGroup | null>(null)
  const [brand, setBrand] = useState<string | null>(null)
  const [width, setWidth] = useState<number | null>(null)
  const [profile, setProfile] = useState<number | null>(null)
  const [diameter, setDiameter] = useState<number | null>(null)
  const [city, setCity] = useState<string | null>(null)
  const [supplier, setSupplier] = useState<string | null>(null)

  const addItem = useCartStore((s) => s.addItem)

  useEffect(() => {
    let cancelled = false
    searchProducts('')
      .then((rows) => {
        if (cancelled) return
        setProducts(rows)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Failed to load products')
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const availableBrands = useMemo(
    () => [...new Set(products.map((p) => p.brand))].sort(),
    [products],
  )
  const availableWidths = useMemo(
    () => [...new Set(products.map((p) => p.width))].sort((a, b) => a - b),
    [products],
  )
  const availableProfiles = useMemo(
    () => [...new Set(products.map((p) => p.profile))].sort((a, b) => a - b),
    [products],
  )
  const availableDiameters = useMemo(
    () => [...new Set(products.map((p) => p.diameter))].sort((a, b) => a - b),
    [products],
  )
  const availableCities = useMemo(
    () => [...new Set(products.flatMap((p) => p.offers.map((o) => o.warehouse)))].sort(),
    [products],
  )
  const availableSuppliers = useMemo(
    () => [...new Set(products.flatMap((p) => p.offers.map((o) => o.supplierName)))].sort(),
    [products],
  )

  const filteredProducts = useMemo(() => {
    const q = query.trim().toLowerCase()
    return products.filter((p) => {
      if (q && !p.name.toLowerCase().includes(q) && !p.brand.toLowerCase().includes(q) && !p.model.toLowerCase().includes(q)) return false
      if (season !== null && !matchesSeason(season, p.season)) return false
      if (brand !== null && p.brand !== brand) return false
      if (width !== null && p.width !== width) return false
      if (profile !== null && p.profile !== profile) return false
      if (diameter !== null && p.diameter !== diameter) return false
      if (city !== null && !p.offers.some((o) => o.warehouse === city)) return false
      if (supplier !== null && !p.offers.some((o) => o.supplierName === supplier)) return false
      return true
    })
  }, [products, query, season, brand, width, profile, diameter, city, supplier])

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // Second click on the active season button clears it → all seasons shown.
  const onSeasonClick = (key: SeasonGroup) => {
    setSeason((cur) => (cur === key ? null : key))
  }

  const applySize = (size: { width: number; profile: number; diameter: number }) => {
    setQuery('')
    setWidth(size.width)
    setProfile(size.profile)
    setDiameter(size.diameter)
  }

  const handleAddToCart = (offer: OfferRow, productName: string) => {
    addItem({
      offerId: offer.offerId,
      canonicalProductId: '',
      productName,
      supplierId: '',
      supplierName: offer.supplierName,
      warehouse: offer.warehouse,
      unitPrice: offer.price,
      qty: 1,
    })
  }

  const totalOffers = filteredProducts.reduce((sum, p) => sum + p.offers.length, 0)

  // Single-select dropdown helper: maps a typed value <-> string option.
  const numberDropdown = (
    label: string,
    value: number | null,
    options: number[],
    set: (v: number | null) => void,
    fmt: (n: number) => string = String,
  ) => (
    <div className={styles.field}>
      <Caption1>{label}</Caption1>
      <Dropdown
        className={styles.dropdown}
        value={value !== null ? fmt(value) : `All`}
        selectedOptions={[value !== null ? String(value) : ALL]}
        onOptionSelect={(_, d) => set(d.optionValue === ALL ? null : Number(d.optionValue))}
      >
        <Option value={ALL}>All</Option>
        {options.map((o) => (
          <Option key={o} value={String(o)} text={fmt(o)}>{fmt(o)}</Option>
        ))}
      </Dropdown>
    </div>
  )

  const textDropdown = (
    label: string,
    value: string | null,
    options: string[],
    set: (v: string | null) => void,
  ) => (
    <div className={styles.field}>
      <Caption1>{label}</Caption1>
      <Dropdown
        className={styles.dropdown}
        placeholder={`All`}
        value={value ?? `All ${label.toLowerCase()}`}
        selectedOptions={[value ?? ALL]}
        onOptionSelect={(_, d) => set(d.optionValue === ALL ? null : (d.optionValue ?? null))}
      >
        <Option value={ALL} text={`All ${label.toLowerCase()}`}>All {label.toLowerCase()}</Option>
        {options.map((o) => (
          <Option key={o} value={o}>{o}</Option>
        ))}
      </Dropdown>
    </div>
  )

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
        {query && <Button onClick={() => setQuery('')}>Clear</Button>}
      </div>

      <div className={styles.popularSizes}>
        <Caption1>Popular sizes:</Caption1>
        {POPULAR_SIZES.map((size) => (
          <Button key={size.label} size="small" appearance="outline" onClick={() => applySize(size)}>
            {size.label}
          </Button>
        ))}
      </div>

      {error && (
        <MessageBar intent="error">
          <MessageBarBody>
            <MessageBarTitle>Could not load offers from Dataverse.</MessageBarTitle>
            {error}
          </MessageBarBody>
        </MessageBar>
      )}

      {/* Top horizontal filter bar */}
      <div className={styles.filterBar}>
        <div className={styles.seasonField}>
          <Caption1>Season</Caption1>
          <div className={styles.seasonGroup}>
            {SEASON_BUTTONS.map((b, i) => (
              <Button
                key={b.key}
                icon={b.icon}
                appearance={season === b.key ? 'primary' : 'outline'}
                onClick={() => onSeasonClick(b.key)}
                className={mergeClasses(
                  styles.seasonBtn,
                  i === 0 && styles.seasonBtnFirst,
                  i === SEASON_BUTTONS.length - 1 && styles.seasonBtnLast,
                )}
              >
                {b.label}
              </Button>
            ))}
          </div>
        </div>

        {numberDropdown('Width', width, availableWidths, setWidth)}
        {numberDropdown('Profile', profile, availableProfiles, setProfile)}
        {numberDropdown('Diameter', diameter, availableDiameters, setDiameter, (n) => `R${n}`)}
        {textDropdown('City', city, availableCities, setCity)}
        {textDropdown('Supplier', supplier, availableSuppliers, setSupplier)}
        {textDropdown('Brand', brand, availableBrands, setBrand)}
      </div>

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
  )
}
