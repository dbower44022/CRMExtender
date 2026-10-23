import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { renderWithQuery, stubFetch } from '../../test/utils.tsx'
import { useComposeStore } from '../../stores/compose.ts'
import { ComposeDock } from './ComposeDock.tsx'
import { InlineReply } from './InlineReply.tsx'

// The rich text editor needs browser layout jsdom lacks; a textarea stands in.
vi.mock('../editor/RichTextEditor.tsx', () => ({
  RichTextEditor: ({ onChange, content }: { onChange?: (j: string, h: string, t: string) => void; content?: string | null }) => (
    <textarea aria-label="Body" defaultValue={content ?? ''} onChange={(e) => onChange?.('{}', `<p>${e.target.value}</p>`, e.target.value)} />
  ),
}))

const accounts = [{ id: 'acct1', email_address: 'me@x.com', display_name: 'Me', is_active: 1 }]
const signatures = [{ id: 's1', name: 'Work', body_json: '{}', body_html: '<p>Doug Bower</p>', provider_account_id: null, is_default: 1, created_at: '', updated_at: '' }]
const settings = { mail_undo_send_seconds: '10', mail_mark_read_dwell_ms: '0' }
const ctx = {
  to_addresses: [{ email: 'ada@example.com', name: 'Ada' }], cc_addresses: [], subject: 'Re: Lunch?', quoted_html: '<p>old</p>',
  in_reply_to: '<m1>', references: null, thread_id: 't1', conversation_id: null, default_account_id: 'acct1', reply_to_communication_id: 'm1',
}
const draft = {
  id: 'd1', from_account_id: 'acct1', to_addresses: [{ email: 'bob@test.com', name: 'Bob' }], cc_addresses: [], bcc_addresses: [],
  subject: 'Hello Bob', body_json: '{}', body_html: '<p>Hi</p>', body_text: 'Hi', source_type: 'manual', status: 'draft', signature_id: null,
  reply_to_communication_id: null, forward_of_communication_id: null, conversation_id: null, created_at: '', updated_at: '',
}

describe('Composer (MAIL-33/34/35)', () => {
  beforeEach(() => {
    vi.useRealTimers()
    useComposeStore.setState({ composers: [], pendingSends: [] })
  })

  it('opens an inline reply addressed from the compose context with the signature shown (MAIL-T16)', async () => {
    stubFetch({
      '/api/v1/settings/accounts': accounts, '/api/v1/settings/system': settings, '/api/v1/signatures': signatures,
      '/api/v1/outbound-emails/compose-context': ctx, '/api/v1/search': [],
    })
    renderWithQuery(<InlineReply threadKey="acct1:t1" lastMessageId="m1" />)
    fireEvent.click(screen.getByText('Reply all'))
    expect(useComposeStore.getState().composers[0]).toMatchObject({ mode: 'reply_all', placement: 'inline', context: { communicationId: 'm1', threadKey: 'acct1:t1' } })
    await screen.findByTestId('inline-reply')
    await waitFor(() => expect(screen.getByLabelText('Subject')).toHaveValue('Re: Lunch?'))
    expect(screen.getByText(/ada@example.com|Ada/)).toBeInTheDocument()
    await screen.findByText(/Signature · Work/)
    expect(screen.getByText('Doug Bower')).toBeInTheDocument()
    // the quoted text is folded until asked for
    expect(screen.queryByText('old')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Quoted text'))
    expect(screen.getByText('old')).toBeInTheDocument()
  })

  it('holds a sent message in the undo window and reopens it on Undo (MAIL-T17)', async () => {
    const sendAt = new Date(Date.now() + 10_000).toISOString()
    const calls = stubFetch({
      '/api/v1/settings/accounts': accounts, '/api/v1/settings/system': settings, '/api/v1/signatures': [], '/api/v1/search': [],
      '/api/v1/outbound-emails/d1/send': { queue_id: 'd1', status: 'queued', scheduled_send_at: sendAt },
      '/api/v1/outbound-emails/d1/undo': { ok: true, status: 'draft' },
      '/api/v1/outbound-emails/d1/attachments': [],
      '/api/v1/outbound-emails/d1': (_u: string, init?: RequestInit) => (init?.method === 'PATCH' ? { ...draft } : draft),
    })
    renderWithQuery(<ComposeDock />)
    useComposeStore.getState().resumeDraft(draft as never)
    await screen.findByTestId('composer-open')
    expect(screen.getByLabelText('Subject')).toHaveValue('Hello Bob')
    fireEvent.click(screen.getByTitle('Send (Ctrl+Enter)'))
    // the composer closes and the undo bar appears
    await screen.findByText(/Sending in \d+s/)
    expect(screen.queryByTestId('composer-open')).not.toBeInTheDocument()
    const send = calls.find((c) => c.url.endsWith('/outbound-emails/d1/send'))!
    expect(JSON.parse(String(send.init?.body))).toEqual({ undo: true })
    fireEvent.click(screen.getByText('Undo'))
    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/outbound-emails/d1/undo'))).toBe(true))
    await screen.findByTestId('composer-open')
    expect(screen.getByLabelText('Subject')).toHaveValue('Hello Bob')
    expect(useComposeStore.getState().pendingSends).toEqual([])
  })

  it('minimizes a docked composer and allows at most three', async () => {
    stubFetch({ '/api/v1/settings/accounts': accounts, '/api/v1/settings/system': settings, '/api/v1/signatures': [], '/api/v1/search': [] })
    renderWithQuery(<ComposeDock />)
    const s = useComposeStore.getState()
    expect(s.openCompose('new')).not.toBeNull()
    expect(s.openCompose('new')).not.toBeNull()
    expect(s.openCompose('new')).not.toBeNull()
    expect(s.openCompose('new')).toBeNull()
    await waitFor(() => expect(screen.getAllByTestId('composer-open').length).toBe(3))
    fireEvent.click(screen.getAllByLabelText('Minimize composer')[0])
    expect(screen.getAllByTestId('composer-open').length).toBe(2)
    expect(screen.getByTestId('composer-minimized')).toBeInTheDocument()
    fireEvent.click(screen.getAllByLabelText('Close composer')[0])
    expect(useComposeStore.getState().composers.length).toBe(2)
  })
})
