import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { useMailEvents, MAIL_EVENTS_URL, announceNewMail } from './useMailEvents.ts'
import { useLiveStore } from '../stores/live.ts'
import { stubFetch } from '../test/utils.tsx'

const toastSpy = vi.hoisted(() => vi.fn())
vi.mock('sonner', () => ({ toast: toastSpy }))

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

  it('announces new mail per the account setting and opens the thread from the pop-up (MAIL-39)', async () => {
    toastSpy.mockClear()
    stubFetch({ '/api/v1/settings/accounts': [{ id: 'a', email_address: 'me@x.com', notifications: 'known_contacts' }] })
    const open = vi.fn()
    await announceNewMail({
      type: 'mail.new', account_id: 'a', count: 2,
      items: [
        { communication_id: 'c1', thread_id: 't1', sender_address: 'ada@x.com', sender_name: 'Ada', known_contact: true, subject: 'Lunch?', snippet: '', timestamp: '' },
        { communication_id: 'c2', thread_id: 't2', sender_address: 'spam@x.com', sender_name: null, known_contact: false, subject: 'Buy', snippet: '', timestamp: '' },
      ],
    }, open)
    expect(toastSpy).toHaveBeenCalledTimes(1)
    const [title, opts] = toastSpy.mock.calls[0]
    expect(title).toBe('Ada')
    expect(opts.description).toBe('Lunch?')
    opts.action.onClick()
    expect(open).toHaveBeenCalledWith('a', 't1')
    // none: silent
    toastSpy.mockClear()
    stubFetch({ '/api/v1/settings/accounts': [{ id: 'a', email_address: 'me@x.com', notifications: 'none' }] })
    await announceNewMail({ type: 'mail.new', account_id: 'a', count: 1, items: [
      { communication_id: 'c1', thread_id: 't1', sender_address: 'ada@x.com', sender_name: 'Ada', known_contact: true, subject: 'Lunch?', snippet: '', timestamp: '' },
    ] }, open)
    expect(toastSpy).not.toHaveBeenCalled()
  })
})
