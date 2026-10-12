/** The Mail surface (Mail Client PRD §2.2–2.3; MAIL-21 route, MAIL-22 folder tree,
 * MAIL-23 thread list, MAIL-24 reading pane).
 *
 * Three panes inside the content area: folder tree (unified set + one
 * section per account), the virtualized thread list for the selected
 * folder with a selection model, and the reading pane.
 */

import { useEffect, useRef, useState } from 'react'
import { Group, Panel, Separator, useDefaultLayout } from 'react-resizable-panels'
import { toast } from 'sonner'
import { useComposeStore } from '../../stores/compose.ts'
import { useMailShortcuts } from '../../hooks/useMailShortcuts.ts'
import { ShortcutSheet } from './ShortcutSheet.tsx'
import { SnoozePicker } from './SnoozePicker.tsx'
import { describeReturn } from '../../lib/snoozeTimes.ts'
import { SearchBox } from './SearchBox.tsx'
import { loadSavedSearches, storeSavedSearches, type SavedSearch } from '../../lib/mailSearchUi.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { threadKey, threadTargets, useInfiniteThreads, useMailAction, useMailFolders, useThread, type ThreadSummary } from '../../api/mail.ts'
import { ActionBar } from './ActionBar.tsx'
import { FolderTree } from './FolderTree.tsx'
import { ThreadList } from './ThreadList.tsx'
import { ReadingPane } from './ReadingPane.tsx'
import { LocalDrafts } from './LocalDrafts.tsx'

export function MailView() {
  const accountId = useNavigationStore((s) => s.mailAccountId)
  const folder = useNavigationStore((s) => s.mailFolder)
  const threadId = useNavigationStore((s) => s.mailThreadId)
  const setMailFolder = useNavigationStore((s) => s.setMailFolder)
  const setMailThread = useNavigationStore((s) => s.setMailThread)

  const folders = useMailFolders()
  // Search (MAIL-31): a query narrows the current folder; it clears on folder change.
  const [search, setSearch] = useState<{ key: string; q: string }>({ key: `${accountId}|${folder}`, q: '' })
  const searchQ = search.key === `${accountId}|${folder}` ? search.q : ''
  const setSearchQ = (q: string) => setSearch({ key: `${accountId}|${folder}`, q })
  const searchRef = useRef<HTMLInputElement>(null)
  const [saved, setSaved] = useState<SavedSearch[]>(() => loadSavedSearches())
  const saveSearch = (entry: SavedSearch) => {
    const next = [...saved.filter((x) => x.name !== entry.name), entry]
    setSaved(next); storeSavedSearches(next)
  }
  const removeSaved = (name: string) => {
    const next = saved.filter((x) => x.name !== name)
    setSaved(next); storeSavedSearches(next)
  }
  const threads = useInfiniteThreads(accountId, folder, searchQ)
  const items = threads.data?.pages.flatMap((p) => p.items) ?? []
  const total = threads.data?.pages[0]?.total ?? 0

  // Selection and focus are keyed by folder: a folder change starts empty
  // without a reset effect (React Compiler rule: no setState in effects).
  const folderKey = `${accountId}|${folder}`
  const [sel, setSel] = useState<{ key: string; focused: string | null; selected: Set<string> }>(
    { key: folderKey, focused: null, selected: new Set() },
  )
  const current = sel.key === folderKey ? sel : { key: folderKey, focused: null, selected: new Set<string>() }
  const focusedKey = current.focused
  const selectedKeys = current.selected
  const setFocusedKey = (focused: string | null) =>
    setSel((prev) => ({ key: folderKey, focused, selected: prev.key === folderKey ? prev.selected : new Set<string>() }))
  const setSelectedKeys = (update: (prev: Set<string>) => Set<string>) =>
    setSel((prev) => {
      const base = prev.key === folderKey ? prev : { key: folderKey, focused: null, selected: new Set<string>() }
      return { ...base, selected: update(base.selected) }
    })

  // A deep link names an account that is not visible: fall back to unified.
  useEffect(() => {
    if (!folders.data) return
    if (accountId !== 'unified' && !folders.data.accounts.some((a) => a.id === accountId)) {
      setMailFolder('unified', 'inbox')
    }
  }, [folders.data, accountId, setMailFolder])

  // The open thread's account: a thread id is only unique within an account.
  const open = threadId ? items.find((t) => t.thread_id === threadId) ?? null : null
  const openKey = open ? threadKey(open) : null
  const openAccountId = open?.account_id ?? (accountId !== 'unified' ? accountId : null)

  // Targets for the action bar: the selection when any, else the open thread.
  const openThread = useThread(openAccountId, threadId)
  const targets = selectedKeys.size > 0
    ? items.filter((t) => selectedKeys.has(threadKey(t)))
    : open ? [open] : []
  const clearSelection = () => setSelectedKeys(() => new Set<string>())

  // Keyboard model (MAIL-30)
  const act = useMailAction()
  const openCompose = useComposeStore((s) => s.openCompose)
  const [sheetOpen, setSheetOpen] = useState(false)
  // Snooze picker (MAIL-28): holds the threads it will apply to.
  const [snoozeFor, setSnoozeFor] = useState<ThreadSummary[] | null>(null)
  const keys = items.map(threadKey)
  const focusedIndex = focusedKey ? keys.indexOf(focusedKey) : -1
  const shortcutTargets = selectedKeys.size > 0
    ? items.filter((t) => selectedKeys.has(threadKey(t)))
    : focusedIndex >= 0 ? [items[focusedIndex]] : open ? [open] : []
  useMailShortcuts(true, {
    moveFocus: (delta) => {
      if (items.length === 0) return
      const base = focusedIndex < 0 ? (delta > 0 ? -1 : 0) : focusedIndex
      const next = Math.min(items.length - 1, Math.max(0, base + delta))
      setFocusedKey(keys[next])
    },
    openFocused: () => { if (focusedIndex >= 0) onOpen(items[focusedIndex]) },
    toggleSelectFocused: () => { if (focusedKey) onToggleSelect(focusedKey) },
    escape: () => {
      if (snoozeFor) setSnoozeFor(null)
      else if (sheetOpen) setSheetOpen(false)
      else if (threadId) setMailThread(null)
      else if (selectedKeys.size > 0) clearSelection()
    },
    act: (action) => {
      if (shortcutTargets.length === 0) return
      const starred = shortcutTargets.some((t) => t.starred)
      const kind = action === 'star' && starred ? 'unstar' : action
      act.mutateAsync({ action: kind, threads: shortcutTargets.flatMap(threadTargets) })
        .then(() => {
          if (selectedKeys.size > 0) clearSelection()
          // Archive/trash/spam remove the thread from most folders: advance focus so j/k keep flowing.
          if ((action === 'archive' || action === 'trash' || action === 'spam') && focusedIndex >= 0) {
            const nextKey = keys[focusedIndex + 1] ?? keys[focusedIndex - 1] ?? null
            setFocusedKey(nextKey)
            if (threadId && shortcutTargets.some((t) => t.thread_id === threadId)) setMailThread(null)
          }
        })
        .catch((err) => toast.error(err instanceof Error ? err.message : String(err)))
    },
    reply: (mode) => {
      const t = openThread.data
      if (!t || t.messages.length === 0) { toast.info('Open a thread first'); return }
      const id = openCompose(mode, { communicationId: t.messages[t.messages.length - 1].id, threadKey: `${t.account_id}:${t.thread_id}` }, 'inline')
      if (id === null) toast.info('Close a composer first (three are open)')
    },
    compose: () => { if (openCompose('new') === null) toast.info('Close a composer first (three are open)') },
    snooze: () => { if (shortcutTargets.length > 0) setSnoozeFor(shortcutTargets); else toast.info('Focus or select a thread first') },
    goFolder: (f) => setMailFolder(accountId, f),
    goAccount: (n) => {
      if (n === 0) { setMailFolder('unified', 'inbox'); return }
      const acct = folders.data?.accounts[n - 1]
      if (acct) setMailFolder(acct.id, 'inbox')
    },
    focusSearch: () => searchRef.current?.focus(),
    toggleSheet: () => setSheetOpen((v) => !v),
  })

  const onOpen = (t: ThreadSummary) => {
    setFocusedKey(threadKey(t))
    setMailThread(t.thread_id)
  }

  // Nudge (MAIL-47): open the thread and start a reply-all to the owner's last
  // message, which the reply context addresses to its original recipients.
  const onNudge = (t: ThreadSummary) => {
    if (!t.latest_message_id) { toast.info('Open the thread and reply from there'); return }
    setFocusedKey(threadKey(t))
    setMailThread(t.thread_id)
    const id = openCompose('reply_all', { communicationId: t.latest_message_id, threadKey: threadKey(t) }, 'inline')
    if (id === null) toast.info('Close a composer first (three are open)')
  }

  // Apply a chosen return time to the picker's threads; they leave the list like an archive.
  const onSnoozePick = (returnAt: string) => {
    const list = snoozeFor ?? []
    setSnoozeFor(null)
    if (list.length === 0) return
    act.mutateAsync({ action: 'snooze', payload: { return_at: returnAt }, threads: list.flatMap(threadTargets) })
      .then(() => {
        toast.success(`Snoozed until ${describeReturn(returnAt)}${list.length > 1 ? ` · ${list.length} threads` : ''}`)
        clearSelection()
        if (focusedIndex >= 0 && list.some((t) => threadKey(t) === focusedKey)) {
          setFocusedKey(keys[focusedIndex + 1] ?? keys[focusedIndex - 1] ?? null)
        }
        if (threadId && list.some((t) => t.thread_id === threadId)) setMailThread(null)
      })
      .catch((err) => toast.error(`Snooze failed: ${err instanceof Error ? err.message : String(err)}`))
  }

  const onToggleSelect = (key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const onRangeSelect = (fromKey: string, toKey: string) => {
    const keys = items.map(threadKey)
    const a = keys.indexOf(fromKey)
    const b = keys.indexOf(toKey)
    if (a < 0 || b < 0) return
    const [lo, hi] = a < b ? [a, b] : [b, a]
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      for (let i = lo; i <= hi; i++) next.add(keys[i])
      return next
    })
  }

  const onSelectAll = () => {
    setSelectedKeys((prev) => (prev.size === items.length ? new Set() : new Set(items.map(threadKey))))
  }

  const onLoadMore = () => {
    if (threads.hasNextPage && !threads.isFetchingNextPage) threads.fetchNextPage()
  }

  // The list / reading-pane split is draggable and remembered per browser.
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({ storage: localStorage, id: 'crm-mail-layout' })

  return (
    <div className="flex h-full min-h-0 overflow-hidden bg-surface-0">
      <aside className="w-56 shrink-0 overflow-y-auto border-r border-surface-200 bg-surface-50">
        <FolderTree
          data={folders.data}
          loading={folders.isLoading}
          activeAccountId={accountId}
          activeFolder={folder}
          onSelect={(acct, f) => setMailFolder(acct, f)}
        />
      </aside>
      <Group orientation="horizontal" id="crm-mail" className="min-w-0 flex-1" defaultLayout={defaultLayout} onLayoutChanged={onLayoutChanged}>
      <Panel id="mail-list" defaultSize="38%" minSize="22%" maxSize="75%">
      <section className="relative flex h-full flex-col overflow-hidden">
        <SearchBox ref={searchRef} value={searchQ} onSearch={setSearchQ} saved={saved} onSaveSearch={saveSearch} onRemoveSaved={removeSaved} />
        <ActionBar targets={targets} onDone={clearSelection} onSnooze={() => setSnoozeFor(targets)} onNudge={onNudge} />
        {folder === 'drafts' && <LocalDrafts />}
        <ThreadList
          items={items}
          total={total}
          loading={threads.isLoading}
          loadingMore={threads.isFetchingNextPage}
          hasMore={!!threads.hasNextPage}
          error={threads.error ? String(threads.error) : null}
          unified={accountId === 'unified'}
          focusedKey={focusedKey}
          openKey={openKey}
          selectedKeys={selectedKeys}
          onFocus={setFocusedKey}
          onOpen={onOpen}
          onToggleSelect={onToggleSelect}
          onRangeSelect={onRangeSelect}
          onSelectAll={onSelectAll}
          onLoadMore={onLoadMore}
        />
      </section>
      </Panel>
      <Separator className="separator-handle" aria-label="Resize the message list" />
      <Panel id="mail-reading" minSize="25%">
      <section className="flex h-full min-w-0 flex-col overflow-hidden">
        <ReadingPane accountId={openAccountId} threadId={threadId} />
      </section>
      </Panel>
      </Group>
      {sheetOpen && <ShortcutSheet onClose={() => setSheetOpen(false)} />}
      {snoozeFor && <SnoozePicker count={snoozeFor.length} onPick={onSnoozePick} onClose={() => setSnoozeFor(null)} />}
    </div>
  )
}
