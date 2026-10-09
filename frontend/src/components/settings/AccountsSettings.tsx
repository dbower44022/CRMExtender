/** Settings → Accounts (Mail Client MAIL-38).
 *
 * One row per connected mailbox: its state (active, needs reconnect, sync
 * error, disconnected), its sync (last run, next due, Sync now), and the
 * actions — Reconnect, Edit, Deactivate, Disconnect (keep the mail as
 * history, or delete it). Administrators also set the sync interval here.
 */

import { Fragment, useState, useEffect } from 'react'
import { AlertTriangle, Loader2, RefreshCw, Unplug } from 'lucide-react'
import { toast } from 'sonner'
import {
  useAccounts, useDisconnectAccount, useProfile, useReferenceData, useSetAccountNotifications, useSyncAccountNow,
  useSystemSettings, useToggleAccount, useUpdateAccount, useUpdateSystemSettings,
} from '../../api/settings.ts'

type Account = NonNullable<ReturnType<typeof useAccounts>['data']>[number]

function fmtWhen(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso.slice(0, 10) : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

function fmtDue(iso: string | null | undefined): string {
  if (!iso) return ''
  const ms = new Date(iso).getTime() - Date.now()
  if (Number.isNaN(ms)) return ''
  if (ms <= 0) return 'due now'
  const s = Math.round(ms / 1000)
  return s < 90 ? `in ${s}s` : `in ${Math.round(s / 60)} min`
}

function SyncInterval() {
  const { data: settings } = useSystemSettings()
  const update = useUpdateSystemSettings()
  const [value, setValue] = useState<string | null>(null)
  if (!settings) return null
  const current = value ?? settings.mail_sync_interval_seconds ?? '120'
  const dirty = current !== (settings.mail_sync_interval_seconds ?? '120')
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-surface-200 bg-surface-50 px-3 py-2 text-sm">
      <label htmlFor="sync-interval" className="text-surface-700">Sync every</label>
      <input
        id="sync-interval"
        type="number"
        min={60}
        step={30}
        value={current}
        onChange={(e) => setValue(e.target.value)}
        className="w-24 rounded border border-surface-300 bg-surface-0 px-2 py-0.5 text-sm"
      />
      <span className="text-surface-500">seconds (minimum 60) · timed syncs {settings.sync_enabled === 'false' ? 'are off' : 'are on'} under System</span>
      {dirty && (
        <button
          type="button"
          onClick={() => update.mutate({ mail_sync_interval_seconds: current }, {
            onSuccess: () => { setValue(null); toast.success('Sync interval saved') },
            onError: (err) => toast.error(err.message),
          })}
          className="rounded bg-primary-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-primary-700"
        >
          Save
        </button>
      )}
    </div>
  )
}

function DisconnectPanel({ account, onDone }: { account: Account; onDone: () => void }) {
  const disconnect = useDisconnectAccount()
  const run = (mode: 'keep' | 'delete') =>
    disconnect.mutate({ accountId: account.id, mode }, {
      onSuccess: (r) => {
        toast.success(mode === 'keep'
          ? `${account.email_address} disconnected; its mail stays as history`
          : `${account.email_address} removed with ${r.communications ?? 0} messages`)
        onDone()
      },
      onError: (err) => toast.error(err.message),
    })
  return (
    <tr className="bg-amber-50">
      <td colSpan={6} className="px-4 py-3 text-sm text-surface-800">
        <div className="font-medium">Disconnect {account.email_address}?</div>
        <p className="mt-0.5 text-xs text-surface-600">
          Syncing stops and the saved sign-in is removed either way. Choose what happens to the mail already here.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" disabled={disconnect.isPending} onClick={() => run('keep')}
            className="rounded border border-surface-300 bg-white px-3 py-1 text-xs font-medium text-surface-800 hover:bg-surface-50 disabled:opacity-50">
            Keep mail as history
          </button>
          <button type="button" disabled={disconnect.isPending} onClick={() => run('delete')}
            className="rounded bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50">
            Delete the account and its mail
          </button>
          <button type="button" onClick={onDone} className="px-2 py-1 text-xs text-surface-500 hover:text-surface-800">Cancel</button>
        </div>
      </td>
    </tr>
  )
}

export function AccountsSettings() {
  const { data: accounts, isLoading } = useAccounts()
  const { data: refData } = useReferenceData()
  const { data: profile } = useProfile()
  const updateAccount = useUpdateAccount()
  const toggleAccount = useToggleAccount()
  const syncNow = useSyncAccountNow()
  const setNotifications = useSetAccountNotifications()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null)

  // Show success message if redirected back from OAuth
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const connected = params.get('connected') === '1'
    const reconnected = params.get('reconnected') === '1'
    if (connected || reconnected) {
      toast.success(
        reconnected
          ? 'Google account reconnected with the current permissions'
          : 'Google account connected successfully',
      )
      const url = new URL(window.location.href)
      url.searchParams.delete('connected')
      url.searchParams.delete('reconnected')
      window.history.replaceState({}, '', url.pathname + url.hash)
    }
  }, [])

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  const startEdit = (account: { id: string; display_name: string | null }) => {
    setEditingId(account.id)
    setEditName(account.display_name ?? '')
  }

  const saveEdit = () => {
    if (!editingId) return
    updateAccount.mutate(
      { accountId: editingId, display_name: editName },
      {
        onSuccess: () => { toast.success('Account updated'); setEditingId(null) },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const cancelEdit = () => setEditingId(null)

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') saveEdit()
    else if (e.key === 'Escape') cancelEdit()
  }

  const googleConfigured = refData?.google_oauth_configured ?? false
  const isAdmin = profile?.role === 'admin'

  const reconnectTitle = (a: Account) =>
    a.auth_status === 'needs_reauth'
      ? `The saved sign-in stopped working${a.auth_error ? ` (${a.auth_error})` : ''}. Sign in again as ${a.email_address}.`
      : a.needs_reauth
        ? `Missing permission: ${a.missing_scopes.join(', ')}. Sign in again as ${a.email_address} to grant it.`
        : `Sign in again as ${a.email_address}`

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-surface-800">
          Connected Accounts
        </h1>

        {googleConfigured && (
          <a
            href="/settings/accounts/connect"
            className="inline-flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
            Connect Google Account
          </a>
        )}
      </div>

      {!googleConfigured && (
        <p className="mb-4 rounded-md border border-surface-200 bg-surface-50 px-3 py-2 text-sm text-surface-600">
          Google OAuth is not configured. Use the CLI to set up <code className="rounded bg-surface-100 px-1 text-xs">client_secret.json</code> first.
        </p>
      )}

      {isAdmin && <SyncInterval />}

      {(!accounts || accounts.length === 0) && (
        <p className="text-sm text-surface-500">No accounts connected.</p>
      )}

      {accounts && accounts.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-surface-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 bg-surface-50 text-left text-xs font-medium uppercase tracking-wider text-surface-500">
                <th className="px-4 py-2">Account</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Sync</th>
                <th className="px-4 py-2">Notify</th>
                <th className="px-4 py-2">Connected</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {accounts.map((account) => {
                const parked = account.auth_status === 'needs_reauth'
                const disconnected = account.auth_status === 'disconnected'
                const canSync = account.is_active === 1 && !parked && !disconnected
                return (
                  <Fragment key={account.id}>
                  <tr className="hover:bg-surface-50 align-top">
                    <td className="px-4 py-2">
                      <div className="font-medium text-surface-800">{account.email_address}</div>
                      {editingId === account.id ? (
                        <div className="mt-1 flex items-center gap-1.5">
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            onKeyDown={handleEditKeyDown}
                            placeholder="Display name"
                            aria-label="Display name"
                            autoFocus
                            className="w-40 rounded border border-surface-300 bg-surface-0 px-1.5 py-0.5 text-sm focus:border-primary-400 focus:outline-none"
                          />
                          <button onClick={saveEdit} className="rounded px-1.5 py-0.5 text-xs text-primary-600 hover:bg-primary-50">Save</button>
                          <button onClick={cancelEdit} className="rounded px-1.5 py-0.5 text-xs text-surface-500 hover:bg-surface-100">Cancel</button>
                        </div>
                      ) : (
                        <div className="text-xs text-surface-500">
                          {account.display_name ? `${account.display_name} · ` : ''}<span className="capitalize">{account.provider}</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap items-center gap-1">
                        {disconnected ? (
                          <span className="inline-block rounded-full bg-surface-200 px-2 py-0.5 text-xs font-medium text-surface-700">Disconnected</span>
                        ) : (
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${account.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                            {account.is_active ? 'Active' : 'Inactive'}
                          </span>
                        )}
                        {account.needs_reauth && !disconnected && (
                          <span
                            className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                            title={reconnectTitle(account)}
                          >
                            Needs reconnect
                          </span>
                        )}
                        {account.last_sync_error && !parked && (
                          <span
                            className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800"
                            title={`${account.last_sync_error} (${fmtWhen(account.last_sync_error_at)})`}
                          >
                            <AlertTriangle size={11} /> Sync error
                          </span>
                        )}
                      </div>
                      {parked && account.auth_error && (
                        <div className="mt-1 max-w-xs truncate text-xs text-amber-800" title={account.auth_error}>{account.auth_error}</div>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-surface-600">
                      {account.sync.running ? (
                        <span className="inline-flex items-center gap-1 text-primary-700"><Loader2 size={12} className="animate-spin" /> Syncing…</span>
                      ) : (
                        <>
                          <div>{account.last_synced_at ? `Last ${fmtWhen(account.last_synced_at)}` : 'Never synced'}</div>
                          {canSync && account.sync.scheduled && account.sync.next_due_at && <div className="text-surface-400">Next {fmtDue(account.sync.next_due_at)}</div>}
                          {!account.initial_sync_done && <div className="text-surface-400">First sync pending</div>}
                        </>
                      )}
                      {canSync && (
                        <button
                          type="button"
                          disabled={account.sync.running || syncNow.isPending}
                          onClick={() => syncNow.mutate(account.id, {
                            onSuccess: () => toast.success(`Sync requested for ${account.email_address}`),
                            onError: (err) => toast.error(err.message),
                          })}
                          className="mt-1 inline-flex items-center gap-1 rounded border border-surface-200 px-2 py-0.5 text-xs text-surface-700 hover:bg-surface-100 disabled:opacity-50"
                        >
                          <RefreshCw size={11} /> Sync now
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <select
                        aria-label={`New-mail pop-ups for ${account.email_address}`}
                        value={account.notifications ?? 'known_contacts'}
                        disabled={disconnected}
                        onChange={(e) => setNotifications.mutate(
                          { accountId: account.id, mode: e.target.value as 'all' | 'known_contacts' | 'none' },
                          { onError: (err) => toast.error(err.message) },
                        )}
                        className="rounded border border-surface-200 bg-surface-0 px-1.5 py-0.5 text-xs text-surface-700 disabled:opacity-50"
                        title="Pop-up for new inbox mail"
                      >
                        <option value="all">All inbox mail</option>
                        <option value="known_contacts">Known contacts only</option>
                        <option value="none">None</option>
                      </select>
                    </td>
                    <td className="px-4 py-2 text-xs text-surface-600">{fmtWhen(account.created_at)}</td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        {googleConfigured && account.provider === 'gmail' && (
                          <a
                            href="/settings/accounts/connect"
                            title={reconnectTitle(account)}
                            className={`rounded px-2 py-0.5 text-xs ${account.needs_reauth || disconnected ? 'bg-amber-50 text-amber-800 hover:bg-amber-100' : 'text-surface-600 hover:bg-surface-100'}`}
                          >
                            Reconnect
                          </a>
                        )}
                        {editingId !== account.id && (
                          <button onClick={() => startEdit(account)} className="rounded px-2 py-0.5 text-xs text-surface-600 hover:bg-surface-100">
                            Edit
                          </button>
                        )}
                        {!disconnected && (
                          <button
                            onClick={() => toggleAccount.mutate(account.id, { onError: (err) => toast.error(err.message) })}
                            className={`rounded px-2 py-0.5 text-xs ${account.is_active ? 'text-red-600 hover:bg-red-50' : 'text-green-600 hover:bg-green-50'}`}
                          >
                            {account.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        )}
                        <button
                          onClick={() => setDisconnectingId(disconnectingId === account.id ? null : account.id)}
                          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs text-surface-600 hover:bg-surface-100"
                          title={disconnected ? 'Delete this account and its mail' : 'Disconnect this account'}
                        >
                          <Unplug size={11} /> {disconnected ? 'Remove' : 'Disconnect'}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {disconnectingId === account.id && (
                    <DisconnectPanel account={account} onDone={() => setDisconnectingId(null)} />
                  )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
