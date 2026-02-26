import { useState, useRef, useEffect } from 'react'
import { X } from 'lucide-react'
import { useGlobalSearch } from '../../api/search.ts'
import type { Recipient } from '../../api/outbound.ts'

interface RecipientFieldProps {
  label: string
  recipients: Recipient[]
  onChange: (recipients: Recipient[]) => void
  placeholder?: string
}

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function RecipientField({ label, recipients, onChange, placeholder }: RecipientFieldProps) {
  const [inputValue, setInputValue] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [highlightIndex, setHighlightIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const { data: searchResults } = useGlobalSearch(inputValue, {
    entityType: 'contact',
    limit: 6,
  })

  const contactResults = searchResults?.groups?.[0]?.results ?? []

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const addRecipient = (recipient: Recipient) => {
    // Avoid duplicates by email
    if (recipients.some((r) => r.email === recipient.email)) return
    onChange([...recipients, recipient])
    setInputValue('')
    setShowDropdown(false)
    setHighlightIndex(-1)
  }

  const removeRecipient = (index: number) => {
    onChange(recipients.filter((_, i) => i !== index))
  }

  const commitFreeformEmail = () => {
    const trimmed = inputValue.trim()
    if (!trimmed) return
    if (EMAIL_REGEX.test(trimmed)) {
      addRecipient({ email: trimmed })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      if (highlightIndex >= 0 && highlightIndex < contactResults.length) {
        const contact = contactResults[highlightIndex]
        if (contact.subtitle) {
          addRecipient({
            email: contact.subtitle,
            contact_id: contact.id,
            name: contact.name,
          })
        }
      } else {
        commitFreeformEmail()
      }
    } else if (e.key === 'Backspace' && inputValue === '' && recipients.length > 0) {
      removeRecipient(recipients.length - 1)
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIndex((prev) =>
        prev < contactResults.length - 1 ? prev + 1 : prev,
      )
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIndex((prev) => (prev > 0 ? prev - 1 : -1))
    } else if (e.key === 'Escape') {
      setShowDropdown(false)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-start gap-2">
        <label className="shrink-0 pt-1.5 text-sm font-medium text-surface-500">
          {label}:
        </label>
        <div
          className="flex min-h-[34px] flex-1 flex-wrap items-center gap-1 rounded border border-surface-200 bg-white px-2 py-1 focus-within:border-primary-400 focus-within:ring-1 focus-within:ring-primary-400"
          onClick={() => inputRef.current?.focus()}
        >
          {recipients.map((r, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-2.5 py-0.5 text-xs text-primary-700"
            >
              <span className="max-w-[200px] truncate">
                {r.name || r.email}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removeRecipient(i)
                }}
                className="ml-0.5 rounded-full p-0.5 hover:bg-primary-100"
              >
                <X size={10} />
              </button>
            </span>
          ))}
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value)
              setShowDropdown(true)
              setHighlightIndex(-1)
            }}
            onFocus={() => {
              if (inputValue.length >= 2) setShowDropdown(true)
            }}
            onBlur={() => {
              // Delay to allow click on dropdown items
              setTimeout(() => commitFreeformEmail(), 150)
            }}
            onKeyDown={handleKeyDown}
            placeholder={recipients.length === 0 ? (placeholder ?? 'Type name or email...') : ''}
            className="min-w-[120px] flex-1 border-none bg-transparent py-0.5 text-sm text-surface-800 outline-none placeholder:text-surface-400"
          />
        </div>
      </div>

      {/* Autocomplete dropdown */}
      {showDropdown && contactResults.length > 0 && inputValue.length >= 2 && (
        <div className="absolute left-[60px] right-0 z-50 mt-1 max-h-[200px] overflow-y-auto rounded-lg border border-surface-200 bg-white shadow-lg">
          {contactResults.map((contact, index) => (
            <button
              key={contact.id}
              type="button"
              className={`flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-surface-50 ${
                index === highlightIndex ? 'bg-surface-50' : ''
              }`}
              onMouseDown={(e) => {
                e.preventDefault() // prevent blur
                if (contact.subtitle) {
                  addRecipient({
                    email: contact.subtitle,
                    contact_id: contact.id,
                    name: contact.name,
                  })
                }
              }}
            >
              <div className="min-w-0 flex-1">
                <div className="font-medium text-surface-800">{contact.name}</div>
                {contact.subtitle && (
                  <div className="text-xs text-surface-500">{contact.subtitle}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
