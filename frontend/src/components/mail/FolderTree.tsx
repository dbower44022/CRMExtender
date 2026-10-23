/** Folder tree: unified set on top, then one section per account (MAIL-22). */

import { Inbox, Star, Clock, Hourglass, FileText, Send, Archive, Trash2, ShieldAlert, Tag, RefreshCw, AlertTriangle } from 'lucide-react'
import type { MailAccountFolders, MailFolders } from '../../api/mail.ts'
import { useLiveStore } from '../../stores/live.ts'

const UNIFIED: { key: string; label: string; icon: typeof Inbox }[] = [
  { key: 'inbox', label: 'Inbox', icon: Inbox },
  { key: 'starred', label: 'Starred', icon: Star },
  { key: 'snoozed', label: 'Snoozed', icon: Clock },
  { key: 'awaiting', label: 'Awaiting reply', icon: Hourglass },
  { key: 'drafts', label: 'Drafts', icon: FileText },
  { key: 'sent', label: 'Sent', icon: Send },
]

const PER_ACCOUNT: { key: string; label: string; icon: typeof Inbox }[] = [
  { key: 'inbox', label: 'Inbox', icon: Inbox },
  { key: 'starred', label: 'Starred', icon: Star },
  { key: 'awaiting', label: 'Awaiting reply', icon: Hourglass },
  { key: 'sent', label: 'Sent', icon: Send },
  { key: 'drafts', label: 'Drafts', icon: FileText },
  { key: 'archive', label: 'Archive', icon: Archive },
  { key: 'spam', label: 'Spam', icon: ShieldAlert },
  { key: 'trash', label: 'Trash', icon: Trash2 },
]

interface Props {
  data: MailFolders | undefined
  loading: boolean
  activeAccountId: string
  activeFolder: string
  onSelect: (accountId: string, folder: string) => void
}

function Row({
  active, label, icon: Icon, unread, total, onClick, indent = 0,
}: {
  active: boolean
  label: string
  icon: typeof Inbox
  unread?: number
  total?: number
  onClick: () => void
  indent?: number
}) {
  return (
    <button
      onClick={onClick}
      title={total !== undefined ? `${total} message${total === 1 ? '' : 's'}` : label}
      className={`flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm ${
        active ? 'bg-primary-100 font-medium text-primary-800' : 'text-surface-700 hover:bg-surface-100'
      }`}
      style={{ paddingLeft: 8 + indent * 12 }}
    >
      <Icon size={15} className="shrink-0 opacity-70" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {unread ? (
        <span className="rounded-full bg-primary-600 px-1.5 text-[11px] font-semibold text-white">{unread}</span>
      ) : null}
    </button>
  )
}

function AccountSection({
  account, activeAccountId, activeFolder, onSelect,
}: {
  account: MailAccountFolders
  activeAccountId: string
  activeFolder: string
  onSelect: Props['onSelect']
}) {
  const userLabels = account.labels
    .filter((l) => l.kind === 'user')
    .sort((a, b) => a.name.localeCompare(b.name))
  const isActiveAccount = activeAccountId === account.id
  const liveSyncing = useLiveStore((s) => s.syncing[account.id])
  const syncing = liveSyncing ?? account.sync?.running
  const syncError = account.sync?.last_error
  return (
    <div className="mt-3">
      <div className="flex items-center gap-1 px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-surface-500">
        {account.color && <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: account.color }} aria-hidden="true" />}
        <span className="min-w-0 flex-1 truncate" title={account.email} style={account.color ? { color: account.color } : undefined}>
          {account.display_name || account.email}
        </span>
        {syncing && <RefreshCw size={11} className="animate-spin text-surface-400" />}
        {syncError && (
          <AlertTriangle size={11} className="text-amber-600" />
        )}
      </div>
      {!account.initial_sync_done && (
        <div className="px-2 pb-1 text-[11px] text-surface-500">First sync pending</div>
      )}
      {PER_ACCOUNT.map((f) => {
        const c = account.system[f.key]
        return (
          <Row
            key={f.key}
            active={isActiveAccount && activeFolder === f.key}
            label={f.label}
            icon={f.icon}
            unread={f.key === 'awaiting' ? c?.total : c?.unread}
            total={c?.total}
            onClick={() => onSelect(account.id, f.key)}
          />
        )
      })}
      {userLabels.map((l) => (
        <Row
          key={l.id}
          active={isActiveAccount && activeFolder === `label:${l.id}`}
          label={l.name}
          icon={Tag}
          unread={l.unread}
          total={l.total}
          indent={1}
          onClick={() => onSelect(account.id, `label:${l.id}`)}
        />
      ))}
    </div>
  )
}

function LiveStatus() {
  const connected = useLiveStore((s) => s.connected)
  const last = useLiveStore((s) => s.lastEvent)
  const when = last ? new Date(last.at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : null
  return (
    <div className="mt-3 flex items-center gap-1.5 px-2 text-[11px] text-surface-400" title={connected ? 'Updates arrive from the server as syncs finish' : 'Refreshing every 30 seconds'}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-surface-300'}`} />
      <span>{connected ? 'Live' : 'Polling'}</span>
      {when && <span>· last sync event {when}</span>}
    </div>
  )
}

export function FolderTree({ data, loading, activeAccountId, activeFolder, onSelect }: Props) {
  if (loading && !data) {
    return <div className="p-3 text-sm text-surface-500">Loading folders…</div>
  }
  if (!data || data.accounts.length === 0) {
    return (
      <div className="p-3 text-sm text-surface-500">
        No mail accounts yet. Connect one under Settings → Accounts.
      </div>
    )
  }
  const unifiedActive = activeAccountId === 'unified'
  return (
    <nav className="p-2">
      <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-surface-500">
        All accounts
      </div>
      {UNIFIED.map((f) => {
        const c = data.unified[f.key]
        return (
          <Row
            key={f.key}
            active={unifiedActive && activeFolder === f.key}
            label={f.label}
            icon={f.icon}
            unread={f.key === 'awaiting' ? c?.total : c?.unread}
            total={c?.total}
            onClick={() => onSelect('unified', f.key)}
          />
        )
      })}
      {data.accounts.map((a) => (
        <AccountSection
          key={a.id}
          account={a}
          activeAccountId={activeAccountId}
          activeFolder={activeFolder}
          onSelect={onSelect}
        />
      ))}
      <LiveStatus />
    </nav>
  )
}
