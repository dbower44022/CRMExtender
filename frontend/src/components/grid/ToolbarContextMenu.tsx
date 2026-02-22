import { useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import {
  PanelLeft,
  Columns3,
  Filter,
  ArrowUpDown,
  Group,
  Settings2,
} from 'lucide-react'

const menuItemClass =
  'flex w-full items-center gap-2 px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50 cursor-pointer'

interface ToolbarContextMenuProps {
  x: number
  y: number
  onClose: () => void
  onAction: (action: string) => void
}

export function ToolbarContextMenu({ x, y, onClose, onAction }: ToolbarContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  const adjustedX = Math.min(x, window.innerWidth - 200)
  const adjustedY = Math.min(y, window.innerHeight - 250)

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[180px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg"
      style={{ left: adjustedX, top: adjustedY }}
    >
      <button className={menuItemClass} onClick={() => onAction('view')}>
        <PanelLeft size={12} /> Edit View
      </button>
      <div className="my-1 border-t border-surface-200" />
      <button className={menuItemClass} onClick={() => onAction('columns')}>
        <Columns3 size={12} /> Edit Columns
      </button>
      <button className={menuItemClass} onClick={() => onAction('filters')}>
        <Filter size={12} /> Edit Filters
      </button>
      <button className={menuItemClass} onClick={() => onAction('sorting')}>
        <ArrowUpDown size={12} /> Edit Sorting
      </button>
      <button className={menuItemClass} onClick={() => onAction('grouping')}>
        <Group size={12} /> Edit Grouping
      </button>
      <div className="my-1 border-t border-surface-200" />
      <button className={menuItemClass} onClick={() => onAction('display')}>
        <Settings2 size={12} /> Edit Grid Display
      </button>
    </div>,
    document.body,
  )
}
