/** Inline reply at the bottom of a thread (MAIL-33): the composer for this
 * thread, or the Reply / Reply all / Forward row that opens one. */

import { Forward, Reply, ReplyAll, X } from 'lucide-react'
import { toast } from 'sonner'
import { useComposeStore, type ComposeMode } from '../../stores/compose.ts'
import { modeLabel } from '../../lib/composeUi.ts'
import { ComposeFormLoader } from './ComposeForm.tsx'

interface Props {
  threadKey: string
  /** The message a reply addresses: the thread's last message. */
  lastMessageId: string
}

export function InlineReply({ threadKey, lastMessageId }: Props) {
  const composer = useComposeStore((s) => s.composers.find((c) => c.placement === 'inline' && c.context?.threadKey === threadKey))
  const openCompose = useComposeStore((s) => s.openCompose)
  const closeCompose = useComposeStore((s) => s.closeCompose)
  const start = (mode: ComposeMode) => {
    if (openCompose(mode, { communicationId: lastMessageId, threadKey }, 'inline') === null) toast.info('Close a composer first (three are open)')
  }
  if (!composer) {
    return (
      <div className="flex gap-2 border-t border-surface-200 px-5 py-3" data-testid="inline-reply-row">
        <button type="button" onClick={() => start('reply')} className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-sm text-surface-700 hover:bg-surface-50" title="Reply (r)">
          <Reply size={14} /> Reply
        </button>
        <button type="button" onClick={() => start('reply_all')} className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-sm text-surface-700 hover:bg-surface-50" title="Reply all (a)">
          <ReplyAll size={14} /> Reply all
        </button>
        <button type="button" onClick={() => start('forward')} className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-sm text-surface-700 hover:bg-surface-50" title="Forward (f)">
          <Forward size={14} /> Forward
        </button>
      </div>
    )
  }
  return (
    <div className="m-4 flex max-h-[70vh] min-h-[320px] flex-col rounded-lg border border-primary-200 bg-white shadow-sm" data-testid="inline-reply">
      <div className="flex items-center justify-between rounded-t-lg border-b border-surface-200 bg-surface-50 px-3 py-1.5 text-xs font-semibold text-surface-700">
        <span>{modeLabel(composer.mode)}</span>
        <button type="button" aria-label="Close composer" className="rounded p-0.5 text-surface-500 hover:bg-surface-200" onClick={() => closeCompose(composer.id)}>
          <X size={14} />
        </button>
      </div>
      <ComposeFormLoader composer={composer} variant="inline" onClose={() => closeCompose(composer.id)} />
    </div>
  )
}
