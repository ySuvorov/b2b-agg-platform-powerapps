import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  makeStyles,
  tokens,
  Title2,
  Body1,
  Body1Strong,
  Caption1,
  Button,
  Spinner,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
} from '@fluentui/react-components'
import { DeleteRegular, CartRegular, MailRegular } from '@fluentui/react-icons'
import { useCartStore } from '../store/cart'
import { createOrder } from '../services/dataverse'

const useStyles = makeStyles({
  root: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tableHeader: {
    display: 'grid',
    gridTemplateColumns: '3fr 2fr 2fr 1fr 1fr 1fr auto',
    gap: '8px',
    padding: '10px 16px',
    backgroundColor: tokens.colorNeutralBackground2,
    fontWeight: '600',
    fontSize: '12px',
    color: tokens.colorNeutralForeground2,
  },
  supplierGroup: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    overflow: 'hidden',
  },
  supplierGroupHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 16px',
    backgroundColor: tokens.colorNeutralBackground3,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  tableRow: {
    display: 'grid',
    gridTemplateColumns: '3fr 2fr 2fr 1fr 1fr 1fr auto',
    gap: '8px',
    padding: '12px 16px',
    alignItems: 'center',
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  qtyControl: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  summary: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '24px',
    alignItems: 'center',
    padding: '16px 0',
  },
  emptyState: {
    textAlign: 'center',
    padding: '64px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    alignItems: 'center',
  },
})

export default function Cart() {
  const styles = useStyles()
  const navigate = useNavigate()
  const { items, removeItem, updateQty, clearCart, totalItems, totalPrice, groupsBySupplier } =
    useCartStore()
  const groups = groupsBySupplier()
  const [placing, setPlacing] = useState(false)
  const [orderResult, setOrderResult] = useState<'success' | 'error' | null>(null)
  const [ordersPlaced, setOrdersPlaced] = useState(0)

  const handlePlaceOrder = async () => {
    setPlacing(true)
    try {
      const orderIds = await createOrder(
        items.map((i) => ({
          offerId: i.offerId,
          productName: i.productName,
          supplierName: i.supplierName,
          warehouse: i.warehouse,
          unitPrice: i.unitPrice,
          qty: i.qty,
        })),
      )
      setOrdersPlaced(orderIds.length)
      clearCart()
      setOrderResult('success')
    } catch {
      setOrderResult('error')
    } finally {
      setPlacing(false)
    }
  }

  if (items.length === 0 && orderResult !== 'success') {
    return (
      <div className={styles.root}>
        <div className={styles.emptyState}>
          <CartRegular fontSize={48} />
          <Body1Strong>Your cart is empty</Body1Strong>
          <Body1>Browse products in Search and add items to your cart.</Body1>
          <Button appearance="primary" onClick={() => navigate('/search')}>
            Go to Search
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <Title2>Cart ({totalItems()} items)</Title2>
        {items.length > 0 && (
          <Button appearance="subtle" onClick={() => clearCart()}>
            Clear cart
          </Button>
        )}
      </div>

      {orderResult === 'success' && (
        <MessageBar intent="success">
          <MessageBarBody>
            <MessageBarTitle>
              {ordersPlaced > 1
                ? `${ordersPlaced} orders placed — one per supplier.`
                : 'Order placed successfully!'}
            </MessageBarTitle>
            A multi-supplier cart is split into a separate order per supplier.
            Check the Orders page to track them.
          </MessageBarBody>
        </MessageBar>
      )}

      {orderResult === 'error' && (
        <MessageBar intent="error">
          <MessageBarBody>
            <MessageBarTitle>Failed to place order.</MessageBarTitle>
            Please try again.
          </MessageBarBody>
        </MessageBar>
      )}

      {items.length > 0 && (
        <>
          {groups.length > 1 && (
            <Body1>
              Your cart spans <Body1Strong>{groups.length} suppliers</Body1Strong> — it will be
              placed as {groups.length} separate orders.
            </Body1>
          )}

          {groups.map((group) => (
            <div key={group.supplierName} className={styles.supplierGroup}>
              <div className={styles.supplierGroupHeader}>
                <Body1Strong>{group.supplierName}</Body1Strong>
                <Caption1>
                  {group.items.length} {group.items.length === 1 ? 'line' : 'lines'} · $
                  {group.subtotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </Caption1>
              </div>
              <div className={styles.tableHeader}>
                <span>Product</span>
                <span>Supplier</span>
                <span>Warehouse</span>
                <span>Price</span>
                <span>Qty</span>
                <span>Subtotal</span>
                <span></span>
              </div>
              {group.items.map((item) => (
                <div key={item.offerId} className={styles.tableRow}>
                  <Caption1>{item.productName}</Caption1>
                  <Caption1>{item.supplierName}</Caption1>
                  <Caption1>{item.warehouse || '—'}</Caption1>
                  <Caption1>${item.unitPrice.toFixed(2)}</Caption1>
                  <div className={styles.qtyControl}>
                    <Button
                      size="small"
                      appearance="outline"
                      onClick={() => updateQty(item.offerId, item.qty - 1)}
                    >
                      −
                    </Button>
                    <Caption1>{item.qty}</Caption1>
                    <Button
                      size="small"
                      appearance="outline"
                      onClick={() => updateQty(item.offerId, item.qty + 1)}
                    >
                      +
                    </Button>
                  </div>
                  <Caption1>${(item.unitPrice * item.qty).toFixed(2)}</Caption1>
                  <Button
                    size="small"
                    appearance="subtle"
                    icon={<DeleteRegular />}
                    onClick={() => removeItem(item.offerId)}
                  />
                </div>
              ))}
            </div>
          ))}

          <div className={styles.summary}>
            <Body1>
              Total: <Body1Strong>{totalItems()} items</Body1Strong>
            </Body1>
            <Body1Strong>${totalPrice().toLocaleString('en-US', { minimumFractionDigits: 2 })}</Body1Strong>
            <Button
              appearance="outline"
              icon={<MailRegular />}
              disabled={placing}
              onClick={() => navigate('/rfq/new')}
            >
              Request quotes
            </Button>
            <Button
              appearance="primary"
              disabled={placing}
              icon={placing ? <Spinner size="tiny" /> : undefined}
              onClick={handlePlaceOrder}
            >
              {placing
                ? 'Placing…'
                : groups.length > 1
                  ? `Place ${groups.length} Orders`
                  : 'Place Order'}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
