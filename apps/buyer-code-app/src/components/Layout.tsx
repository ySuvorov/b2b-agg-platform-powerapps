import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { makeStyles, tokens, mergeClasses, Badge, Button, Tooltip } from '@fluentui/react-components'
import {
  HomeRegular,
  SearchRegular,
  CartRegular,
  DocumentRegular,
  ChartMultipleRegular,
  MailRegular,
  PanelLeftContractRegular,
  PanelLeftExpandRegular,
  type FluentIcon,
} from '@fluentui/react-icons'
import { useCartStore } from '../store/cart'
import BotPanel from './BotPanel'

const SIDEBAR_STORAGE_KEY = 'b2bagg.sidebarCollapsed'

interface NavEntry {
  to: string
  label: string
  icon: FluentIcon
  badge?: boolean
}

const NAV: NavEntry[] = [
  { to: '/home', label: 'Home', icon: HomeRegular },
  { to: '/search', label: 'Search', icon: SearchRegular },
  { to: '/cart', label: 'Cart', icon: CartRegular, badge: true },
  { to: '/rfq/new', label: 'New RFQ', icon: MailRegular },
  { to: '/orders', label: 'Orders', icon: DocumentRegular },
  { to: '/insights', label: 'Insights', icon: ChartMultipleRegular },
]

const useStyles = makeStyles({
  root: {
    display: 'flex',
    height: '100vh',
    overflow: 'hidden',
  },
  sidebar: {
    width: '220px',
    minWidth: '220px',
    backgroundColor: tokens.colorNeutralBackground2,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    display: 'flex',
    flexDirection: 'column',
    padding: '12px 0',
    transitionProperty: 'width, min-width',
    transitionDuration: tokens.durationNormal,
    transitionTimingFunction: tokens.curveEasyEase,
  },
  sidebarCollapsed: {
    width: '52px',
    minWidth: '52px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '8px',
    padding: '0 12px 12px',
    minHeight: '32px',
  },
  headerCollapsed: {
    justifyContent: 'center',
    padding: '0 0 12px',
  },
  brand: {
    fontWeight: '600',
    fontSize: '14px',
    color: tokens.colorNeutralForeground2,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '10px 16px',
    textDecoration: 'none',
    color: tokens.colorNeutralForeground1,
    fontSize: '14px',
    borderRadius: tokens.borderRadiusMedium,
    margin: '2px 8px',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    '&:hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  navItemCollapsed: {
    justifyContent: 'center',
    padding: '10px 0',
    gap: 0,
    margin: '2px 6px',
  },
  navItemActive: {
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorBrandForeground1,
    fontWeight: '600',
  },
  label: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flex: 1,
  },
  // Icon wrapper so the cart count can float over the icon when collapsed.
  iconWrap: {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
  },
  collapsedBadge: {
    position: 'absolute',
    top: '-6px',
    right: '-8px',
  },
  content: {
    flex: 1,
    overflow: 'auto',
    backgroundColor: tokens.colorNeutralBackground1,
  },
})

export default function Layout() {
  const styles = useStyles()
  const totalItems = useCartStore((s) => s.totalItems())
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1',
  )

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? '1' : '0')
      return next
    })
  }

  return (
    <div className={styles.root}>
      <nav className={mergeClasses(styles.sidebar, collapsed && styles.sidebarCollapsed)}>
        <div className={mergeClasses(styles.header, collapsed && styles.headerCollapsed)}>
          {!collapsed && <span className={styles.brand}>B2BAgg</span>}
          <Tooltip
            content={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            relationship="label"
            positioning="after"
          >
            <Button
              appearance="subtle"
              size="small"
              icon={collapsed ? <PanelLeftExpandRegular /> : <PanelLeftContractRegular />}
              onClick={toggle}
              aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            />
          </Tooltip>
        </div>

        {NAV.map((entry) => {
          const Icon = entry.icon
          const showBadge = entry.badge && totalItems > 0
          const link = (
            <NavLink
              key={entry.to}
              to={entry.to}
              className={({ isActive }) =>
                mergeClasses(
                  styles.navItem,
                  collapsed && styles.navItemCollapsed,
                  isActive && styles.navItemActive,
                )
              }
            >
              <span className={styles.iconWrap}>
                <Icon fontSize={18} />
                {collapsed && showBadge && (
                  <Badge
                    className={styles.collapsedBadge}
                    appearance="filled"
                    color="brand"
                    size="small"
                  >
                    {totalItems}
                  </Badge>
                )}
              </span>
              {!collapsed && (
                <span className={styles.label}>
                  {entry.label}
                  {showBadge && (
                    <Badge appearance="filled" color="brand" size="small">
                      {totalItems}
                    </Badge>
                  )}
                </span>
              )}
            </NavLink>
          )

          return collapsed ? (
            <Tooltip
              key={entry.to}
              content={entry.label}
              relationship="label"
              positioning="after"
            >
              {link}
            </Tooltip>
          ) : (
            link
          )
        })}
      </nav>
      <main className={styles.content}>
        <Outlet />
      </main>
      <BotPanel />
    </div>
  )
}
