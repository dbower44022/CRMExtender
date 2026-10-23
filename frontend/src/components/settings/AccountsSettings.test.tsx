import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { renderWithQuery, stubFetch } from '../../test/utils.tsx'
import { AccountsSettings } from './AccountsSettings.tsx'

const base = {
  provider: 'gmail', display_name: null, is_active: 1, initial_sync_done: 1, last_synced_at: '2026-10-09T13:00:00Z',
  created_at: '2026-10-01T00:00:00Z', updated_at: '', missing_scopes: [], token_present: true, auth_error: null,
  last_sync_error: null, last_sync_error_at: null,
  sync: { running: false, next_due_at: '2026-10-09T13:02:00Z', last_started: null, last_finished: null, scheduled: true },
}
const accounts = [
  { ...base, id: 'a1', email_address: 'one@x.com', needs_reauth: false, auth_status: 'ok' },
  { ...base, id: 'a2', email_address: 'two@x.com', needs_reauth: true, auth_status: 'needs_reauth', auth_error: 'refresh failed (invalid_grant)',
    sync: { ...base.sync, scheduled: false } },
  { ...base, id: 'a3', email_address: 'three@x.com', needs_reauth: false, auth_status: 'ok', last_sync_error: 'three@x.com: email sync failed (429)', last_sync_error_at: '2026-10-09T12:50:00Z' },
  { ...base, id: 'a4', email_address: 'four@x.com', needs_reauth: false, auth_status: 'disconnected', is_active: 0, sync: { ...base.sync, scheduled: false } },
]

describe('AccountsSettings (MAIL-38)', () => {
  it('shows each account state and offers Sync now only where it can run', async () => {
    stubFetch({
      '/api/v1/settings/accounts': accounts,
      '/api/v1/settings/profile': { id: 'u', name: 'A', email: 'a@x.com', role: 'admin', timezone: null, start_of_week: 'monday', date_format: null },
      '/api/v1/settings/system': { mail_sync_interval_seconds: '120', sync_enabled: 'true' },
      '/api/v1/reference-data': { google_oauth_configured: true },
    })
    renderWithQuery(<AccountsSettings />)
    await screen.findByText('one@x.com')
    expect(screen.getByText('Needs reconnect')).toBeInTheDocument()
    expect(screen.getByText('refresh failed (invalid_grant)')).toBeInTheDocument()
    expect(screen.getByText('Sync error')).toBeInTheDocument()
    expect(screen.getByText('Disconnected')).toBeInTheDocument()
    // Sync now: the healthy account and the one with a sync error, not the parked or disconnected ones
    expect(screen.getAllByText('Sync now').length).toBe(2)
    await screen.findByLabelText('Sync every')
    expect(screen.getByLabelText('Sync every')).toHaveValue(120)
  })

  it('requests a sync and disconnects keeping the mail', async () => {
    const calls = stubFetch({
      '/api/v1/settings/accounts/a1/sync': { status: 'requested', account_id: 'a1' },
      '/api/v1/settings/accounts/a1?mode=keep': { ok: true, deleted: false },
      '/api/v1/settings/accounts': [accounts[0]],
      '/api/v1/settings/profile': { id: 'u', name: 'A', email: 'a@x.com', role: 'user', timezone: null, start_of_week: 'monday', date_format: null },
      '/api/v1/reference-data': { google_oauth_configured: false },
    })
    renderWithQuery(<AccountsSettings />)
    await screen.findByText('one@x.com')
    expect(screen.queryByLabelText('Sync every')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Sync now'))
    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/settings/accounts/a1/sync') && c.init?.method === 'POST')).toBe(true))
    fireEvent.click(screen.getByText('Disconnect'))
    fireEvent.click(await screen.findByText('Keep mail as history'))
    await waitFor(() => {
      const del = calls.find((c) => c.init?.method === 'DELETE')
      expect(del?.url).toContain('/settings/accounts/a1?mode=keep')
    })
  })
})
