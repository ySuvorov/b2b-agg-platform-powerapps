// ---------------------------------------------------------------------------
// RFQ Broadcast — submit one RFQ per selected supplier.
//
// The actual fan-out (one b2b_rfq row per supplier) is done by the Power
// Automate flow `RFQ Broadcast` (trigger: "When Power Apps (V2) calls a flow"),
// NOT by the Code App — so we never touch the b2b_rfq table from here. The Code
// App only collects the request and invokes the flow via the generated
// RFQBroadcastService (added with `npx power-apps add-flow`).
//
// Flow input contract (verified against the exported flow definition):
//   text   = supplier names, ';'-joined  →  split + Apply to each
//   text_1 = notes                       →  b2b_notes
//   text_2 = deadline (ISO or empty)     →  b2b_deadline
// Output: { created } = number of b2b_rfq rows the flow wrote.
// ---------------------------------------------------------------------------

import { RFQBroadcastService } from '../generated/services/RFQBroadcastService'

const USE_MOCK = (import.meta.env.VITE_USE_MOCK as string | undefined) === 'true'

export interface RfqBroadcastInput {
  /** Supplier display names — the flow looks each up by `b2b_name`. */
  supplierNames: string[]
  /** Free-text body; the requested products are summarised here (b2b_rfq has
   *  no line-item child table, mirroring the MarketBot Create RFQ flow). */
  notes: string
  /** Optional ISO date for `b2b_deadline`. */
  deadline?: string
}

export interface RfqBroadcastResult {
  /** Number of b2b_rfq rows the flow reported creating. */
  created: number
}

export async function broadcastRfq(input: RfqBroadcastInput): Promise<RfqBroadcastResult> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 400))
    return { created: input.supplierNames.length }
  }

  const result = await RFQBroadcastService.Run({
    text: input.supplierNames.join(';'),
    text_1: input.notes,
    text_2: input.deadline ?? '',
  })

  if (!result.success) {
    throw result.error ?? new Error('RFQ Broadcast flow failed')
  }
  // The flow returns the count it wrote; fall back to the request size if the
  // response is empty (e.g. older flow definition without the `created` output).
  return { created: result.data?.created ?? input.supplierNames.length }
}
