import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { RecordDetail } from '../detail/RecordDetail.tsx'

interface RecordModalProps {
  entityType: string
  entityId: string
  onClose: () => void
}

export function RecordModal({ entityType, entityId, onClose }: RecordModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="relative mx-4 flex h-[85vh] w-full max-w-3xl flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-3">
          <span className="text-xs font-medium text-surface-500 uppercase">
            {entityType} detail
          </span>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <RecordDetail entityType={entityType} entityId={entityId} />
        </div>
      </div>
    </div>,
    document.body,
  )
}
