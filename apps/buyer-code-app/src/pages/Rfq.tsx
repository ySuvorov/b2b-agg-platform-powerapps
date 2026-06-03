import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  makeStyles,
  tokens,
  Title2,
  Body1,
  Body1Strong,
  Caption1,
  Button,
  Checkbox,
  Textarea,
  Field,
  Input,
  Spinner,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
} from '@fluentui/react-components'
import { SendRegular } from '@fluentui/react-icons'
import { useCartStore } from '../store/cart'
import { fetchSuppliers } from '../services/dataverse'
import { broadcastRfq } from '../services/rfq'

const useStyles = makeStyles({
  root: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    maxWidth: '720px',
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  supplierList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: '12px 16px',
  },
  actions: {
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
  },
  hint: {
    color: tokens.colorNeutralForeground3,
  },
})

function defaultDeadline(): string {
  const d = new Date()
  d.setDate(d.getDate() + 7)
  return d.toISOString().slice(0, 10)
}

export default function Rfq() {
  const styles = useStyles()
  const navigate = useNavigate()
  // Subscribe only to `items` (a stable reference until the cart changes).
  // NOTE: do NOT select groupsBySupplier() here — it returns a fresh array each
  // call, which makes useSyncExternalStore loop and crashes the app.
  const cartItems = useCartStore((s) => s.items)

  const [suppliers, setSuppliers] = useState<{ b2b_supplierid: string; b2b_name: string }[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  // Pre-fill notes with a product summary from the current cart (computed once
  // at mount — the buyer arrives here from the cart, so the contents are stable).
  const [notes, setNotes] = useState(() =>
    cartItems.length === 0
      ? ''
      : `Requesting a quote for:\n${cartItems.map((i) => `- ${i.productName} ×${i.qty}`).join('\n')}`,
  )
  const [deadline, setDeadline] = useState(defaultDeadline())
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<{ kind: 'success' | 'error'; msg: string } | null>(null)

  // Load suppliers; pre-select those already represented in the cart.
  useEffect(() => {
    let alive = true
    fetchSuppliers()
      .then((s) => {
        if (!alive) return
        setSuppliers(s)
        // Default selection = suppliers present in the cart, else none.
        const cartNames = new Set(cartItems.map((i) => i.supplierName).filter(Boolean))
        setSelected(new Set(s.filter((x) => cartNames.has(x.b2b_name)).map((x) => x.b2b_name)))
        setLoading(false)
      })
      .catch(() => {
        if (!alive) return
        setResult({ kind: 'error', msg: 'Could not load suppliers.' })
        setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggle = (name: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })

  const handleSend = async () => {
    setSending(true)
    setResult(null)
    try {
      const supplierNames = Array.from(selected)
      const res = await broadcastRfq({ supplierNames, notes, deadline })
      setResult({
        kind: 'success',
        msg: `RFQ broadcast to ${res.created} supplier${res.created === 1 ? '' : 's'}. View them in the Operations app → RFQs.`,
      })
    } catch (e) {
      setResult({
        kind: 'error',
        msg: e instanceof Error ? e.message : 'Failed to send RFQ.',
      })
    } finally {
      setSending(false)
    }
  }

  const canSend = selected.size > 0 && notes.trim().length > 0 && !sending

  return (
    <div className={styles.root}>
      <Title2>New RFQ</Title2>
      <Body1 className={styles.hint}>
        Request quotes from multiple suppliers at once. Each selected supplier receives its own RFQ
        via the <Body1Strong>RFQ Broadcast</Body1Strong> flow.
      </Body1>

      {result && (
        <MessageBar intent={result.kind}>
          <MessageBarBody>
            <MessageBarTitle>{result.kind === 'success' ? 'RFQ sent' : 'Could not send RFQ'}</MessageBarTitle>
            {result.msg}
          </MessageBarBody>
        </MessageBar>
      )}

      <div className={styles.section}>
        <Body1Strong>Suppliers</Body1Strong>
        {loading ? (
          <Spinner size="tiny" label="Loading suppliers…" />
        ) : (
          <div className={styles.supplierList}>
            {suppliers.map((s) => (
              <Checkbox
                key={s.b2b_supplierid}
                label={s.b2b_name}
                checked={selected.has(s.b2b_name)}
                onChange={() => toggle(s.b2b_name)}
              />
            ))}
            {suppliers.length === 0 && <Caption1>No suppliers found.</Caption1>}
          </div>
        )}
      </div>

      <Field label="Deadline">
        <Input type="date" value={deadline} onChange={(_, d) => setDeadline(d.value)} />
      </Field>

      <Field label="Notes / requested items" required>
        <Textarea
          value={notes}
          onChange={(_, d) => setNotes(d.value)}
          rows={6}
          placeholder="Describe the products and quantities you want quoted…"
        />
      </Field>

      <div className={styles.actions}>
        <Button
          appearance="primary"
          icon={sending ? <Spinner size="tiny" /> : <SendRegular />}
          disabled={!canSend}
          onClick={handleSend}
        >
          {sending
            ? 'Sending…'
            : selected.size > 1
              ? `Send RFQ to ${selected.size} suppliers`
              : 'Send RFQ'}
        </Button>
        <Button appearance="subtle" onClick={() => navigate('/search')}>
          Back to Search
        </Button>
      </div>
    </div>
  )
}
