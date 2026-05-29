import { useState, useEffect } from 'react'
import {
  makeStyles,
  tokens,
  Title2,
  Title3,
  Body1Strong,
  Caption1,
  Badge,
  Skeleton,
  SkeletonItem,
  Divider,
  Table,
  TableHeader,
  TableHeaderCell,
  TableBody,
  TableRow,
  TableCell,
} from '@fluentui/react-components'
import {
  BuildingRegular,
  BoxMultipleRegular,
  TagMultipleRegular,
  MapRegular,
} from '@fluentui/react-icons'
import { fetchStats, fetchOrders } from '../services/dataverse'
import type { Order } from '../types'
import { ORDER_STATUS, ORDER_STATUS_COLOR } from '../types'

const useStyles = makeStyles({
  root: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  banner: {
    color: tokens.colorNeutralForeground2,
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '16px',
  },
  statCard: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  statHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    color: tokens.colorNeutralForeground2,
  },
  statValue: {
    fontSize: '32px',
    fontWeight: '700',
    color: tokens.colorBrandForeground1,
    lineHeight: '1',
  },
  ordersSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  skeletonCard: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
})

interface Stats {
  suppliers: number
  products: number
  offers: number
  regions: number
}

interface StatCardProps {
  label: string
  value: number | null
  icon: React.ReactNode
}

function StatCard({ label, value, icon }: StatCardProps) {
  const styles = useStyles()

  if (value === null) {
    return (
      <div className={styles.skeletonCard}>
        <Skeleton>
          <SkeletonItem size={16} style={{ width: '60%' }} />
          <SkeletonItem size={40} style={{ width: '40%', marginTop: '8px' }} />
        </Skeleton>
      </div>
    )
  }

  return (
    <div className={styles.statCard}>
      <div className={styles.statHeader}>
        {icon}
        <Caption1>{label}</Caption1>
      </div>
      <div className={styles.statValue}>{value}</div>
    </div>
  )
}

export default function Home() {
  const styles = useStyles()
  const [stats, setStats] = useState<Stats | null>(null)
  const [orders, setOrders] = useState<Order[]>([])

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() =>
        setStats({ suppliers: 0, products: 0, offers: 0, regions: 0 }),
      )

    fetchOrders()
      .then((data) => setOrders(data.slice(0, 3)))
      .catch(() => setOrders([]))
  }, [])

  return (
    <div className={styles.root}>
      <Title2 className={styles.banner}>
        B2BAgg Market Intelligence — Wholesale Tire Platform
      </Title2>

      <div className={styles.statsGrid}>
        <StatCard
          label="Suppliers"
          value={stats?.suppliers ?? null}
          icon={<BuildingRegular />}
        />
        <StatCard
          label="Products"
          value={stats?.products ?? null}
          icon={<BoxMultipleRegular />}
        />
        <StatCard
          label="Total Offers"
          value={stats?.offers ?? null}
          icon={<TagMultipleRegular />}
        />
        <StatCard
          label="Regions"
          value={stats?.regions ?? null}
          icon={<MapRegular />}
        />
      </div>

      <Divider />

      <div className={styles.ordersSection}>
        <Title3>Recent Orders</Title3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Order #</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Total</TableHeaderCell>
              <TableHeaderCell>Date</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((order) => (
              <TableRow key={order.b2b_orderid}>
                <TableCell>
                  <Body1Strong>{order.b2b_order_number ?? '(draft)'}</Body1Strong>
                </TableCell>
                <TableCell>
                  <Badge
                    color={ORDER_STATUS_COLOR[order.b2b_status]}
                    appearance="filled"
                  >
                    {ORDER_STATUS[order.b2b_status]}
                  </Badge>
                </TableCell>
                <TableCell>${(order.b2b_total_amount ?? 0).toFixed(2)}</TableCell>
                <TableCell>
                  {new Date(order.createdon).toLocaleDateString('en-GB')}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
