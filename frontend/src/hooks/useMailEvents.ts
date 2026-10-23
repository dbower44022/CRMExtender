/** Server-sent events from the scheduler (MAIL-37).
 *
 * One EventSource per tab. A finished account sync or post pass, or a
 * queued message going out, invalidates the mail queries so the folder
 * counts, the open list, and the open thread refresh at once. The timed
 * polling in api/mail.ts stays as the fallback; the browser reconnects on
 * its own when the stream drops.
 */

import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useLiveStore, type LiveEvent } from '../stores/live.ts'
import { useNavigationStore } from '../stores/navigation.ts'
import { describeNotifications, selectNotifications, type NewMailEvent, type NotifyMode } from '../lib/mailNotify.ts'
import { get } from '../api/client.ts'

export const MAIL_EVENTS_URL = '/api/v1/mail/events'
const REFRESH_ON = new Set(['sync.finished', 'post_pass.finished', 'outbound.sent', 'mail.new'])

interface AccountSetting { id: string; email_address: string; notifications: NotifyMode }

/** The per-account notification mode, read fresh (cheap) so a change on the
 * Accounts page applies to the next event without a reload. */
async function notifyModeFor(accountId: string): Promise<{ mode: NotifyMode; email?: string }> {
  try {
    const accounts = await get<AccountSetting[]>('/settings/accounts')
    const a = accounts.find((x) => x.id === accountId)
    return { mode: a?.notifications ?? 'known_contacts', email: a?.email_address }
  } catch {
    return { mode: 'known_contacts' }
  }
}

/** Show pop-ups for a mail.new event per the account's setting (MAIL-39). */
export async function announceNewMail(ev: NewMailEvent, openThread: (accountId: string, threadId: string) => void) {
  const { mode, email } = await notifyModeFor(ev.account_id)
  const items = selectNotifications(ev, mode)
  if (!items) return
  for (const n of describeNotifications(items, ev.count, email)) {
    toast(n.title, {
      description: n.body,
      duration: 8000,
      action: n.item?.thread_id ? { label: 'Open', onClick: () => openThread(ev.account_id, n.item!.thread_id!) } : undefined,
    })
  }
}

export function useMailEvents(enabled = true) {
  const qc = useQueryClient()
  const setConnected = useLiveStore((s) => s.setConnected)
  const recordEvent = useLiveStore((s) => s.recordEvent)
  const openMail = useNavigationStore((s) => s.openMail)
  useEffect(() => {
    if (!enabled || typeof EventSource === 'undefined') return
    const es = new EventSource(MAIL_EVENTS_URL, { withCredentials: true })
    const onEvent = (raw: MessageEvent) => {
      let e: LiveEvent
      try { e = JSON.parse(raw.data) } catch { return }
      recordEvent(e)
      if (REFRESH_ON.has(e.type)) {
        qc.invalidateQueries({ queryKey: ['mail'] })
        if (e.type === 'outbound.sent') qc.invalidateQueries({ queryKey: ['outbound-drafts'] })
      }
      if (e.type === 'mail.new') {
        void announceNewMail(e as unknown as NewMailEvent, (acct, thread) => openMail(acct, 'inbox', thread))
      }
    }
    for (const t of ['sync.started', 'sync.finished', 'post_pass.finished', 'outbound.sent', 'mail.new']) es.addEventListener(t, onEvent)
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    return () => { es.close(); setConnected(false) }
  }, [enabled, qc, setConnected, recordEvent, openMail])
}
