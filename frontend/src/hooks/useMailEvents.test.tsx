import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { useMailEvents, MAIL_EVENTS_URL } from './useMailEvents.ts'
import { useLiveStore } from '../stores/live.ts'

/** A hand-driven EventSource: the test fires the events. */
class FakeEventSource {
  static instances: FakeEventSource[] = []
  url: string
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {}
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor(url: string) { this.url = url; FakeEventSource.instances.push(this) }
  addEventListener(type: string, fn: (e: MessageEvent) => void) { (this.listeners[type] ??= []).push(fn) }
  close() { this.closed = true }
  emit(type: string, data: object) { for (const fn of this.listeners[type] ?? []) fn({ data: JSON.stringify(data) } as MessageEvent) }
}

function Probe() { useMailEvents(); return null }

describe('useMailEvents (MAIL-37)', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
    useLiveStore.setState({ connected: false, lastEvent: null, syncing: {} })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('connects to the event stream, tracks sync state, and refreshes mail queries when a sync finishes', () => {
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const r = render(<QueryClientProvider client={qc}><Probe /></QueryClientProvider>)
    const es = FakeEventSource.instances[0]
    expect(es.url).toBe(MAIL_EVENTS_URL)
    es.onopen?.()
    expect(useLiveStore.getState().connected).toBe(true)
    es.emit('sync.started', { id: 1, type: 'sync.started', at: '2026-10-09T14:00:00Z', account_id: 'a' })
    expect(useLiveStore.getState().syncing.a).toBe(true)
    expect(spy).not.toHaveBeenCalled()
    es.emit('sync.finished', { id: 2, type: 'sync.finished', at: '2026-10-09T14:00:05Z', account_id: 'a', result: { emails_fetched: 3 } })
    expect(useLiveStore.getState().syncing.a).toBe(false)
    expect(spy).toHaveBeenCalledWith({ queryKey: ['mail'] })
    es.emit('outbound.sent', { id: 3, type: 'outbound.sent', at: '2026-10-09T14:00:06Z' })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['outbound-drafts'] })
    es.onerror?.()
    expect(useLiveStore.getState().connected).toBe(false)
    r.unmount()
    expect(es.closed).toBe(true)
  })
})
