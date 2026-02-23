import {
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  addDays,
  addWeeks,
  addMonths,
  subDays,
  subWeeks,
  subMonths,
} from 'date-fns'
import type { FieldDef, QuickFilter } from '../types/api.ts'

export interface ParsedSearch {
  freeText: string
  fieldFilters: QuickFilter[]
}

type Fields = Record<string, FieldDef>

// Build a case-insensitive lookup from field key + label → field key
function buildFieldLookup(fields: Fields): Map<string, string> {
  const map = new Map<string, string>()
  for (const [key, def] of Object.entries(fields)) {
    if (def.type === 'hidden') continue
    map.set(key.toLowerCase(), key)
    map.set(def.label.toLowerCase(), key)
  }
  return map
}

// Tokenize input, respecting quoted strings
function tokenize(input: string): string[] {
  const tokens: string[] = []
  let current = ''
  let inQuote = false
  let quoteChar = ''

  for (let i = 0; i < input.length; i++) {
    const ch = input[i]

    if (inQuote) {
      if (ch === quoteChar) {
        inQuote = false
      } else {
        current += ch
      }
    } else if (ch === '"' || ch === "'") {
      inQuote = true
      quoteChar = ch
    } else if (ch === ' ') {
      if (current) {
        tokens.push(current)
        current = ''
      }
    } else {
      current += ch
    }
  }
  if (current) tokens.push(current)
  return tokens
}


function resolveRelativeDate(expr: string, now: Date): [string, string] | null {
  const lower = expr.toLowerCase().trim()

  switch (lower) {
    case 'today':
      return [startOfDay(now).toISOString(), endOfDay(now).toISOString()]
    case 'tomorrow':
      return [startOfDay(addDays(now, 1)).toISOString(), endOfDay(addDays(now, 1)).toISOString()]
    case 'yesterday':
      return [startOfDay(subDays(now, 1)).toISOString(), endOfDay(subDays(now, 1)).toISOString()]
    case 'this week':
      return [
        startOfWeek(now, { weekStartsOn: 1 }).toISOString(),
        endOfWeek(now, { weekStartsOn: 1 }).toISOString(),
      ]
    case 'last week': {
      const prev = subWeeks(now, 1)
      return [
        startOfWeek(prev, { weekStartsOn: 1 }).toISOString(),
        endOfWeek(prev, { weekStartsOn: 1 }).toISOString(),
      ]
    }
    case 'next week': {
      const next = addWeeks(now, 1)
      return [
        startOfWeek(next, { weekStartsOn: 1 }).toISOString(),
        endOfWeek(next, { weekStartsOn: 1 }).toISOString(),
      ]
    }
    case 'this month':
      return [startOfMonth(now).toISOString(), endOfMonth(now).toISOString()]
    case 'last month': {
      const prev = subMonths(now, 1)
      return [startOfMonth(prev).toISOString(), endOfMonth(prev).toISOString()]
    }
    case 'next month': {
      const next = addMonths(now, 1)
      return [startOfMonth(next).toISOString(), endOfMonth(next).toISOString()]
    }
    default: {
      // "last N days" / "next N days"
      const lastMatch = lower.match(/^last\s+(\d+)\s+days?$/)
      if (lastMatch) {
        const n = parseInt(lastMatch[1], 10)
        return [startOfDay(subDays(now, n)).toISOString(), endOfDay(now).toISOString()]
      }
      const nextMatch = lower.match(/^next\s+(\d+)\s+days?$/)
      if (nextMatch) {
        const n = parseInt(nextMatch[1], 10)
        return [startOfDay(now).toISOString(), endOfDay(addDays(now, n)).toISOString()]
      }
      return null
    }
  }
}

// Parse numeric comparison prefix: ">500", ">=100", "<50", "<=200", "=42"
function parseNumericValue(raw: string): { operator: string; value: string } | null {
  const m = raw.match(/^(>=|<=|>|<|=)(.+)$/)
  if (m) {
    const val = parseFloat(m[2])
    if (isNaN(val)) return null
    const opMap: Record<string, string> = {
      '>': 'gt',
      '<': 'lt',
      '>=': 'gte',
      '<=': 'lte',
      '=': 'equals',
    }
    return { operator: opMap[m[1]], value: String(val) }
  }
  // Plain number — treat as equals
  const val = parseFloat(raw)
  if (!isNaN(val)) return { operator: 'equals', value: String(val) }
  return null
}

// Multi-word lookahead tokens for date expressions
const MULTI_WORD_PREFIXES = ['this', 'last', 'next']

export function parseSearchQuery(input: string, fields: Fields): ParsedSearch {
  if (!input.trim()) return { freeText: '', fieldFilters: [] }

  const fieldLookup = buildFieldLookup(fields)
  const tokens = tokenize(input)
  const freeTextParts: string[] = []
  const fieldFilters: QuickFilter[] = []
  const now = new Date()

  let i = 0
  while (i < tokens.length) {
    const token = tokens[i]
    const colonIdx = token.indexOf(':')

    // Must have colon and something before it
    if (colonIdx > 0) {
      const fieldPart = token.substring(0, colonIdx).toLowerCase()
      let valuePart = token.substring(colonIdx + 1)

      const fieldKey = fieldLookup.get(fieldPart)
      if (fieldKey) {
        const fd = fields[fieldKey]

        if (fd.type === 'datetime') {
          // Multi-word lookahead for relative dates
          if (MULTI_WORD_PREFIXES.includes(valuePart.toLowerCase()) && i + 1 < tokens.length) {
            // Check if combining with next token makes a valid expression
            const combined = valuePart + ' ' + tokens[i + 1]
            // Also check for "last N days" / "next N days" (3 tokens)
            if (i + 2 < tokens.length) {
              const triple = combined + ' ' + tokens[i + 2]
              const tripleRange = resolveRelativeDate(triple, now)
              if (tripleRange) {
                fieldFilters.push({ field_key: fieldKey, operator: 'is_after', value: tripleRange[0] })
                fieldFilters.push({ field_key: fieldKey, operator: 'is_before', value: tripleRange[1] })
                i += 3
                continue
              }
            }
            const range = resolveRelativeDate(combined, now)
            if (range) {
              fieldFilters.push({ field_key: fieldKey, operator: 'is_after', value: range[0] })
              fieldFilters.push({ field_key: fieldKey, operator: 'is_before', value: range[1] })
              i += 2
              continue
            }
          }

          // Single-word date expressions
          const range = resolveRelativeDate(valuePart, now)
          if (range) {
            fieldFilters.push({ field_key: fieldKey, operator: 'is_after', value: range[0] })
            fieldFilters.push({ field_key: fieldKey, operator: 'is_before', value: range[1] })
            i++
            continue
          }

          // Fall through to ISO date string — use is_after/is_before for a day range
          if (/^\d{4}-\d{2}-\d{2}/.test(valuePart)) {
            const dayStart = startOfDay(new Date(valuePart)).toISOString()
            const dayEnd = endOfDay(new Date(valuePart)).toISOString()
            fieldFilters.push({ field_key: fieldKey, operator: 'is_after', value: dayStart })
            fieldFilters.push({ field_key: fieldKey, operator: 'is_before', value: dayEnd })
            i++
            continue
          }
        }

        if (fd.type === 'number') {
          const parsed = parseNumericValue(valuePart)
          if (parsed) {
            fieldFilters.push({ field_key: fieldKey, operator: parsed.operator, value: parsed.value })
            i++
            continue
          }
        }

        if (fd.type === 'select') {
          // Exact match for select fields
          if (valuePart) {
            fieldFilters.push({ field_key: fieldKey, operator: 'equals', value: valuePart })
            i++
            continue
          }
        }

        // Default for text fields: contains
        if (valuePart) {
          fieldFilters.push({ field_key: fieldKey, operator: 'contains', value: valuePart })
          i++
          continue
        }
      }
    }

    // Not a recognized field:value token — keep as free text
    freeTextParts.push(token)
    i++
  }

  return {
    freeText: freeTextParts.join(' '),
    fieldFilters,
  }
}

// --- Autocomplete suggestions ---

export interface AutocompleteSuggestion {
  type: 'field' | 'value'
  label: string
  // What to insert — replaces the current "word" in the input
  insertText: string
  // Display description
  description?: string
}

export function getAutocompleteSuggestions(
  input: string,
  cursorPos: number,
  fields: Fields,
): AutocompleteSuggestion[] {
  if (!input || cursorPos === 0) return []

  // Extract the "word" the cursor is in or just after
  const textUpToCursor = input.slice(0, cursorPos)

  // Find the start of the current word (split by space)
  const lastSpaceIdx = textUpToCursor.lastIndexOf(' ')
  const currentWord = textUpToCursor.slice(lastSpaceIdx + 1)

  if (!currentWord) return []

  const colonIdx = currentWord.indexOf(':')

  if (colonIdx === -1) {
    // No colon yet — suggest field names that match the partial word
    const partial = currentWord.toLowerCase()
    const suggestions: AutocompleteSuggestion[] = []
    const seen = new Set<string>()

    for (const [key, def] of Object.entries(fields)) {
      if (def.type === 'hidden') continue
      if (seen.has(key)) continue

      const keyMatch = key.toLowerCase().startsWith(partial)
      const labelMatch = def.label.toLowerCase().startsWith(partial)

      if (keyMatch || labelMatch) {
        seen.add(key)
        suggestions.push({
          type: 'field',
          label: def.label,
          insertText: key + ':',
          description: def.type,
        })
      }
    }

    return suggestions.slice(0, 8)
  }

  // Has colon — suggest values for the field
  const fieldPart = currentWord.slice(0, colonIdx).toLowerCase()
  const valuePart = currentWord.slice(colonIdx + 1).toLowerCase()

  // Resolve field key
  const fieldLookup = buildFieldLookup(fields)
  const fieldKey = fieldLookup.get(fieldPart)
  if (!fieldKey) return []

  const fd = fields[fieldKey]
  const prefix = currentWord.slice(0, colonIdx + 1) // e.g., "status:"

  if (fd.type === 'select' && fd.select_options) {
    return fd.select_options
      .filter((opt) => opt.toLowerCase().startsWith(valuePart))
      .map((opt) => ({
        type: 'value' as const,
        label: opt,
        insertText: prefix + (opt.includes(' ') ? `"${opt}"` : opt),
      }))
  }

  if (fd.type === 'datetime') {
    const dateKeywords = [
      'today',
      'tomorrow',
      'yesterday',
      'this week',
      'last week',
      'next week',
      'this month',
      'last month',
      'next month',
      'last 7 days',
      'last 30 days',
      'next 7 days',
    ]
    return dateKeywords
      .filter((kw) => kw.startsWith(valuePart))
      .map((kw) => ({
        type: 'value' as const,
        label: kw,
        insertText: prefix + kw,
      }))
  }

  if (fd.type === 'number') {
    if (!valuePart) {
      return [
        { type: 'value', label: '> (greater than)', insertText: prefix + '>' },
        { type: 'value', label: '< (less than)', insertText: prefix + '<' },
        { type: 'value', label: '>= (at least)', insertText: prefix + '>=' },
        { type: 'value', label: '<= (at most)', insertText: prefix + '<=' },
      ]
    }
  }

  return []
}
