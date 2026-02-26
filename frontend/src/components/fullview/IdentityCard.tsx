import { Reply, ReplyAll, Forward } from 'lucide-react'
import { CHANNEL_ICONS, CHANNEL_TYPE_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useComposeStore } from '../../stores/compose.ts'
import type { CommunicationFullData } from '../../types/api.ts'

interface IdentityCardProps {
  data: CommunicationFullData
}

export function IdentityCard({ data }: IdentityCardProps) {
  const ChannelIcon = CHANNEL_ICONS[data.channel] ?? CHANNEL_ICONS.email
  const channelLabel = CHANNEL_TYPE_LABELS[data.channel] ?? data.channel
  const openCompose = useComposeStore((s) => s.openCompose)
  const isEmail = data.channel === 'email'

  return (
    <div className="border-b border-surface-200 bg-surface-50 px-5 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-surface-600">
          <ChannelIcon size={16} className="text-surface-400" />
          <span className="font-medium">{channelLabel}</span>
        </div>
        <div className="flex items-center gap-2">
          {isEmail && (
            <>
              <button
                onClick={() => openCompose('reply', { communicationId: data.id })}
                className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-surface-500 hover:bg-surface-200 hover:text-surface-700"
                title="Reply"
              >
                <Reply size={13} />
                Reply
              </button>
              <button
                onClick={() => openCompose('reply_all', { communicationId: data.id })}
                className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-surface-500 hover:bg-surface-200 hover:text-surface-700"
                title="Reply All"
              >
                <ReplyAll size={13} />
                Reply All
              </button>
              <button
                onClick={() => openCompose('forward', { communicationId: data.id })}
                className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-surface-500 hover:bg-surface-200 hover:text-surface-700"
                title="Forward"
              >
                <Forward size={13} />
                Forward
              </button>
            </>
          )}
          <span className="text-sm text-surface-500">{formatTimestamp(data.timestamp)}</span>
        </div>
      </div>
    </div>
  )
}
