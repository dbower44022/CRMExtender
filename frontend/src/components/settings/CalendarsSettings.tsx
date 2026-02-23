import { useState } from 'react'
import { toast } from 'sonner'
import {
  useCalendars,
  useFetchCalendars,
  useSaveCalendars,
} from '../../api/settings.ts'
import { RefreshCw } from 'lucide-react'

export function CalendarsSettings() {
  const { data: accounts, isLoading } = useCalendars()
  const fetchCalendars = useFetchCalendars()
  const saveCalendars = useSaveCalendars()

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
          No active Google accounts. Connect an account in the Accounts tab first.
        </p>
      </div>
    )
  }

  const handleLoad = (accountId: string, existingSelected: string[]) => {
    fetchCalendars.mutate(accountId, {
      onSuccess: (data) => {
        setLoadedCalendars((prev) => ({
          ...prev,
          [accountId]: data.calendars,
        }))
        setSelections((prev) => ({
          ...prev,
          [accountId]: new Set(existingSelected),
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

  const handleSave = (accountId: string) => {
    const selected = Array.from(selections[accountId] ?? [])
    saveCalendars.mutate(
      { accountId, calendar_ids: selected },
      {
        onSuccess: () => toast.success('Calendar selection saved'),
        onError: (err) => toast.error(err.message),
      },
    )
  }

  return (
    <div className="w-full">
      <h1 className="mb-6 text-lg font-semibold text-surface-800">
        Calendar Sync
      </h1>

      <div className="space-y-6">
        {accounts.map((account) => {
          const calendars = loadedCalendars[account.id]
          const selected = selections[account.id]

          return (
            <div
              key={account.id}
              className="rounded-lg border border-surface-200 bg-surface-50 p-4"
            >
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-surface-800">
                    {account.email_address}
                  </span>
                  {account.selected_calendars.length > 0 && (
                    <span className="ml-2 text-xs text-surface-500">
                      ({account.selected_calendars.length} selected)
                    </span>
                  )}
                </div>
                <button
                  onClick={() =>
                    handleLoad(account.id, account.selected_calendars)
                  }
                  disabled={fetchCalendars.isPending}
                  className="flex items-center gap-1.5 rounded-md border border-surface-300 bg-surface-0 px-3 py-1.5 text-xs font-medium text-surface-600 transition-colors hover:bg-surface-100 disabled:opacity-50"
                >
                  <RefreshCw
                    size={12}
                    className={
                      fetchCalendars.isPending ? 'animate-spin' : ''
                    }
                  />
                  Load Calendars
                </button>
              </div>

              {calendars && (
                <div className="space-y-1">
                  {calendars.map((cal) => (
                    <label
                      key={cal.id}
                      className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-surface-100"
                    >
                      <input
                        type="checkbox"
                        checked={selected?.has(cal.id) ?? false}
                        onChange={() => toggleCalendar(account.id, cal.id)}
                        className="rounded border-surface-300 text-primary-600 focus:ring-primary-200"
                      />
                      <span className="text-surface-700">{cal.summary}</span>
                    </label>
                  ))}

                  {calendars.length === 0 && (
                    <p className="text-xs text-surface-500">
                      No calendars found.
                    </p>
                  )}

                  <button
                    onClick={() => handleSave(account.id)}
                    disabled={saveCalendars.isPending}
                    className="mt-3 rounded-md bg-primary-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
                  >
                    {saveCalendars.isPending ? 'Saving...' : 'Save Selection'}
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
