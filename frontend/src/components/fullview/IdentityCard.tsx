import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { CommunicationFullData } from '../../types/api.ts'

interface IdentityCardProps {
  data: CommunicationFullData
}

const DIRECTION_LABELS: Record<string, string> = {
  inbound: 'Inbound',
  outbound: 'Outbound',
  mutual: 'Meeting',
}

const SOURCE_LABELS: Record<string, string> = {
  synced: 'Synced',
  manual: 'Manual',
  imported: 'Imported',
  test: 'Test',
}

export function IdentityCard({ data }: IdentityCardProps) {
  const ChannelIcon = CHANNEL_ICONS[data.channel] ?? CHANNEL_ICONS.email
  const channelLabel = CHANNEL_LABELS[data.channel] ?? data.channel
  const directionLabel = DIRECTION_LABELS[data.direction ?? ''] ?? data.direction
  const sourceLabel = SOURCE_LABELS[data.source ?? ''] ?? data.source

  return (
    <div className="border-b border-surface-200 bg-surface-50 px-5 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-surface-600">
          <ChannelIcon size={16} className="text-surface-400" />
          <span className="font-medium">{channelLabel}</span>
          <span className="text-surface-300">&middot;</span>
          <span>{directionLabel}</span>
          {data.source && (
            <>
              <span className="text-surface-300">&middot;</span>
              <span>{sourceLabel}</span>
            </>
          )}
        </div>
        <span className="text-sm text-surface-500">{formatTimestamp(data.timestamp)}</span>
      </div>
      {data.provider_account && (
        <div className="mt-0.5 text-xs text-surface-400">
          from {data.provider_account.email_address}
        </div>
      )}
    </div>
  )
}
