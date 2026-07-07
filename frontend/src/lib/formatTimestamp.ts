import { getDatePrefs, type DateFormatPref } from './datePrefs.ts'

/**
 * Contextual Date Formatting per GUI Functional Requirements PRD V3.1
 * Section 2.3, rendered in the user's preferred timezone with the date
 * portion following the profile date-format preference (ISO / US / EU):
 *
 * - Today:              "Today - Mar 10 - 2:30 PM"
 * - Yesterday:          "Yesterday - Mar 09 - 4:00 PM"
 * - 2–6 days ago:       "Tue Mar 08 - 5:30 PM" (abbreviated day name)
 * - 7+ days, this year: "Mar 01 - 7:30 AM"
 * - Previous year(s):   "Mar 01 2024 - 7:30 AM"
 *
 * (Examples shown in US format; ISO renders "03-01" / "2024-03-01",
 * EU renders "01 Mar" / "01 Mar 2024".)
 */

interface ZonedParts {
  year: number
  month: number // 1-12
  day: number
  monthShort: string
  weekdayShort: string
  time: string // "2:30 PM"
}

const MONTH_NUM: Record<string, number> = {
  Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6,
  Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12,
}

function zonedParts(date: Date): ZonedParts {
  const { timeZone } = getDatePrefs()
  const opts: Intl.DateTimeFormatOptions = {
    year: 'numeric', month: 'short', day: '2-digit', weekday: 'short',
    hour: 'numeric', minute: '2-digit', hour12: true,
  }
  if (timeZone) opts.timeZone = timeZone
  const parts = new Intl.DateTimeFormat('en-US', opts).formatToParts(date)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  const monthShort = get('month')
  return {
    year: Number(get('year')),
    month: MONTH_NUM[monthShort] ?? 0,
    day: Number(get('day')),
    monthShort,
    weekdayShort: get('weekday'),
    time: `${get('hour')}:${get('minute')} ${get('dayPeriod')}`,
  }
}

/** Whole days between two zoned calendar dates (a - b). */
function calendarDaysBetween(a: ZonedParts, b: ZonedParts): number {
  return Math.round(
    (Date.UTC(a.year, a.month - 1, a.day) - Date.UTC(b.year, b.month - 1, b.day)) / 86_400_000,
  )
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Date portion without year, per format preference. */
function shortDate(p: ZonedParts, fmt: DateFormatPref): string {
  if (fmt === 'ISO') return `${pad(p.month)}-${pad(p.day)}`
  if (fmt === 'EU') return `${pad(p.day)} ${p.monthShort}`
  return `${p.monthShort} ${pad(p.day)}`
}

/** Date portion with year, per format preference. */
function fullDate(p: ZonedParts, fmt: DateFormatPref): string {
  if (fmt === 'ISO') return `${p.year}-${pad(p.month)}-${pad(p.day)}`
  if (fmt === 'EU') return `${pad(p.day)} ${p.monthShort} ${p.year}`
  return `${p.monthShort} ${pad(p.day)} ${p.year}`
}

interface ContextualDate {
  datePart: string
  time: string
}

function contextualDate(isoString: string): ContextualDate | null {
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return null
  const { dateFormat } = getDatePrefs()
  const p = zonedParts(date)
  const now = zonedParts(new Date())
  const daysAgo = calendarDaysBetween(now, p)

  let datePart: string
  if (daysAgo === 0) {
    datePart = `Today - ${shortDate(p, dateFormat)}`
  } else if (daysAgo === 1) {
    datePart = `Yesterday - ${shortDate(p, dateFormat)}`
  } else if (daysAgo >= 2 && daysAgo <= 6) {
    datePart = `${p.weekdayShort} ${shortDate(p, dateFormat)}`
  } else if (p.year === now.year) {
    datePart = shortDate(p, dateFormat)
  } else {
    datePart = fullDate(p, dateFormat)
  }
  return { datePart, time: p.time }
}

export function formatTimestamp(isoString: string | null | undefined): string {
  if (!isoString) return ''
  const ctx = contextualDate(isoString)
  if (!ctx) return isoString
  return `${ctx.datePart} - ${ctx.time}`
}

export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return ''
  const ctx = contextualDate(isoString)
  if (!ctx) return isoString
  return ctx.datePart
}

/**
 * Two-line timestamp: returns { datePart, timePart } for stacked rendering.
 * Uses the same contextual date rules as formatTimestamp.
 */
export function formatTimestampTwoLine(
  isoString: string | null | undefined,
): { datePart: string; timePart: string } | null {
  if (!isoString) return null
  const ctx = contextualDate(isoString)
  if (!ctx) return null
  return { datePart: ctx.datePart, timePart: ctx.time }
}

/**
 * Compact timestamp for Preview Cards per Communication View PRD Section 4.4:
 * - Today:      time only ("2:30 PM")
 * - This year:  "Feb 21, 2:30 PM"
 * - Older:      "Feb 21, 2025 2:30 PM"  (date portion follows preference)
 */
export function formatPreviewTimestamp(isoString: string | null | undefined): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString
  const { dateFormat } = getDatePrefs()
  const p = zonedParts(date)
  const now = zonedParts(new Date())
  if (calendarDaysBetween(now, p) === 0) return p.time
  if (p.year === now.year) return `${shortDate(p, dateFormat)}, ${p.time}`
  return `${fullDate(p, dateFormat)} ${p.time}`
}
