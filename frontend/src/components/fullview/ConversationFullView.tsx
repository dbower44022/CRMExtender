import { useCallback, useEffect, useRef, useState } from 'react'
import { useConversationFull } from '../../api/conversationFull.ts'
import { buildParticipantColorMap } from '../../lib/participantColors.ts'
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

interface ConversationFullViewProps {
  convId: string
  onNavigateAway: () => void
}

const TWO_COLUMN_MIN_WIDTH = 700
const SPLITTER_MIN_RIGHT = 280
const SPLITTER_KEY_PREFIX = 'conv-splitter-'
const DEFAULT_RIGHT_WIDTH = 360

function getSplitterWidth(convId: string): number {
  try {
    const stored = localStorage.getItem(SPLITTER_KEY_PREFIX + convId)
    if (stored) return Math.max(SPLITTER_MIN_RIGHT, parseInt(stored, 10))
  } catch { /* ignore */ }
  return DEFAULT_RIGHT_WIDTH
}

function setSplitterWidth(convId: string, width: number) {
  try {
    localStorage.setItem(SPLITTER_KEY_PREFIX + convId, String(Math.round(width)))
  } catch { /* ignore */ }
}

export function ConversationFullView({ convId, onNavigateAway }: ConversationFullViewProps) {
  const { data, isLoading, error } = useConversationFull(convId)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  const [rightWidth, setRightWidth] = useState(() => getSplitterWidth(convId))

  useEffect(() => {
    setRightWidth(getSplitterWidth(convId))
  }, [convId])

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

  const useTwoColumn = containerWidth >= TWO_COLUMN_MIN_WIDTH

  // Clamp right width: min 280, max 60% of container
  const clampedRight = Math.max(SPLITTER_MIN_RIGHT, Math.min(rightWidth, containerWidth * 0.6))

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = clampedRight

    const onMove = (ev: MouseEvent) => {
      const delta = startX - ev.clientX
      const newWidth = Math.max(SPLITTER_MIN_RIGHT, Math.min(startWidth + delta, containerWidth * 0.6))
      setRightWidth(newWidth)
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      // Persist on drop
      setSplitterWidth(convId, rightWidth)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [clampedRight, containerWidth, convId, rightWidth])

  // Persist when rightWidth changes (debounced via mouseup above)
  useEffect(() => {
    setSplitterWidth(convId, rightWidth)
  }, [convId, rightWidth])

  const colorMap = data
    ? buildParticipantColorMap(
        data.participants.map((p) => ({ address: p.address, contact_id: p.contact_id })),
        data.account_owner_email,
      )
    : null

  const crmCards = data ? (
    <div className="space-y-3">
      <ConversationParticipantsCard
        participants={data.participants}
        colorMap={colorMap!}
        accountOwnerEmail={data.account_owner_email}
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
              <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
                <ConversationTimelineCard
                  communications={data.communications}
                  colorMap={colorMap!}
                  onNavigateAway={onNavigateAway}
                />
              </div>
              {/* Drag handle */}
              <div
                className="flex w-1.5 shrink-0 cursor-col-resize items-center justify-center bg-surface-200 hover:bg-primary-300 active:bg-primary-400"
                onMouseDown={handleDragStart}
                title="Drag to resize"
              />
              <div
                className="shrink-0 overflow-y-auto border-l border-surface-200 bg-surface-50 p-4"
                style={{ width: clampedRight }}
              >
                {crmCards}
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              <ConversationTimelineCard
                communications={data.communications}
                colorMap={colorMap!}
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
