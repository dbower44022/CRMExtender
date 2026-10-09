/** The Mail surface (Mail Client PRD §2.2–2.3; MAIL-21 route, MAIL-22 folder tree).
 *
 * Three panes inside the content area: folder tree (unified set + one
 * section per account), thread list for the selected folder, and the
 * reading pane. MAIL-23/24 replace the basic list and pane here with the
 * virtualized rows and the collapsing message view.
 */

import { useEffect } from 'react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useMailFolders, useThreads } from '../../api/mail.ts'
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
  const threads = useThreads(accountId, folder, '')

  // A deep link names an account that is not visible: fall back to unified.
  useEffect(() => {
    if (!folders.data) return
    if (accountId !== 'unified' && !folders.data.accounts.some((a) => a.id === accountId)) {
      setMailFolder('unified', 'inbox')
    }
  }, [folders.data, accountId, setMailFolder])

  // The selected thread's account: a thread id is only unique within an account.
  const selected = threadId
    ? threads.data?.items.find((t) => t.thread_id === threadId) ?? null
    : null
  const selectedAccountId = selected?.account_id ?? (accountId !== 'unified' ? accountId : null)

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
      <section className="flex w-[380px] shrink-0 flex-col overflow-hidden border-r border-surface-200">
        <ThreadList
          page={threads.data}
          loading={threads.isLoading}
          error={threads.error ? String(threads.error) : null}
          selectedThreadId={threadId}
          unified={accountId === 'unified'}
          onSelect={(t) => setMailThread(t.thread_id)}
        />
      </section>
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <ReadingPane accountId={selectedAccountId} threadId={threadId} />
      </section>
    </div>
  )
}
