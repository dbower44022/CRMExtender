import { format } from 'date-fns'

/**
 * Format a datetime string per PRD spec: "Feb 15, 2026 3:30 PM"
 * Always includes year and time — no smart "today" or "this year" shortcuts.
 */
export function formatTimestamp(isoString: string | null | undefined): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString

  return format(date, 'MMM d, yyyy h:mm a')
}

/**
 * Format a date-only string per PRD spec: "Feb 15, 2026"
 * No time component — use for pure date fields.
 */
export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString

  return format(date, 'MMM d, yyyy')
}
