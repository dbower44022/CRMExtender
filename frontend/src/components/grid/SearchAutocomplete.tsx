import { useState, useEffect, useCallback, useRef } from 'react'
import type { AutocompleteSuggestion } from '../../lib/searchParser.ts'
import type { FieldDef } from '../../types/api.ts'
import { getAutocompleteSuggestions } from '../../lib/searchParser.ts'

interface SearchAutocompleteProps {
  inputValue: string
  cursorPosition: number
  fields: Record<string, FieldDef>
  onAccept: (suggestion: AutocompleteSuggestion) => void
  onDismiss: () => void
  visible: boolean
}

export function SearchAutocomplete({
  inputValue,
  cursorPosition,
  fields,
  onAccept,
  onDismiss,
  visible,
}: SearchAutocompleteProps) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)

  const suggestions = visible
    ? getAutocompleteSuggestions(inputValue, cursorPosition, fields)
    : []

  // Reset selection when suggestions change
  useEffect(() => {
    setSelectedIndex(0)
  }, [inputValue, cursorPosition])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (suggestions.length === 0) return

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault()
          setSelectedIndex((prev) => Math.min(prev + 1, suggestions.length - 1))
          break
        case 'ArrowUp':
          e.preventDefault()
          setSelectedIndex((prev) => Math.max(prev - 1, 0))
          break
        case 'Enter':
        case 'Tab':
          if (suggestions.length > 0) {
            e.preventDefault()
            onAccept(suggestions[selectedIndex])
          }
          break
        case 'Escape':
          e.preventDefault()
          onDismiss()
          break
      }
    },
    [suggestions, selectedIndex, onAccept, onDismiss],
  )

  useEffect(() => {
    if (suggestions.length > 0 && visible) {
      document.addEventListener('keydown', handleKeyDown, true)
      return () => document.removeEventListener('keydown', handleKeyDown, true)
    }
  }, [suggestions.length, visible, handleKeyDown])

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const items = listRef.current.children
      if (items[selectedIndex]) {
        ;(items[selectedIndex] as HTMLElement).scrollIntoView({ block: 'nearest' })
      }
    }
  }, [selectedIndex])

  if (!visible || suggestions.length === 0) return null

  return (
    <div
      ref={listRef}
      className="absolute left-0 top-full z-50 mt-1 max-h-48 w-full overflow-auto rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg"
    >
      {suggestions.map((suggestion, index) => (
        <button
          key={`${suggestion.insertText}-${index}`}
          onMouseDown={(e) => {
            e.preventDefault() // Prevent input blur
            onAccept(suggestion)
          }}
          onMouseEnter={() => setSelectedIndex(index)}
          className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs ${
            index === selectedIndex
              ? 'bg-primary-50 text-primary-700'
              : 'text-surface-600 hover:bg-surface-50'
          }`}
        >
          <span className="font-medium">{suggestion.label}</span>
          {suggestion.description && (
            <span className="ml-auto text-surface-400">{suggestion.description}</span>
          )}
        </button>
      ))}
    </div>
  )
}
