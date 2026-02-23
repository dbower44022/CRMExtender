import { useState } from 'react'
import { toast } from 'sonner'
import {
  useCalendars,
  useFetchCalendars,
  useSaveCalendars,
  type CalendarEntry,
} from '../../api/settings.ts'
import { RefreshCw, Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react'

export function CalendarsSettings() {
  const { data: accounts, isLoading } = useCalendars()
  const fetchCalendars = useFetchCalendars()
  const saveCalendars = useSaveCalendars()

  const [addingForAccount, setAddingForAccount] = useState<string | null>(null)
  const [loadedCalendars, setLoadedCalendars] = useState<
    Record<string, Array<{ id: string; summary: string }>>
  >({})
  const [selections, setSelections] = useState<Record<string, Set<string>>>({})

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  if (!accounts || accounts.length === 0) {
    return (
      <div className="w-full">
        <h1 className="mb-6 text-lg font-semibold text-surface-800">
          Calendar Sync
        </h1>
        <p className="text-sm text-surface-500">
          No active Google accounts. Connect an account in the Accounts tab
          first.
        </p>
      </div>
    )
  }

  // Flatten all configured calendars across accounts
  const allCalendars: Array<{
    accountId: string
    accountName: string
    entry: CalendarEntry
  }> = []
  for (const account of accounts) {
    const name = account.display_name || account.email_address
    for (const entry of account.selected_calendars) {
      allCalendars.push({
        accountId: account.id,
        accountName: name,
        entry,
      })
    }
  }

  const handleRemove = (accountId: string, calendarId: string) => {
    const account = accounts.find((a) => a.id === accountId)
    if (!account) return
    const updated = account.selected_calendars.filter(
      (e) => e.id !== calendarId,
    )
    saveCalendars.mutate(
      { accountId, calendar_entries: updated },
      {
        onSuccess: () => toast.success('Calendar removed'),
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const handleLoad = (accountId: string) => {
    fetchCalendars.mutate(accountId, {
      onSuccess: (data) => {
        const account = accounts.find((a) => a.id === accountId)
        const existingIds = new Set(
          (account?.selected_calendars ?? []).map((e) => e.id),
        )
        setLoadedCalendars((prev) => ({
          ...prev,
          [accountId]: data.calendars,
        }))
        // Pre-check already-selected calendars
        setSelections((prev) => ({
          ...prev,
          [accountId]: existingIds,
        }))
      },
      onError: (err) => toast.error(err.message),
    })
  }

  const toggleCalendar = (accountId: string, calId: string) => {
    setSelections((prev) => {
      const current = new Set(prev[accountId] ?? [])
      if (current.has(calId)) current.delete(calId)
      else current.add(calId)
      return { ...prev, [accountId]: current }
    })
  }

  const handleSaveSelection = (accountId: string) => {
    const selected = selections[accountId] ?? new Set<string>()
    const available = loadedCalendars[accountId] ?? []
    const entries: CalendarEntry[] = available
      .filter((cal) => selected.has(cal.id))
      .map((cal) => ({ id: cal.id, summary: cal.summary }))

    saveCalendars.mutate(
      { accountId, calendar_entries: entries },
      {
        onSuccess: () => {
          toast.success('Calendar selection saved')
          setAddingForAccount(null)
          setLoadedCalendars((prev) => {
            const next = { ...prev }
            delete next[accountId]
            return next
          })
        },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const toggleAddPanel = (accountId: string) => {
    if (addingForAccount === accountId) {
      setAddingForAccount(null)
    } else {
      setAddingForAccount(accountId)
      if (!loadedCalendars[accountId]) {
        handleLoad(accountId)
      }
    }
  }

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-surface-800">
          Calendar Sync
        </h1>
      </div>

      {/* Configured calendars table */}
      {allCalendars.length > 0 ? (
        <div className="mb-6 overflow-x-auto rounded-lg border border-surface-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 bg-surface-50 text-left text-xs font-medium uppercase tracking-wider text-surface-500">
                <th className="px-4 py-2">Account</th>
                <th className="px-4 py-2">Calendar</th>
                <th className="px-4 py-2 w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {allCalendars.map((row) => (
                <tr
                  key={`${row.accountId}-${row.entry.id}`}
                  className="hover:bg-surface-50"
                >
                  <td className="px-4 py-2 text-surface-600">
                    {row.accountName}
                  </td>
                  <td className="px-4 py-2 font-medium text-surface-800">
                    {row.entry.summary}
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => handleRemove(row.accountId, row.entry.id)}
                      disabled={saveCalendars.isPending}
                      className="flex items-center gap-1 rounded px-2 py-0.5 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      <Trash2 size={12} />
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mb-6 text-sm text-surface-500">
          No calendars configured. Use the button below to add calendars from
          your Google accounts.
        </p>
      )}

      {/* Add Calendar section */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium text-surface-700">
          Add Calendars
        </h2>
        {accounts.map((account) => {
          const isOpen = addingForAccount === account.id
          const calendars = loadedCalendars[account.id]
          const selected = selections[account.id]
          const accountName =
            account.display_name || account.email_address

          return (
            <div
              key={account.id}
              className="rounded-lg border border-surface-200 bg-surface-50"
            >
              <button
                onClick={() => toggleAddPanel(account.id)}
                className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-medium text-surface-700 hover:bg-surface-100"
              >
                <div className="flex items-center gap-2">
                  <Plus size={14} className="text-surface-400" />
                  {accountName}
                </div>
                {isOpen ? (
                  <ChevronUp size={14} className="text-surface-400" />
                ) : (
                  <ChevronDown size={14} className="text-surface-400" />
                )}
              </button>

              {isOpen && (
                <div className="border-t border-surface-200 px-4 py-3">
                  {fetchCalendars.isPending && !calendars && (
                    <div className="flex items-center gap-2 text-sm text-surface-500">
                      <RefreshCw size={12} className="animate-spin" />
                      Loading calendars from Google...
                    </div>
                  )}

                  {calendars && calendars.length === 0 && (
                    <p className="text-xs text-surface-500">
                      No calendars found for this account.
                    </p>
                  )}

                  {calendars && calendars.length > 0 && (
                    <>
                      <div className="mb-3 space-y-1">
                        {calendars.map((cal) => (
                          <label
                            key={cal.id}
                            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-surface-100"
                          >
                            <input
                              type="checkbox"
                              checked={selected?.has(cal.id) ?? false}
                              onChange={() =>
                                toggleCalendar(account.id, cal.id)
                              }
                              className="rounded border-surface-300 text-primary-600 focus:ring-primary-200"
                            />
                            <span className="text-surface-700">
                              {cal.summary}
                            </span>
                          </label>
                        ))}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleSaveSelection(account.id)}
                          disabled={saveCalendars.isPending}
                          className="rounded-md bg-primary-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
                        >
                          {saveCalendars.isPending
                            ? 'Saving...'
                            : 'Save Selection'}
                        </button>
                        <button
                          onClick={() => handleLoad(account.id)}
                          disabled={fetchCalendars.isPending}
                          className="flex items-center gap-1.5 rounded-md border border-surface-300 bg-surface-0 px-3 py-1.5 text-xs font-medium text-surface-600 transition-colors hover:bg-surface-100 disabled:opacity-50"
                        >
                          <RefreshCw
                            size={12}
                            className={
                              fetchCalendars.isPending ? 'animate-spin' : ''
                            }
                          />
                          Refresh
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
