/** Mail surface API client (Mail Client PRD; routes in poc/web/routes/api_mail.py). */

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { get, post } from './client.ts'

export interface FolderCount {
  total: number
  unread: number
}

export interface MailLabel {
  id: string
  provider_label_id: string
  name: string
  kind: string
  parent_id: string | null
  total: number
  unread: number
}

export interface MailAccountFolders {
  id: string
  email: string
  display_name: string | null
  /** Label colour (#rrggbb) chosen on Settings → Accounts, or null. */
  color: string | null
  provider: string
  is_active: boolean
  initial_sync_done: boolean
  last_synced_at: string | null
  system: Record<string, FolderCount>
  labels: MailLabel[]
  sync: {
    running: boolean
    last_finished: string | null
    next_due_at: string | null
    last_error: string | null
  } | null
}

export interface MailFolders {
  accounts: MailAccountFolders[]
  unified: Record<string, FolderCount>
}

export interface ThreadParticipant {
  address: string
  name: string | null
  is_me: boolean
}

export interface ThreadSummary {
  account_id: string
  account_email: string
  account_color?: string | null
  thread_id: string
  subject: string
  snippet: string
  last_at: string
  message_count: number
  unread_count: number
  starred: boolean
  has_attachments: boolean
  labels: string[]
  participants: ThreadParticipant[]
  latest_message_id: string | null
  /** ISO return time while the thread is snoozed (MAIL-17); null or absent otherwise. */
  snoozed_until?: string | null
}

/** Stable key for a thread row: a thread id is unique only within its account. */
export const threadKey = (t: Pick<ThreadSummary, 'account_id' | 'thread_id'>) => `${t.account_id}:${t.thread_id}`

export interface ThreadPage {
  total: number
  items: ThreadSummary[]
  limit: number
  offset: number
}

export interface MailAttachment {
  id: string
  filename: string
  mime_type: string | null
  size_bytes: number | null
  content_id: string | null
  is_inline: boolean
}

export interface MailMessage {
  id: string
  timestamp: string
  direction: string | null
  subject: string | null
  snippet: string | null
  sender: {
    address: string | null
    name: string | null
    contact_id: string | null
    contact_name: string | null
    is_me: boolean
  }
  participants: { address: string; name: string | null; role: string; contact_id: string | null; contact_name: string | null }[]
  body_html: string
  body_text: string
  is_read: boolean
  is_starred: boolean
  is_archived: boolean
  labels: { id: string; name: string; kind: string }[]
  attachments: MailAttachment[]
  header_message_id: string | null
  provider_message_id: string | null
}

export interface ThreadDetail {
  account_id: string
  account_email: string
  thread_id: string
  subject: string
  labels: string[]
  message_count: number
  unread_count: number
  conversation: { id: string; title: string | null; ai_summary: string | null; ai_status: string | null } | null
  messages: MailMessage[]
}

export function useMailFolders(enabled = true) {
  return useQuery({
    queryKey: ['mail', 'folders'],
    queryFn: () => get<MailFolders>('/mail/folders'),
    enabled,
    staleTime: 15_000,
    refetchInterval: 30_000,
  })
}

/** Unread count for the rail badge: the unified inbox. */
export function useMailUnread() {
  return useQuery({
    queryKey: ['mail', 'folders'],
    queryFn: () => get<MailFolders>('/mail/folders'),
    staleTime: 15_000,
    refetchInterval: 60_000,
    select: (d) => d.unified?.inbox?.unread ?? 0,
  })
}

export function useThreads(accountId: string, folder: string, q: string, limit = 50) {
  const isLabel = folder.startsWith('label:')
  const params = new URLSearchParams()
  if (isLabel) params.set('label_id', folder.slice('label:'.length))
  else params.set('folder', folder)
  if (accountId && accountId !== 'unified') params.set('account_id', accountId)
  if (q) params.set('q', q)
  params.set('limit', String(limit))
  return useQuery({
    queryKey: ['mail', 'threads', accountId, folder, q, limit],
    queryFn: () => get<ThreadPage>(`/mail/threads?${params.toString()}`),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
}

/** Infinite thread list (MAIL-23): pages of `limit` by offset; refetched on the poll interval. */
export function useInfiniteThreads(accountId: string, folder: string, q: string, limit = 50) {
  const isLabel = folder.startsWith('label:')
  const base = new URLSearchParams()
  if (isLabel) base.set('label_id', folder.slice('label:'.length))
  else base.set('folder', folder)
  if (accountId && accountId !== 'unified') base.set('account_id', accountId)
  if (q) base.set('q', q)
  base.set('limit', String(limit))
  return useInfiniteQuery({
    queryKey: ['mail', 'threads', 'infinite', accountId, folder, q, limit],
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams(base)
      params.set('offset', String(pageParam))
      return get<ThreadPage>(`/mail/threads?${params.toString()}`)
    },
    initialPageParam: 0,
    getNextPageParam: (last) => {
      const next = last.offset + last.items.length
      return next < last.total && last.items.length > 0 ? next : undefined
    },
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
}

export function useThread(accountId: string | null, threadId: string | null) {
  return useQuery({
    queryKey: ['mail', 'thread', accountId, threadId],
    queryFn: () => get<ThreadDetail>(`/mail/threads/${encodeURIComponent(accountId!)}/${encodeURIComponent(threadId!)}`),
    enabled: !!accountId && !!threadId,
    staleTime: 10_000,
  })
}

export interface MailActionInput {
  action: string
  communication_ids?: string[]
  /** Whole threads: every current message of each is targeted server-side (D-33). */
  threads?: { account_id: string; thread_id: string }[]
  label_id?: string
  account_id?: string
  payload?: Record<string, unknown>
}

export function useMailAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: MailActionInput) => post<{ id: string; status: string } | { items: unknown[] }>('/mail/actions', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mail'] })
    },
  })
}

export interface MailActionRow {
  id: string
  account_id: string
  action: string
  target_ids: string[]
  status: 'pending' | 'pushed' | 'gone' | 'failed' | 'discarded'
  attempts: number
  error: string | null
  created_at: string
}

/** The action queue for the caller's accounts: counts plus recent rows. */
export function useMailActionQueue() {
  return useQuery({
    queryKey: ['mail', 'actions'],
    queryFn: () => get<{ items: MailActionRow[]; counts: { pending: number; failed: number } }>('/mail/actions?limit=50'),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
}

export function useMailActionResolve() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, op }: { id: string; op: 'retry' | 'discard' }) =>
      post<MailActionRow>(`/mail/actions/${encodeURIComponent(id)}/${op}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mail'] })
    },
  })
}
