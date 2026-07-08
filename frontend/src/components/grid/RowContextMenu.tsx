import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Eye,
  Maximize2,
  Pencil,
  Trash2,
  Link,
  Download,
  Tag,
  Archive,
} from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { deleteEntity, recomputeScore } from '../../api/subresources.ts'
import { useNavigationStore } from '../../stores/navigation.ts'

interface RowContextMenuProps {
  x: number
  y: number
  rowId: string
  rowIndex: number
  entityType: string
  selectedRowIds: Set<string>
  onClose: () => void
  onOpenDetail: () => void
  onOpenModal: () => void
  onEdit: () => void
}

const menuItemClass =
  'flex w-full items-center gap-2 px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50 cursor-pointer'

const comingSoon = () => toast('Coming soon')

export function RowContextMenu({
  x,
  y,
  rowId,
  entityType,
  selectedRowIds,
  onClose,
  onOpenDetail,
  onOpenModal,
  onEdit,
}: RowContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const canMutate = entityType === 'contact' || entityType === 'company'

  const handleDelete = async () => {
    if (!confirmingDelete) {
      setConfirmingDelete(true)
      return
    }
    try {
      await deleteEntity(entityType, rowId)
      toast.success(`${entityType === 'contact' ? 'Contact' : 'Company'} deleted`)
      const nav = useNavigationStore.getState()
      if (nav.selectedRowId === rowId) nav.setSelectedRow(null, -1)
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
    } catch {
      toast.error('Delete failed')
    }
    onClose()
  }

  const handleScore = async () => {
    onClose()
    try {
      const res = await recomputeScore(entityType, rowId) as {
        score: { score_value?: number } | null
      }
      const value = res.score?.score_value
      toast.success(
        value != null
          ? `Score recomputed: ${Math.round(value)}`
          : 'No communications yet — no score computed',
      )
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
    } catch {
      toast.error('Score recompute failed')
    }
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', keyHandler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('keydown', keyHandler)
    }
  }, [onClose])

  // Adjust position to stay within viewport
  const adjustedX = Math.min(x, window.innerWidth - 200)
  const adjustedY = Math.min(y, window.innerHeight - 250)

  const isBulkMode = selectedRowIds.size > 0

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[180px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg"
      style={{ left: adjustedX, top: adjustedY }}
    >
      {isBulkMode ? (
        <>
          <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
            <Pencil size={12} />
            Bulk Edit ({selectedRowIds.size})
          </button>
          <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
            <Trash2 size={12} />
            Bulk Delete ({selectedRowIds.size})
          </button>
          <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
            <Download size={12} />
            Bulk Export
          </button>
          <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
            <Tag size={12} />
            Bulk Tag
          </button>
          <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
            <Archive size={12} />
            Bulk Archive
          </button>
        </>
      ) : (
        <>
          <button onClick={onOpenDetail} className={menuItemClass}>
            <Eye size={12} />
            Open in Detail Panel
          </button>
          <button onClick={onOpenModal} className={menuItemClass}>
            <Maximize2 size={12} />
            Open in Full View
          </button>
          <div className="my-1 border-t border-surface-200" />
          <button onClick={onEdit} className={menuItemClass}>
            <Pencil size={12} />
            Edit
          </button>
          {canMutate ? (
            <button
              onClick={handleDelete}
              className={confirmingDelete
                ? 'flex w-full items-center gap-2 px-3 py-1.5 text-xs font-medium text-white bg-red-600 cursor-pointer'
                : menuItemClass}
            >
              <Trash2 size={12} />
              {confirmingDelete ? 'Confirm delete?' : 'Delete'}
            </button>
          ) : (
            <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
              <Trash2 size={12} />
              Delete
            </button>
          )}
          {canMutate && (
            <button onClick={handleScore} className={menuItemClass}>
              <Download size={12} className="rotate-180" />
              Recompute Score
            </button>
          )}
          <div className="my-1 border-t border-surface-200" />
          <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
            <Link size={12} />
            Copy Link
          </button>
        </>
      )}
    </div>,
    document.body,
  )
}
