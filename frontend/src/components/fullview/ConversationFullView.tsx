import { useCallback, useEffect, useRef, useState } from 'react'
import { useConversationFull } from '../../api/conversationFull.ts'
import { buildParticipantColorMap } from '../../lib/participantColors.ts'
import { ConversationIdentityCard } from './ConversationIdentityCard.tsx'
import { ConversationTimelineCard } from './ConversationTimelineCard.tsx'
import { ConversationParticipantsCard } from './ConversationParticipantsCard.tsx'
import { ConversationSummaryCard } from './ConversationSummaryCard.tsx'
import { ConversationProjectCard } from './ConversationProjectCard.tsx'
import { ConversationEventsCard } from './ConversationEventsCard.tsx'
import { ConversationAssociationsCard } from './ConversationAssociationsCard.tsx'
import { ConversationChildrenCard } from './ConversationChildrenCard.tsx'
import { ConversationTagsCard } from './ConversationTagsCard.tsx'
import { TriageCard } from './TriageCard.tsx'
import { ConversationNotesCard } from './ConversationNotesCard.tsx'
import { ConversationMetadataCard } from './ConversationMetadataCard.tsx'
import { FullViewSkeleton } from './FullViewSkeleton.tsx'

interface ConversationFullViewProps {
  convId: string
  onNavigateAway: () => void
}

// Layout constraints per PRD Section 5
const TWO_COLUMN_MIN_WIDTH = 700
const RIGHT_COL_MIN_PX = 280
const LEFT_COL_MIN_RATIO = 0.4
const RIGHT_COL_MAX_RATIO = 0.6

const SPLITTER_KEY_PREFIX = 'conv-splitter-'
const DEFAULT_RIGHT_WIDTH = 360

function getSplitterWidth(convId: string): number | null {
  try {
    const stored = localStorage.getItem(SPLITTER_KEY_PREFIX + convId)
    if (stored) return parseInt(stored, 10)
  } catch { /* ignore */ }
  return null
}

function setSplitterWidth(convId: string, width: number) {
  try {
    localStorage.setItem(SPLITTER_KEY_PREFIX + convId, String(Math.round(width)))
  } catch { /* ignore */ }
}

/**
 * Clamp right column width to valid range:
 * - min: RIGHT_COL_MIN_PX (280px)
 * - max: RIGHT_COL_MAX_RATIO * containerWidth (60%)
 * - left column must be at least LEFT_COL_MIN_RATIO * containerWidth (40%)
 * Returns null if constraints can't be simultaneously satisfied (=> single column).
 */
function clampRightWidth(desired: number, containerWidth: number): number | null {
  const maxRight = containerWidth * RIGHT_COL_MAX_RATIO
  const minLeft = containerWidth * LEFT_COL_MIN_RATIO
  const maxFromLeft = containerWidth - minLeft

  const effectiveMax = Math.min(maxRight, maxFromLeft)
  if (effectiveMax < RIGHT_COL_MIN_PX) return null // Can't satisfy both constraints

  return Math.max(RIGHT_COL_MIN_PX, Math.min(desired, effectiveMax))
}

export function ConversationFullView({ convId, onNavigateAway }: ConversationFullViewProps) {
  const { data, isLoading, error } = useConversationFull(convId)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  const [rightWidth, setRightWidth] = useState(() => getSplitterWidth(convId) ?? DEFAULT_RIGHT_WIDTH)

  useEffect(() => {
    setRightWidth(getSplitterWidth(convId) ?? DEFAULT_RIGHT_WIDTH)
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

  // Determine layout: two-column only if width threshold met AND constraints satisfiable
  const clampedRight = containerWidth >= TWO_COLUMN_MIN_WIDTH
    ? clampRightWidth(rightWidth, containerWidth)
    : null
  const useTwoColumn = clampedRight !== null

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = clampedRight ?? DEFAULT_RIGHT_WIDTH

    const onMove = (ev: MouseEvent) => {
      const delta = startX - ev.clientX
      const newWidth = startWidth + delta
      setRightWidth(newWidth)
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [clampedRight])

  // Persist splitter position when it changes
  useEffect(() => {
    setSplitterWidth(convId, rightWidth)
  }, [convId, rightWidth])

  const colorMap = data
    ? buildParticipantColorMap(
        data.participants.map((p) => ({ address: p.address, contact_id: p.contact_id })),
        data.account_owner_email,
      )
    : null

  // CRM cards — ordered per PRD Section 14.2
  const crmCards = data ? (
    <div className="space-y-3">
      <ConversationParticipantsCard
        participants={data.participants}
        colorMap={colorMap!}
        accountOwnerEmail={data.account_owner_email}
        onNavigateAway={onNavigateAway}
      />
      <ConversationSummaryCard data={data} />
      <ConversationAssociationsCard associations={data.associations} onNavigateAway={onNavigateAway} />
      {data.is_aggregate && (
        <ConversationChildrenCard children={data.children} onNavigateAway={onNavigateAway} />
      )}
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
          {/* Identity Card — always full width */}
          <ConversationIdentityCard data={data} />

          {useTwoColumn ? (
            /* Two-column layout: timeline left, CRM sidebar right */
            <div className="flex min-h-0 flex-1">
              {/* Left column — Timeline (independent scroll) */}
              <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
                <ConversationTimelineCard
                  communications={data.communications}
                  colorMap={colorMap!}
                  onNavigateAway={onNavigateAway}
                />
              </div>

              {/* Draggable splitter */}
              <div
                className="flex w-1.5 shrink-0 cursor-col-resize items-center justify-center bg-surface-200 transition-colors hover:bg-primary-300 active:bg-primary-400"
                onMouseDown={handleDragStart}
                title="Drag to resize"
              />

              {/* Right column — CRM sidebar (independent scroll, visual distinction) */}
              <div
                className="shrink-0 overflow-y-auto border-l border-surface-200 bg-surface-50 p-4"
                style={{ width: clampedRight }}
              >
                {crmCards}
              </div>
            </div>
          ) : (
            /* Single-column layout: timeline first, then CRM cards */
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
