import { useEffect, useRef } from 'react'
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
  selectedRowIds,
  onClose,
  onOpenDetail,
  onOpenModal,
  onEdit,
}: RowContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

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
          <button onClick={() => { comingSoon(); onClose() }} className={menuItemClass}>
            <Trash2 size={12} />
            Delete
          </button>
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
