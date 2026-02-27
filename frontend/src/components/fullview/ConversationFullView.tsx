import { useEffect, useRef, useState } from 'react'
import { useConversationFull } from '../../api/conversationFull.ts'
import { ConversationIdentityCard } from './ConversationIdentityCard.tsx'
import { ConversationTimelineCard } from './ConversationTimelineCard.tsx'
import { ConversationParticipantsCard } from './ConversationParticipantsCard.tsx'
import { ConversationSummaryCard } from './ConversationSummaryCard.tsx'
import { ConversationProjectCard } from './ConversationProjectCard.tsx'
import { ConversationEventsCard } from './ConversationEventsCard.tsx'
import { ConversationTagsCard } from './ConversationTagsCard.tsx'
import { TriageCard } from './TriageCard.tsx'
import { ConversationNotesCard } from './ConversationNotesCard.tsx'
import { ConversationMetadataCard } from './ConversationMetadataCard.tsx'
import { FullViewSkeleton } from './FullViewSkeleton.tsx'
import type { ConversationFullData } from '../../types/api.ts'

interface ConversationFullViewProps {
  convId: string
  onNavigateAway: () => void
}

const TWO_COLUMN_MIN_WIDTH = 900

/** Count visible CRM cards (Metadata excluded — collapsed by default) */
function countVisibleCards(data: ConversationFullData): number {
  let count = 0
  if (data.participants.length > 0) count++
  if (data.ai_summary || data.ai_action_items || data.ai_topics) count++
  count++ // Project card always visible
  if (data.events.length > 0) count++
  if (data.tags.length > 0) count++
  if (data.triage_result) count++
  if (data.notes.length > 0) count++
  return count
}

export function ConversationFullView({ convId, onNavigateAway }: ConversationFullViewProps) {
  const { data, isLoading, error } = useConversationFull(convId)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

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
      <ConversationParticipantsCard
        participants={data.participants}
        onNavigateAway={onNavigateAway}
      />
      <ConversationSummaryCard data={data} />
      <ConversationProjectCard topic={data.topic} />
      <ConversationEventsCard events={data.events} onNavigateAway={onNavigateAway} />
      <ConversationTagsCard tags={data.tags} />
      {data.triage_result && (
        <TriageCard triageResult={data.triage_result} triageReason={data.dismissed_reason} />
      )}
      <ConversationNotesCard notes={data.notes} />
      <ConversationMetadataCard data={data} />
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
          <p>Failed to load conversation.</p>
          <p className="max-w-md text-xs text-surface-400">{String(error)}</p>
        </div>
      ) : !data ? null : (
        <>
          <ConversationIdentityCard data={data} />

          {useTwoColumn ? (
            <div className="flex min-h-0 flex-1">
              <div className="flex flex-[3] flex-col overflow-y-auto border-r border-surface-200">
                <ConversationTimelineCard
                  communications={data.communications}
                  onNavigateAway={onNavigateAway}
                />
              </div>
              <div className="flex-[2] overflow-y-auto p-4">
                {crmCards}
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              <ConversationTimelineCard
                communications={data.communications}
                onNavigateAway={onNavigateAway}
              />
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
