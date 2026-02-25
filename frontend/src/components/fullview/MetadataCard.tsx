import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { CommunicationFullData } from '../../types/api.ts'

interface MetadataCardProps {
  data: CommunicationFullData
}

const SOURCE_LABELS: Record<string, string> = {
  synced: 'Synced',
  manual: 'Manual',
  imported: 'Imported',
  test: 'Test',
}

const DIRECTION_LABELS: Record<string, string> = {
  inbound: 'Inbound',
  outbound: 'Outbound',
  mutual: 'Meeting',
}

export function MetadataCard({ data }: MetadataCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-semibold uppercase text-surface-500 hover:bg-surface-50"
      >
        <span>Metadata</span>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {expanded && (
        <div className="border-t border-surface-200 px-4 py-3">
          <dl className="space-y-2 text-sm">
            <MetadataRow
              label="Direction"
              value={DIRECTION_LABELS[data.direction ?? ''] ?? data.direction}
            />
            <MetadataRow label="Source" value={SOURCE_LABELS[data.source ?? ''] ?? data.source} />
            {data.provider_account && (
              <>
                <MetadataRow label="Provider" value={data.provider_account.provider} />
                <MetadataRow label="Account" value={data.provider_account.email_address} />
              </>
            )}
            {data.provider_message_id && (
              <MetadataRow label="Provider Message ID" value={data.provider_message_id} mono />
            )}
            {data.provider_thread_id && (
              <MetadataRow label="Provider Thread ID" value={data.provider_thread_id} mono />
            )}
            {data.header_message_id && (
              <MetadataRow label="Header Message ID" value={data.header_message_id} mono />
            )}
            <MetadataRow label="Created" value={formatTimestamp(data.created_at)} />
            <MetadataRow label="Updated" value={formatTimestamp(data.updated_at)} />
          </dl>
        </div>
      )}
    </div>
  )
}

function MetadataRow({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null
  return (
    <div className="flex justify-between gap-4">
      <dt className="shrink-0 text-surface-400">{label}</dt>
      <dd className={`truncate text-right text-surface-700 ${mono ? 'font-mono text-xs' : ''}`} title={value}>
        {value}
      </dd>
    </div>
  )
}
