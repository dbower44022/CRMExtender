/** The Mail surface (Mail Client PRD §2.2–2.3; MAIL-21 route, MAIL-22 folder tree,
 * MAIL-23 thread list, MAIL-24 reading pane).
 *
 * Three panes inside the content area: folder tree (unified set + one
 * section per account), the virtualized thread list for the selected
 * folder with a selection model, and the reading pane.
 */

import { useEffect, useState } from 'react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { threadKey, useInfiniteThreads, useMailFolders, useThread, type ThreadSummary } from '../../api/mail.ts'
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
  const threads = useInfiniteThreads(accountId, folder, '')
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
  const messageIdsByThread: Record<string, string[]> = {}
  if (openThread.data) {
    messageIdsByThread[`${openThread.data.account_id}:${openThread.data.thread_id}`] = openThread.data.messages.map((x) => x.id)
  }
  const clearSelection = () => setSelectedKeys(() => new Set<string>())

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
        <ActionBar targets={targets} messageIdsByThread={messageIdsByThread} onDone={clearSelection} />
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
    </div>
  )
}
