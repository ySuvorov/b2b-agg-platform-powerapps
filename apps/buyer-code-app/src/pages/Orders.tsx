import { useState, useEffect } from 'react'
import {
  makeStyles,
  tokens,
  Title2,
  Body1Strong,
  Caption1,
  Badge,
  Spinner,
} from '@fluentui/react-components'
import { ChevronDownRegular, ChevronRightRegular } from '@fluentui/react-icons'
import { fetchOrders } from '../services/dataverse'
import type { Order } from '../types'
import { ORDER_STATUS, ORDER_STATUS_COLOR } from '../types'

const useStyles = makeStyles({
  root: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  orderCard: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    overflow: 'hidden',
    marginBottom: '8px',
  },
  orderHeader: {
    display: 'grid',
    gridTemplateColumns: 'auto 2fr 1fr 1fr 1fr',
    gap: '12px',
    padding: '12px 16px',
    alignItems: 'center',
    cursor: 'pointer',
    ':hover': { backgroundColor: tokens.colorNeutralBackground2 },
  },
  orderLines: {
    padding: '0 16px 12px',
  },
  lineHeader: {
    display: 'grid',
    gridTemplateColumns: '3fr 2fr 2fr 1fr 1fr',
    gap: '8px',
    padding: '8px 0',
    fontWeight: '600',
    fontSize: '11px',
    color: tokens.colorNeutralForeground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  lineRow: {
    display: 'grid',
    gridTemplateColumns: '3fr 2fr 2fr 1fr 1fr',
    gap: '8px',
    padding: '6px 0',
    fontSize: '13px',
  },
  emptyState: {
    textAlign: 'center',
    padding: '48px',
    color: tokens.colorNeutralForeground2,
  },
})

export default function Orders() {
  const styles = useStyles()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchOrders().then((data) => {
      setOrders(data)
      setLoading(false)
    })
  }, [])

  const toggle = (orderId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(orderId)) next.delete(orderId)
      else next.add(orderId)
      return next
    })
  }

  return (
    <div className={styles.root}>
      <Title2>Orders</Title2>

      {loading ? (
        <Spinner label="Loading orders..." />
      ) : orders.length === 0 ? (
        <div className={styles.emptyState}>
          <Caption1>No orders yet.</Caption1>
        </div>
      ) : (
        orders.map((order) => {
          const isExpanded = expanded.has(order.b2b_orderid)
          return (
            <div key={order.b2b_orderid} className={styles.orderCard}>
              <div
                className={styles.orderHeader}
                onClick={() => toggle(order.b2b_orderid)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') toggle(order.b2b_orderid)
                }}
              >
                {isExpanded ? <ChevronDownRegular /> : <ChevronRightRegular />}
                <Body1Strong>{order.b2b_name}</Body1Strong>
                <Badge
                  appearance="filled"
                  color={ORDER_STATUS_COLOR[order.b2b_status]}
                >
                  {ORDER_STATUS[order.b2b_status] ?? order.b2b_status}
                </Badge>
                <Caption1>
                  ${order.b2b_total_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </Caption1>
                <Caption1>
                  {new Date(order.createdon).toLocaleDateString('en-GB', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                  })}
                </Caption1>
              </div>

              {isExpanded && order.orderlines && order.orderlines.length > 0 && (
                <div className={styles.orderLines}>
                  <div className={styles.lineHeader}>
                    <span>Product</span>
                    <span>Supplier</span>
                    <span>Warehouse</span>
                    <span>Qty</span>
                    <span>Price</span>
                  </div>
                  {order.orderlines.map((line) => (
                    <div key={line.b2b_orderlineid} className={styles.lineRow}>
                      <span>{line.productName ?? '—'}</span>
                      <span>{line.supplierName ?? '—'}</span>
                      <span>{line.warehouse ?? '—'}</span>
                      <span>{line.b2b_qty}</span>
                      <span>${(line.b2b_unit_price * line.b2b_qty).toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
