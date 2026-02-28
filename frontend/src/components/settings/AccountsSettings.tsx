import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { useAccounts, useUpdateAccount, useToggleAccount, useReferenceData } from '../../api/settings.ts'

export function AccountsSettings() {
  const { data: accounts, isLoading } = useAccounts()
  const { data: refData } = useReferenceData()
  const updateAccount = useUpdateAccount()
  const toggleAccount = useToggleAccount()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  // Show success toast if redirected back from OAuth
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('connected') === '1') {
      toast.success('Google account connected successfully')
      const url = new URL(window.location.href)
      url.searchParams.delete('connected')
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
        onSuccess: () => {
          toast.success('Account updated')
          setEditingId(null)
        },
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

  const formatDate = (val: string | null | undefined) =>
    val ? val.slice(0, 10) : ''

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

      {(!accounts || accounts.length === 0) && (
        <p className="text-sm text-surface-500">No accounts connected.</p>
      )}

      {accounts && accounts.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-surface-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 bg-surface-50 text-left text-xs font-medium uppercase tracking-wider text-surface-500">
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Display Name</th>
                <th className="px-4 py-2">Provider</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Initial Sync</th>
                <th className="px-4 py-2">Last Synced</th>
                <th className="px-4 py-2">Connected</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {accounts.map((account) => (
                <tr key={account.id} className="hover:bg-surface-50">
                  <td className="px-4 py-2 font-medium text-surface-800">
                    {account.email_address}
                  </td>
                  <td className="px-4 py-2 text-surface-600">
                    {editingId === account.id ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={handleEditKeyDown}
                          placeholder="Display name"
                          autoFocus
                          className="w-40 rounded border border-surface-300 bg-surface-0 px-1.5 py-0.5 text-sm focus:border-primary-400 focus:outline-none"
                        />
                        <button
                          onClick={saveEdit}
                          className="rounded px-1.5 py-0.5 text-xs text-primary-600 hover:bg-primary-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="rounded px-1.5 py-0.5 text-xs text-surface-500 hover:bg-surface-100"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      account.display_name ?? ''
                    )}
                  </td>
                  <td className="px-4 py-2 text-surface-600 capitalize">
                    {account.provider}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        account.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {account.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-surface-600">
                    {account.initial_sync_done ? 'Done' : 'Pending'}
                  </td>
                  <td className="px-4 py-2 text-surface-600">
                    {account.last_synced_at ? formatDate(account.last_synced_at) : 'Never'}
                  </td>
                  <td className="px-4 py-2 text-surface-600">
                    {formatDate(account.created_at)}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      {editingId !== account.id && (
                        <button
                          onClick={() => startEdit(account)}
                          className="rounded px-2 py-0.5 text-xs text-surface-600 hover:bg-surface-100"
                        >
                          Edit
                        </button>
                      )}
                      <button
                        onClick={() =>
                          toggleAccount.mutate(account.id, {
                            onError: (err) => toast.error(err.message),
                          })
                        }
                        className={`rounded px-2 py-0.5 text-xs ${
                          account.is_active
                            ? 'text-red-600 hover:bg-red-50'
                            : 'text-green-600 hover:bg-green-50'
                        }`}
                      >
                        {account.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
