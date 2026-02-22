import { useState, useRef, useEffect } from 'react'
import { useCellEdit } from '../../api/views.ts'
import { Loader2, Check } from 'lucide-react'
import type { FieldDef } from '../../types/api.ts'

interface InlineEditorProps {
  entityType: string
  entityId: string
  fieldKey: string
  fieldDef: FieldDef
  currentValue: string
  initialChars?: string
  onClose: () => void
}

export function InlineEditor({
  entityType,
  entityId,
  fieldKey,
  fieldDef,
  currentValue,
  initialChars,
  onClose,
}: InlineEditorProps) {
  const [value, setValue] = useState(initialChars ?? currentValue)
  const [showCheck, setShowCheck] = useState(false)
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null)
  const cellEdit = useCellEdit()

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.focus()
    if (el instanceof HTMLInputElement) {
      if (initialChars) {
        // Position cursor at end of initial chars
        el.setSelectionRange(initialChars.length, initialChars.length)
      } else {
        el.select()
      }
    }
  }, [initialChars])

  const save = () => {
    if (value === currentValue) {
      onClose()
      return
    }
    cellEdit.mutate(
      {
        entity_type: entityType,
        entity_id: entityId,
        field_key: fieldKey,
        value,
      },
      {
        onSuccess: () => {
          setShowCheck(true)
          setTimeout(() => {
            flashCell('success')
            onClose()
          }, 300)
        },
        onError: () => {
          flashCell('error')
          onClose()
        },
      },
    )
  }

  const flashCell = (type: 'success' | 'error') => {
    const cell = document.querySelector(
      `[data-edit-cell="${entityId}-${fieldKey}"]`,
    )
    if (!cell) return
    const cls = type === 'success' ? 'cell-flash-success' : 'cell-flash-error'
    cell.classList.add(cls)
    setTimeout(() => cell.classList.remove(cls), 600)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      save()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
    e.stopPropagation()
  }

  if (fieldDef.select_options) {
    return (
      <select
        ref={inputRef as React.RefObject<HTMLSelectElement>}
        value={value}
        onChange={(e) => {
          setValue(e.target.value)
          // Auto-save on select change
          setTimeout(() => {
            cellEdit.mutate(
              {
                entity_type: entityType,
                entity_id: entityId,
                field_key: fieldKey,
                value: e.target.value,
              },
              {
                onSuccess: () => {
                  flashCell('success')
                  onClose()
                },
                onError: () => {
                  flashCell('error')
                  onClose()
                },
              },
            )
          }, 0)
        }}
        onBlur={onClose}
        onKeyDown={handleKeyDown}
        className="h-full w-full border border-primary-400 bg-surface-0 px-1 text-sm outline-none"
      >
        <option value="">--</option>
        {fieldDef.select_options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    )
  }

  return (
    <div className="relative flex items-center">
      <input
        ref={inputRef as React.RefObject<HTMLInputElement>}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        onKeyDown={handleKeyDown}
        className="h-full w-full border border-primary-400 bg-surface-0 px-1 pr-6 text-sm outline-none"
      />
      {cellEdit.isPending && (
        <Loader2
          size={12}
          className="absolute right-1 animate-spin text-primary-500"
        />
      )}
      {showCheck && (
        <Check
          size={12}
          className="absolute right-1 text-green-500"
        />
      )}
    </div>
  )
}
