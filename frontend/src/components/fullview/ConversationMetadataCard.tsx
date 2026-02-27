import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { ConversationFullData } from '../../types/api.ts'

interface ConversationMetadataCardProps {
  data: ConversationFullData
}

export function ConversationMetadataCard({ data }: ConversationMetadataCardProps) {
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
            {data.provider_account && (
              <>
                <MetadataRow label="Provider" value={data.provider_account.provider} />
                <MetadataRow label="Account" value={data.provider_account.email_address} />
              </>
            )}
            {data.topic && (
              <>
                <MetadataRow label="Topic" value={data.topic.name} />
                {data.topic.project_name && (
                  <MetadataRow label="Project" value={data.topic.project_name} />
                )}
              </>
            )}
            <MetadataRow label="Created" value={formatTimestamp(data.created_at)} />
            <MetadataRow label="Updated" value={formatTimestamp(data.updated_at)} />
            {data.created_by_name && (
              <MetadataRow label="Created by" value={data.created_by_name} />
            )}
            {data.updated_by_name && (
              <MetadataRow label="Updated by" value={data.updated_by_name} />
            )}
            <MetadataRow label="Conversation ID" value={data.id} mono />
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
