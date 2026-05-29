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
import { DeleteRegular, CartRegular } from '@fluentui/react-icons'
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
  table: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    overflow: 'hidden',
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
  const { items, removeItem, updateQty, clearCart, totalItems, totalPrice } = useCartStore()
  const [placing, setPlacing] = useState(false)
  const [orderResult, setOrderResult] = useState<'success' | 'error' | null>(null)

  const handlePlaceOrder = async () => {
    setPlacing(true)
    try {
      await createOrder(
        items.map((i) => ({
          offerId: i.offerId,
          productName: i.productName,
          supplierName: i.supplierName,
          warehouse: i.warehouse,
          unitPrice: i.unitPrice,
          qty: i.qty,
        })),
      )
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
            <MessageBarTitle>Order placed successfully!</MessageBarTitle>
            Check Orders page to track your order.
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
          <div className={styles.table}>
            <div className={styles.tableHeader}>
              <span>Product</span>
              <span>Supplier</span>
              <span>Warehouse</span>
              <span>Price</span>
              <span>Qty</span>
              <span>Subtotal</span>
              <span></span>
            </div>
            {items.map((item) => (
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

          <div className={styles.summary}>
            <Body1>
              Total: <Body1Strong>{totalItems()} items</Body1Strong>
            </Body1>
            <Body1Strong>${totalPrice().toLocaleString('en-US', { minimumFractionDigits: 2 })}</Body1Strong>
            <Button
              appearance="primary"
              disabled={placing}
              icon={placing ? <Spinner size="tiny" /> : undefined}
              onClick={handlePlaceOrder}
            >
              {placing ? 'Placing…' : 'Place Order'}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
