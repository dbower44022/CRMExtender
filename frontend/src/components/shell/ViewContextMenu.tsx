import { useRef, useEffect } from 'react'
import { Copy, Pencil, Trash2 } from 'lucide-react'

interface ViewContextMenuProps {
  x: number
  y: number
  isDefault: boolean
  onRename: () => void
  onDuplicate: () => void
  onDelete: () => void
  onClose: () => void
}

export function ViewContextMenu({
  x,
  y,
  isDefault,
  onRename,
  onDuplicate,
  onDelete,
  onClose,
}: ViewContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="fixed z-50 min-w-[140px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg"
      style={{ left: x, top: y }}
    >
      <button
        onClick={onRename}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-surface-700 hover:bg-surface-100"
      >
        <Pencil size={13} />
        Rename
      </button>
      <button
        onClick={onDuplicate}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-surface-700 hover:bg-surface-100"
      >
        <Copy size={13} />
        Duplicate
      </button>
      {!isDefault && (
        <button
          onClick={onDelete}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-red-600 hover:bg-red-50"
        >
          <Trash2 size={13} />
          Delete
        </button>
      )}
    </div>
  )
}
