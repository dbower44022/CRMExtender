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
import { useLiveStore, type LiveEvent } from '../stores/live.ts'

export const MAIL_EVENTS_URL = '/api/v1/mail/events'
const REFRESH_ON = new Set(['sync.finished', 'post_pass.finished', 'outbound.sent'])

export function useMailEvents(enabled = true) {
  const qc = useQueryClient()
  const setConnected = useLiveStore((s) => s.setConnected)
  const recordEvent = useLiveStore((s) => s.recordEvent)
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
    }
    for (const t of ['sync.started', 'sync.finished', 'post_pass.finished', 'outbound.sent']) es.addEventListener(t, onEvent)
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    return () => { es.close(); setConnected(false) }
  }, [enabled, qc, setConnected, recordEvent])
}
