import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'

interface ChannelBreakdownProps {
  breakdown: Record<string, number>
  className?: string
}

export function ChannelBreakdown({ breakdown, className }: ChannelBreakdownProps) {
  const entries = Object.entries(breakdown).filter(([, count]) => count > 0)
  if (entries.length === 0) return null

  return (
    <span className={`inline-flex items-center gap-2 ${className ?? ''}`}>
      {entries.map(([channel, count]) => {
        const Icon = CHANNEL_ICONS[channel] ?? CHANNEL_ICONS.email
        return (
          <span
            key={channel}
            className="inline-flex items-center gap-0.5"
            title={`${count} ${CHANNEL_LABELS[channel] ?? channel}`}
          >
            <Icon size={12} />
            <span>{count}</span>
          </span>
        )
      })}
    </span>
  )
}
