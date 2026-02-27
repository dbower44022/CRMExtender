import { format, isToday, isYesterday, isThisYear, differenceInCalendarDays } from 'date-fns'

/**
 * Contextual Date Formatting per GUI Functional Requirements PRD V3.1 Section 2.3:
 *
 * - Today:              "Today - Mar 10 - 2:30 PM"
 * - Yesterday:          "Yesterday - Mar 09 - 4:00 PM"
 * - 2–6 days ago:       "Tue Mar 08 - 5:30 PM" (abbreviated day name)
 * - 7+ days, this year: "Mar 01 - 7:30 AM"
 * - Previous year(s):   "Mar 01 2024 - 7:30 AM"
 */
export function formatTimestamp(isoString: string | null | undefined): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString

  const time = format(date, 'h:mm a')

  if (isToday(date)) {
    return `Today - ${format(date, 'MMM dd')} - ${time}`
  }
  if (isYesterday(date)) {
    return `Yesterday - ${format(date, 'MMM dd')} - ${time}`
  }
  const daysAgo = differenceInCalendarDays(new Date(), date)
  if (daysAgo >= 2 && daysAgo <= 6) {
    return `${format(date, 'EEE MMM dd')} - ${time}`
  }
  if (isThisYear(date)) {
    return `${format(date, 'MMM dd')} - ${time}`
  }
  return `${format(date, 'MMM dd yyyy')} - ${time}`
}

/**
 * Contextual Date Formatting for date-only fields (no time component)
 * per GUI Functional Requirements PRD V3.1 Section 2.3:
 *
 * - Today:              "Today - Mar 10"
 * - Yesterday:          "Yesterday - Mar 09"
 * - 2–6 days ago:       "Tue Mar 08"
 * - 7+ days, this year: "Mar 01"
 * - Previous year(s):   "Mar 01 2024"
 */
export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return isoString

  if (isToday(date)) {
    return `Today - ${format(date, 'MMM dd')}`
  }
  if (isYesterday(date)) {
    return `Yesterday - ${format(date, 'MMM dd')}`
  }
  const daysAgo = differenceInCalendarDays(new Date(), date)
  if (daysAgo >= 2 && daysAgo <= 6) {
    return format(date, 'EEE MMM dd')
  }
  if (isThisYear(date)) {
    return format(date, 'MMM dd')
  }
  return format(date, 'MMM dd yyyy')
}
