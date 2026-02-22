import { useState, useRef, useEffect } from 'react'
import { useCellEdit } from '../../api/views.ts'
import type { FieldDef } from '../../types/api.ts'

interface InlineEditorProps {
  entityType: string
  entityId: string
  fieldKey: string
  fieldDef: FieldDef
  currentValue: string
  onClose: () => void
}

export function InlineEditor({
  entityType,
  entityId,
  fieldKey,
  fieldDef,
  currentValue,
  onClose,
}: InlineEditorProps) {
  const [value, setValue] = useState(currentValue)
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null)
  const cellEdit = useCellEdit()

  useEffect(() => {
    inputRef.current?.focus()
    if (inputRef.current instanceof HTMLInputElement) {
      inputRef.current.select()
    }
  }, [])

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
          flashCell('success')
          onClose()
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
    <input
      ref={inputRef as React.RefObject<HTMLInputElement>}
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={save}
      onKeyDown={handleKeyDown}
      className="h-full w-full border border-primary-400 bg-surface-0 px-1 text-sm outline-none"
    />
  )
}
