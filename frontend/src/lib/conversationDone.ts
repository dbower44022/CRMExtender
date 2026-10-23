/**
 * Mark Done and Reopen actions for conversations (Base PRD §6.4, §8.9–8.10).
 *
 * One pair of functions serves the row context menu, the Content Tool Bar,
 * the Preview Card and the full View. Every Mark Done toast carries an Undo
 * link that reopens exactly the conversations the call changed.
 */

import type { QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { workflows } from '../api/workflows.ts'

export function invalidateConversationQueries(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: ['view-data'] })
  queryClient.invalidateQueries({ queryKey: ['conversation-full'] })
  queryClient.invalidateQueries({ queryKey: ['conversation-preview'] })
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? '' : 's'}`
}

export async function markConversationsDone(
  ids: string[],
  queryClient: QueryClient,
): Promise<boolean> {
  if (ids.length === 0) return false
  try {
    const res = await workflows.markConversationsDone(ids)
    invalidateConversationQueries(queryClient)
    if (res.done === 0) {
      toast.info(ids.length === 1 ? 'Already done' : 'All selected conversations were already done')
      return true
    }
    const changed = res.ids
    toast.success(
      res.done === 1 ? 'Conversation marked done' : `${plural(res.done, 'conversation')} marked done`,
      {
        action: {
          label: 'Undo',
          onClick: () => { void reopenConversations(changed, queryClient, { quiet: true }) },
        },
      },
    )
    return true
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Mark done failed')
    return false
  }
}

export async function reopenConversations(
  ids: string[],
  queryClient: QueryClient,
  opts: { quiet?: boolean } = {},
): Promise<boolean> {
  if (ids.length === 0) return false
  try {
    const res = await workflows.reopenConversations(ids)
    invalidateConversationQueries(queryClient)
    if (opts.quiet) return true
    if (res.reopened === 0) {
      toast.info(ids.length === 1 ? 'Not done' : 'None of the selected conversations were done')
    } else {
      toast.success(
        res.reopened === 1 ? 'Conversation reopened' : `${plural(res.reopened, 'conversation')} reopened`,
      )
    }
    return true
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Reopen failed')
    return false
  }
}
