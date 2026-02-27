import { useEffect, useRef, useState } from 'react'
import { useCommunicationFull } from '../../api/communicationFull.ts'
import { IdentityCard } from './IdentityCard.tsx'
import { ContentCard } from './ContentCard.tsx'
import { ParticipantsCard } from './ParticipantsCard.tsx'
import { SummaryCard } from './SummaryCard.tsx'
import { ConversationCard } from './ConversationCard.tsx'
import { TriageCard } from './TriageCard.tsx'
import { NotesCard } from './NotesCard.tsx'
import { MetadataCard } from './MetadataCard.tsx'
import { FullViewSkeleton } from './FullViewSkeleton.tsx'
import type { CommunicationFullData } from '../../types/api.ts'

interface CommunicationFullContentProps {
  commId: string
  onNavigateAway: () => void
}

const TWO_COLUMN_MIN_WIDTH = 900

/** Count visible, non-collapsed CRM cards (Metadata excluded — collapsed by default) */
function countVisibleCards(data: CommunicationFullData): number {
  let count = 0
  if (data.participants.length > 0) count++
  if (data.ai_summary) count++
  count++ // Conversation card is always visible
  if (data.triage_result) count++
  if (data.notes.length > 0) count++
  return count
}

export function CommunicationFullContent({ commId, onNavigateAway }: CommunicationFullContentProps) {
  const { data, isLoading, error } = useCommunicationFull(commId)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

  // Measure container width with ResizeObserver
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width)
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const useTwoColumn = data
    ? containerWidth >= TWO_COLUMN_MIN_WIDTH && countVisibleCards(data) >= 2
    : false

  const crmCards = data ? (
    <div className="space-y-3">
      <ParticipantsCard
        participants={data.participants}
        providerAccount={data.provider_account}
        senderName={data.sender_name}
        senderAddress={data.sender_address}
        onClose={onNavigateAway}
      />
      <SummaryCard data={data} />
      <ConversationCard conversation={data.conversation} onClose={onNavigateAway} />
      {data.triage_result && (
        <TriageCard triageResult={data.triage_result} triageReason={data.triage_reason} />
      )}
      <NotesCard notes={data.notes} />
      <MetadataCard data={data} />
    </div>
  ) : null

  return (
    <div ref={containerRef} className="flex h-full flex-col">
      {isLoading ? (
        <div className="flex-1 overflow-y-auto">
          <FullViewSkeleton />
        </div>
      ) : error ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-red-500">
          <p>Failed to load communication.</p>
          <p className="max-w-md text-xs text-surface-400">{String(error)}</p>
        </div>
      ) : !data ? null : (
        <>
          {/* Identity card — always full width */}
          <IdentityCard data={data} />

          {useTwoColumn ? (
            /* Two-column layout */
            <div className="flex min-h-0 flex-1">
              {/* Left: Content — scrolls independently */}
              <div className="flex-[3] overflow-y-auto">
                <ContentCard data={data} onClose={onNavigateAway} />
              </div>
              {/* Right: CRM cards — scrolls independently, subtle sidebar tint */}
              <div className="flex-[2] overflow-y-auto border-l border-surface-200 bg-surface-50 p-4">
                {crmCards}
              </div>
            </div>
          ) : (
            /* Single-column layout */
            <div className="flex-1 overflow-y-auto">
              <ContentCard data={data} onClose={onNavigateAway} />
              <div className="p-4">
                {crmCards}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
