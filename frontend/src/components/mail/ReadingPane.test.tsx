import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { ReadingPane } from './ReadingPane.tsx'
import { renderWithQuery, stubFetch } from '../../test/utils.tsx'

const msg = (id: string, over: Record<string, unknown> = {}) => ({
  id, timestamp: '2026-10-01T12:00:00+00:00', direction: 'inbound', subject: 'Lunch?', snippet: `snip ${id}`,
  sender: { address: 'ada@example.com', name: 'Ada', contact_id: null, contact_name: null, is_me: false },
  participants: [{ address: 'me@x.com', name: null, role: 'to', contact_id: null, contact_name: null }],
  body_html: `<p>body ${id}</p>`, body_text: `body ${id}`, is_read: true, is_starred: false, is_archived: false,
  labels: [{ id: 'l1', name: 'INBOX', kind: 'inbox' }], attachments: [], header_message_id: null, provider_message_id: id,
  ...over,
})

const thread = {
  account_id: 'a', account_email: 'me@x.com', thread_id: 't1', subject: 'Lunch?', labels: ['INBOX'],
  message_count: 3, unread_count: 1, conversation: null,
  messages: [msg('m1'), msg('m2'), msg('m3', { is_read: false, attachments: [
    { id: 'att1', filename: 'deck.pdf', mime_type: 'application/pdf', size_bytes: 2048, content_id: null, is_inline: false },
  ] })],
}

describe('ReadingPane (MAIL-24/26/27)', () => {
  beforeEach(() => {
    vi.useRealTimers()
  })

  it('collapses read messages, expands unread ones, and lists attachments', async () => {
    stubFetch({ '/api/v1/settings/system': { mail_mark_read_dwell_ms: '0' }, '/api/v1/mail/threads/a/t1': thread })
    renderWithQuery(<ReadingPane accountId="a" threadId="t1" />)
    await screen.findByText('3 messages')
    // m1 and m2 collapsed to one line (snippet visible), m3 expanded (frame present)
    expect(screen.getByText('snip m1')).toBeInTheDocument()
    expect(screen.getByText('snip m2')).toBeInTheDocument()
    expect(screen.queryByText('snip m3')).not.toBeInTheDocument()
    expect(screen.getAllByTitle('Message').length).toBe(1)
    // attachment chip opens the attachment route
    const chip = screen.getByText('deck.pdf').closest('a')!
    expect(chip.getAttribute('href')).toBe('/api/v1/mail/attachments/att1')
    expect(screen.getByLabelText('Download deck.pdf').getAttribute('href')).toContain('download=1')
    // expand m1 by clicking its collapsed line
    fireEvent.click(screen.getByText('snip m1'))
    await waitFor(() => expect(screen.getAllByTitle('Message').length).toBe(2))
    // Expand all
    fireEvent.click(screen.getByText('Expand all'))
    await waitFor(() => expect(screen.getAllByTitle('Message').length).toBe(3))
  })

  it('marks unread messages read after the dwell', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = stubFetch({
      '/api/v1/settings/system': { mail_mark_read_dwell_ms: '50' },
      '/api/v1/mail/threads/a/t1': thread,
      '/api/v1/mail/actions': { id: 'q1', status: 'pending' },
    })
    renderWithQuery(<ReadingPane accountId="a" threadId="t1" />)
    await screen.findByText('3 messages')
    await vi.advanceTimersByTimeAsync(80)
    await waitFor(() => {
      const post = calls.find((c) => c.url.endsWith('/mail/actions') && c.init?.method === 'POST')
      expect(post).toBeTruthy()
      expect(JSON.parse(String(post!.init!.body))).toEqual({ action: 'mark_read', account_id: 'a', communication_ids: ['m3'] })
    })
    vi.useRealTimers()
  })

  it('shows the empty prompt without a thread', () => {
    stubFetch({})
    renderWithQuery(<ReadingPane accountId={null} threadId={null} />)
    expect(screen.getByText('Select a thread to read it.')).toBeInTheDocument()
  })
})
