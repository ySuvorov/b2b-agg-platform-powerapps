import { Outlet, NavLink } from 'react-router-dom'
import { makeStyles, tokens, Badge } from '@fluentui/react-components'
import { HomeRegular, SearchRegular, CartRegular, DocumentRegular } from '@fluentui/react-icons'
import { useCartStore } from '../store/cart'

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
    padding: '16px 0',
  },
  sidebarTitle: {
    padding: '0 16px 16px',
    fontWeight: '600',
    fontSize: '14px',
    color: tokens.colorNeutralForeground2,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '10px 16px',
    textDecoration: 'none',
    color: tokens.colorNeutralForeground1,
    fontSize: '14px',
    borderRadius: '4px',
    margin: '2px 8px',
    '&:hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  navItemActive: {
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorBrandForeground1,
    fontWeight: '600',
  },
  cartLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flex: 1,
  },
  content: {
    flex: 1,
    overflow: 'auto',
    backgroundColor: tokens.colorNeutralBackground1,
  },
})

export default function Layout() {
  const styles = useStyles()
  const totalItems = useCartStore(s => s.totalItems())

  return (
    <div className={styles.root}>
      <nav className={styles.sidebar}>
        <div className={styles.sidebarTitle}>B2BAgg</div>
        <NavLink
          to="/home"
          className={({ isActive }) =>
            `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
          }
        >
          <HomeRegular fontSize={18} />
          Home
        </NavLink>
        <NavLink
          to="/search"
          className={({ isActive }) =>
            `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
          }
        >
          <SearchRegular fontSize={18} />
          Search
        </NavLink>
        <NavLink
          to="/cart"
          className={({ isActive }) =>
            `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
          }
        >
          <CartRegular fontSize={18} />
          <span className={styles.cartLabel}>
            Cart
            {totalItems > 0 && (
              <Badge appearance="filled" color="brand" size="small">
                {totalItems}
              </Badge>
            )}
          </span>
        </NavLink>
        <NavLink
          to="/orders"
          className={({ isActive }) =>
            `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
          }
        >
          <DocumentRegular fontSize={18} />
          Orders
        </NavLink>
      </nav>
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  )
}
