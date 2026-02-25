import { useEffect, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
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

interface CommunicationFullViewProps {
  commId: string
  onClose: () => void
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

export function CommunicationFullView({ commId, onClose }: CommunicationFullViewProps) {
  const { data, isLoading, error } = useCommunicationFull(commId)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

  // Escape key to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

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

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose()
    },
    [onClose],
  )

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
        onClose={onClose}
      />
      <SummaryCard data={data} />
      <ConversationCard conversation={data.conversation} onClose={onClose} />
      {data.triage_result && (
        <TriageCard triageResult={data.triage_result} triageReason={data.triage_reason} />
      )}
      <NotesCard notes={data.notes} />
      <MetadataCard data={data} />
    </div>
  ) : null

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
    >
      <div
        ref={containerRef}
        className="relative mx-4 flex h-[90vh] w-full max-w-5xl flex-col rounded-lg bg-white shadow-xl"
      >
        {/* Header bar */}
        <div className="flex shrink-0 items-center justify-between border-b border-surface-200 px-5 py-2.5">
          <span className="text-xs font-medium uppercase text-surface-500">
            Communication
          </span>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
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
                <div className="flex-[3] overflow-y-auto border-r border-surface-200">
                  <ContentCard data={data} onClose={onClose} />
                </div>
                {/* Right: CRM cards — scrolls independently */}
                <div className="flex-[2] overflow-y-auto p-4">
                  {crmCards}
                </div>
              </div>
            ) : (
              /* Single-column layout */
              <div className="flex-1 overflow-y-auto">
                <ContentCard data={data} onClose={onClose} />
                <div className="p-4">
                  {crmCards}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>,
    document.body,
  )
}
