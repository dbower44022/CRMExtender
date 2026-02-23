import { useEffect, useState } from 'react'
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
      // Clean up the URL param without a full reload
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

  const googleConfigured = refData?.google_oauth_configured ?? false

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

      <div className="space-y-3">
        {accounts?.map((account) => (
          <div
            key={account.id}
            className="flex items-center justify-between rounded-lg border border-surface-200 bg-surface-50 px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-surface-800">
                  {account.email_address}
                </span>
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                    account.is_active
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {account.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              {editingId === account.id ? (
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Display name"
                    className="rounded-md border border-surface-300 bg-surface-0 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none"
                  />
                  <button
                    onClick={saveEdit}
                    className="rounded px-2 py-1 text-xs text-primary-600 hover:bg-primary-50"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="rounded px-2 py-1 text-xs text-surface-500 hover:bg-surface-100"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                account.display_name && (
                  <div className="mt-0.5 text-xs text-surface-500">
                    {account.display_name}
                  </div>
                )
              )}
            </div>

            <div className="flex items-center gap-2">
              {editingId !== account.id && (
                <button
                  onClick={() => startEdit(account)}
                  className="rounded px-2 py-1 text-xs text-surface-600 hover:bg-surface-100"
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
                className={`rounded px-2 py-1 text-xs ${
                  account.is_active
                    ? 'text-red-600 hover:bg-red-50'
                    : 'text-green-600 hover:bg-green-50'
                }`}
              >
                {account.is_active ? 'Deactivate' : 'Activate'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
