import { CHANNEL_ICONS, CHANNEL_TYPE_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { CommunicationFullData } from '../../types/api.ts'

interface IdentityCardProps {
  data: CommunicationFullData
}

export function IdentityCard({ data }: IdentityCardProps) {
  const ChannelIcon = CHANNEL_ICONS[data.channel] ?? CHANNEL_ICONS.email
  const channelLabel = CHANNEL_TYPE_LABELS[data.channel] ?? data.channel

  return (
    <div className="border-b border-surface-200 bg-surface-50 px-5 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-surface-600">
          <ChannelIcon size={16} className="text-surface-400" />
          <span className="font-medium">{channelLabel}</span>
        </div>
        <span className="text-sm text-surface-500">{formatTimestamp(data.timestamp)}</span>
      </div>
    </div>
  )
}
