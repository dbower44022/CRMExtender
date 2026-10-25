/**
 * Conversation System Status display (Conversation Base PRD §6.1, §6.4).
 *
 * One label and one style per stored value, shared by the grid cards, the
 * Preview Card and the full View so "done" reads as Done everywhere.
 */

export const CONVERSATION_STATUS_DONE = 'done'
export const CONVERSATION_STATUS_ACTIVE = 'active'

const LABELS: Record<string, string> = {
  active: 'Active',
  stale: 'Stale',
  done: 'Done',
  closed: 'Closed',
  archived: 'Archived',
}

const CLASSES: Record<string, string> = {
  active: 'bg-green-50 text-green-700',
  stale: 'bg-amber-50 text-amber-700',
  done: 'bg-surface-100 text-surface-500',
  closed: 'bg-surface-100 text-surface-500',
  archived: 'bg-surface-100 text-surface-400',
}

const REOPEN_REASONS: Record<string, string> = {
  inbound: 'New inbound message',
  user: 'Reopened by user',
}

export function conversationStatusLabel(status: string | null | undefined): string {
  if (!status) return ''
  return LABELS[status] ?? status.charAt(0).toUpperCase() + status.slice(1)
}

export function conversationStatusClass(status: string | null | undefined): string {
  return (status && CLASSES[status]) || 'bg-surface-100 text-surface-500'
}

export function isConversationDone(status: string | null | undefined): boolean {
  return status === CONVERSATION_STATUS_DONE
}

const DONE_REASONS: Record<string, string> = {
  user: 'Marked done',
  timer: 'Silent past the done threshold',
}

export function doneReasonLabel(reason: string | null | undefined): string {
  if (!reason) return ''
  return DONE_REASONS[reason] ?? reason
}

export function reopenReasonLabel(reason: string | null | undefined): string {
  if (!reason) return ''
  return REOPEN_REASONS[reason] ?? reason
}
