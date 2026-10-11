/** Snooze return times (Mail Client KP-MAIL-06; MAIL-28).
 *
 * The picker offers later today, tomorrow, this weekend, next week, and a
 * custom date and time. Preset times are in the viewer's local clock:
 * 6 pm for later today, 8 am for the others.
 */

export interface SnoozeOption {
  key: 'later_today' | 'tomorrow' | 'weekend' | 'next_week'
  label: string
  /** ISO 8601 with offset, as the API's payload.return_at expects. */
  at: string
}

const MORNING = 8
const EVENING = 18

function at(base: Date, hour: number): Date {
  const d = new Date(base)
  d.setHours(hour, 0, 0, 0)
  return d
}

function addDays(base: Date, n: number): Date {
  const d = new Date(base)
  d.setDate(d.getDate() + n)
  return d
}

export function snoozeOptions(now: Date = new Date()): SnoozeOption[] {
  const out: SnoozeOption[] = []
  const evening = at(now, EVENING)
  if (evening.getTime() - now.getTime() >= 60 * 60 * 1000) {
    out.push({ key: 'later_today', label: 'Later today', at: evening.toISOString() })
  }
  out.push({ key: 'tomorrow', label: 'Tomorrow', at: at(addDays(now, 1), MORNING).toISOString() })
  // Saturday 8 am; from Saturday or Sunday that means the following Saturday.
  const day = now.getDay() // 0 Sunday … 6 Saturday
  const toSaturday = day === 6 ? 7 : day === 0 ? 6 : 6 - day
  out.push({ key: 'weekend', label: 'This weekend', at: at(addDays(now, toSaturday), MORNING).toISOString() })
  const toMonday = day === 0 ? 1 : 8 - day
  out.push({ key: 'next_week', label: 'Next week', at: at(addDays(now, toMonday), MORNING).toISOString() })
  return out
}

/** Value for a datetime-local input: local wall time, minute precision. */
export function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Parse a datetime-local value; null when empty, invalid, or not after `now`. */
export function fromLocalInputValue(value: string, now: Date = new Date()): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime()) || d.getTime() <= now.getTime()) return null
  return d.toISOString()
}

/** "Tomorrow 8:00 AM", "Sat 8:00 AM", "Oct 20, 8:00 AM" for chips and toasts. */
export function describeReturn(iso: string, now: Date = new Date()): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  const dayDiff = Math.round((at(d, 0).getTime() - at(now, 0).getTime()) / 86_400_000)
  if (dayDiff === 0) return `Today ${time}`
  if (dayDiff === 1) return `Tomorrow ${time}`
  if (dayDiff > 1 && dayDiff < 7) return `${d.toLocaleDateString([], { weekday: 'short' })} ${time}`
  const sameYear = d.getFullYear() === now.getFullYear()
  return `${d.toLocaleDateString([], sameYear ? { month: 'short', day: 'numeric' } : { year: 'numeric', month: 'short', day: 'numeric' })}, ${time}`
}
