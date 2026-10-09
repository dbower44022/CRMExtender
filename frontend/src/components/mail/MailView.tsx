/** The Mail surface (Mail Client PRD §2.2–2.3; MAIL-21 route, MAIL-22 folder tree,
 * MAIL-23 thread list, MAIL-24 reading pane).
 *
 * Three panes inside the content area: folder tree (unified set + one
 * section per account), the virtualized thread list for the selected
 * folder with a selection model, and the reading pane.
 */

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { useComposeStore } from '../../stores/compose.ts'
import { useMailShortcuts } from '../../hooks/useMailShortcuts.ts'
import { ShortcutSheet } from './ShortcutSheet.tsx'
import { SearchBox } from './SearchBox.tsx'
import { loadSavedSearches, storeSavedSearches, type SavedSearch } from '../../lib/mailSearchUi.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { threadKey, useInfiniteThreads, useMailAction, useMailFolders, useThread, type ThreadSummary } from '../../api/mail.ts'
import { ActionBar } from './ActionBar.tsx'
import { FolderTree } from './FolderTree.tsx'
import { ThreadList } from './ThreadList.tsx'
import { ReadingPane } from './ReadingPane.tsx'

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
      if (sheetOpen) setSheetOpen(false)
      else if (threadId) setMailThread(null)
      else if (selectedKeys.size > 0) clearSelection()
    },
    act: (action) => {
      if (shortcutTargets.length === 0) return
      const starred = shortcutTargets.some((t) => t.starred)
      const kind = action === 'star' && starred ? 'unstar' : action
      act.mutateAsync({ action: kind, threads: shortcutTargets.map((t) => ({ account_id: t.account_id, thread_id: t.thread_id })) })
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
      const msgs = openThread.data?.messages
      if (!msgs || msgs.length === 0) { toast.info('Open a thread first'); return }
      openCompose(mode, { communicationId: msgs[msgs.length - 1].id })
    },
    compose: () => openCompose('new'),
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
      <section className="relative flex w-[400px] shrink-0 flex-col overflow-hidden border-r border-surface-200">
        <SearchBox ref={searchRef} value={searchQ} onSearch={setSearchQ} saved={saved} onSaveSearch={saveSearch} onRemoveSaved={removeSaved} />
        <ActionBar targets={targets} onDone={clearSelection} />
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
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <ReadingPane accountId={openAccountId} threadId={threadId} />
      </section>
      {sheetOpen && <ShortcutSheet onClose={() => setSheetOpen(false)} />}
    </div>
  )
}
