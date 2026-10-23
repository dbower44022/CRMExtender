/** Composer helpers (MAIL-34/35), kept out of the component files so
 * fast refresh and the tests can import them directly. */

import type { Signature } from '../api/outbound.ts'
import type { ComposeMode, Composer } from '../stores/compose.ts'

export function modeLabel(mode: ComposeMode): string {
  return mode === 'reply' ? 'Reply' : mode === 'reply_all' ? 'Reply all' : mode === 'forward' ? 'Forward' : 'New message'
}

/** The signature the server will add on send: the account's default, else the
 * user's overall default (same order as the server). */
export function defaultSignature(signatures: Signature[], accountId: string): Signature | null {
  if (!signatures.length) return null
  const forAccount = accountId ? signatures.find((s) => s.is_default && s.provider_account_id === accountId) : undefined
  return forAccount ?? signatures.find((s) => s.is_default && !s.provider_account_id) ?? null
}

export function fmtBytes(n: number | null | undefined): string {
  if (!n) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

/** Quick picks for scheduled send: the next working-hour slots. */
export function scheduleOptions(now: Date): { label: string; at: Date }[] {
  const at = (daysAhead: number, hour: number) => {
    const d = new Date(now)
    d.setDate(d.getDate() + daysAhead)
    d.setHours(hour, 0, 0, 0)
    return d
  }
  const out: { label: string; at: Date }[] = []
  const laterToday = at(0, now.getHours() + 3)
  if (laterToday.getDate() === now.getDate() && laterToday.getHours() <= 18) out.push({ label: 'In 3 hours', at: laterToday })
  out.push({ label: 'Tomorrow morning', at: at(1, 8) })
  const dow = now.getDay()                     // 0 = Sunday
  const toMonday = ((8 - dow) % 7) || 7
  out.push({ label: 'Monday morning', at: at(toMonday, 8) })
  return out
}

/** Seconds left on a pending send, never negative. */
export function secondsLeft(sendAt: number, now: number = Date.now()): number {
  return Math.max(0, Math.ceil((sendAt - now) / 1000))
}

/** True when an inline composer belongs to the thread now open in the mail view. */
export function isInlineVisible(c: Composer, mailMode: boolean, threadId: string | null): boolean {
  return c.placement === 'inline' && mailMode && !!threadId && !!c.context?.threadKey && c.context.threadKey.endsWith(`:${threadId}`)
}
