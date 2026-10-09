/** New-mail notification rules (MAIL-39): which items of a `mail.new`
 * event to announce under the account's setting, and how to word them. */

export type NotifyMode = 'all' | 'known_contacts' | 'none'

export interface NewMailItem {
  communication_id: string
  thread_id: string | null
  sender_address: string | null
  sender_name: string | null
  known_contact: boolean
  subject: string
  snippet: string
  timestamp: string
}

export interface NewMailEvent {
  type: 'mail.new'
  account_id: string
  email?: string
  count: number
  items: NewMailItem[]
}

/** Items to announce; `null` when the setting says to stay quiet. */
export function selectNotifications(ev: NewMailEvent, mode: NotifyMode): NewMailItem[] | null {
  if (mode === 'none') return null
  const items = mode === 'all' ? ev.items : ev.items.filter((i) => i.known_contact)
  return items.length ? items : null
}

export const MAX_SEPARATE = 3

/** One pop-up per message up to MAX_SEPARATE; beyond that, one summary. */
export function describeNotifications(items: NewMailItem[], total: number, accountEmail?: string): { title: string; body: string; item?: NewMailItem }[] {
  if (items.length <= MAX_SEPARATE) {
    return items.map((i) => ({ title: i.sender_name || i.sender_address || 'New mail', body: i.subject, item: i }))
  }
  const n = Math.max(total, items.length)
  return [{ title: `${n} new messages${accountEmail ? ` for ${accountEmail}` : ''}`, body: items.slice(0, 3).map((i) => i.subject).join(' · ') }]
}
