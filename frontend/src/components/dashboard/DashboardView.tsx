import { useState } from 'react'
import {
  Building2,
  Calendar,
  FolderKanban,
  MessageSquare,
  RefreshCw,
  User,
  Users,
} from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { getSyncStatus, triggerSync, useDashboard } from '../../api/dashboard.ts'
import { ApiError } from '../../api/client.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function DashboardView() {
  const { data, isLoading } = useDashboard(true)
  const queryClient = useQueryClient()
  const [syncing, setSyncing] = useState(false)

  const handleSync = async () => {
    setSyncing(true)
    try {
      try {
        await triggerSync()
        toast.info('Sync started')
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          toast.info('A sync is already running — watching it')
        } else {
          throw err
        }
      }
      // Poll until the background run completes, then summarize
      let status = await getSyncStatus()
      while (status.running) {
        await sleep(2000)
        status = await getSyncStatus()
      }
      if (status.error) {
        toast.error(`Sync failed: ${status.error}`)
      } else if (status.result) {
        const r = status.result
        toast.success(
          `Synced ${r.accounts} account(s): ${r.contacts} contacts, ` +
          `${r.emails_fetched} emails, ${r.triaged} triaged, ${r.summarized} summarized`,
        )
        if (r.errors.length) {
          toast.warning(`${r.errors.length} account error(s): ${r.errors[0]}`)
        }
      }
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
    } catch {
      toast.error('Could not start sync')
    } finally {
      setSyncing(false)
    }
  }

  const nav = (entityType: string, entityId: string) => {
    const store = useNavigationStore.getState()
    store.closeDashboard()
    store.setActiveEntityType(entityType)
    store.setPendingNavigation({ entityType, entityId })
  }

  if (isLoading || !data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-400">
        Loading dashboard…
      </div>
    )
  }

  const c = data.counts
  const tiles = [
    { label: 'Open Conversations', value: c.conversations_open, icon: MessageSquare },
    { label: 'Total Conversations', value: c.conversations_total, icon: MessageSquare },
    { label: 'Contacts', value: c.contacts, icon: User },
    { label: 'Companies', value: c.companies, icon: Building2 },
    { label: 'Projects', value: c.projects, icon: FolderKanban },
    { label: 'Events', value: c.events, icon: Calendar },
  ]

  return (
    <div className="h-full overflow-y-auto bg-surface-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-surface-900">Dashboard</h1>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-60"
          >
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing…' : 'Sync Now'}
          </button>
        </div>

        {/* Stat tiles */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {tiles.map(({ label, value, icon: Icon }) => (
            <div
              key={label}
              className="rounded-lg border border-surface-200 bg-white p-3"
            >
              <div className="mb-1 flex items-center gap-1.5 text-xs text-surface-500">
                <Icon size={12} />
                {label}
              </div>
              <div className="text-2xl font-semibold tabular-nums text-surface-900">
                {value.toLocaleString()}
              </div>
            </div>
          ))}
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Recent conversations */}
          <div className="rounded-lg border border-surface-200 bg-white lg:col-span-2">
            <div className="border-b border-surface-200 px-4 py-2.5 text-sm font-medium text-surface-700">
              Recent Conversations
            </div>
            {data.recent_conversations.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-surface-400">
                No conversations yet — run a sync to get started.
              </div>
            ) : (
              <ul className="divide-y divide-surface-100">
                {data.recent_conversations.map((conv) => (
                  <li key={conv.id}>
                    <button
                      onClick={() => nav('conversation', conv.id)}
                      className="flex w-full items-center gap-3 px-4 py-2 text-left transition-colors hover:bg-surface-50"
                    >
                      <MessageSquare size={14} className="shrink-0 text-surface-400" />
                      <span className="min-w-0 flex-1 truncate text-sm text-surface-800">
                        {conv.title || 'Untitled'}
                      </span>
                      <span className="shrink-0 text-xs text-surface-400">
                        {conv.communication_count} msg
                        {conv.communication_count === 1 ? '' : 's'}
                      </span>
                      <span className="w-24 shrink-0 text-right text-xs text-surface-400">
                        {formatTimestamp(conv.last_activity_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Top companies */}
          <RankedList
            title="Top Companies"
            icon={Building2}
            empty="No scored companies yet."
            items={data.top_companies.map((co) => ({
              id: co.id,
              primary: co.name,
              secondary: co.domain,
              score: co.score,
            }))}
            onOpen={(id) => nav('company', id)}
          />

          {/* Top contacts */}
          <RankedList
            title="Top Contacts"
            icon={Users}
            empty="No scored contacts yet."
            items={data.top_contacts.map((ct) => ({
              id: ct.id,
              primary: ct.name,
              secondary: ct.company_name || ct.email,
              score: ct.score,
            }))}
            onOpen={(id) => nav('contact', id)}
          />
        </div>
      </div>
    </div>
  )
}

interface RankedItem {
  id: string
  primary: string
  secondary: string | null
  score: number
}

function RankedList({
  title,
  icon: Icon,
  empty,
  items,
  onOpen,
}: {
  title: string
  icon: typeof Building2
  empty: string
  items: RankedItem[]
  onOpen: (id: string) => void
}) {
  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-2.5 text-sm font-medium text-surface-700">
        <Icon size={14} />
        {title}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-6 text-center text-sm text-surface-400">{empty}</div>
      ) : (
        <ul className="divide-y divide-surface-100">
          {items.map((item, i) => (
            <li key={item.id}>
              <button
                onClick={() => onOpen(item.id)}
                className="flex w-full items-center gap-3 px-4 py-2 text-left transition-colors hover:bg-surface-50"
              >
                <span className="w-4 shrink-0 text-xs tabular-nums text-surface-400">
                  {i + 1}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm text-surface-800">
                  {item.primary}
                </span>
                {item.secondary && (
                  <span className="max-w-[40%] shrink-0 truncate text-xs text-surface-400">
                    {item.secondary}
                  </span>
                )}
                <span className="w-10 shrink-0 text-right text-xs font-medium tabular-nums text-surface-600">
                  {Math.round(item.score)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
