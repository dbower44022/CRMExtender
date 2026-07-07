/** User date-display preferences (profile settings: timezone + date format).
 *
 * Module singleton set by AppShell once the profile loads; formatters in
 * formatTimestamp.ts read it on every call. timeZone null = browser local.
 */

export type DateFormatPref = 'ISO' | 'US' | 'EU'

interface DatePrefs {
  timeZone: string | null
  dateFormat: DateFormatPref
}

let prefs: DatePrefs = { timeZone: null, dateFormat: 'US' }

export function setDatePrefs(next: { timeZone?: string | null; dateFormat?: string }): void {
  prefs = {
    timeZone: next.timeZone !== undefined ? normalizeTz(next.timeZone) : prefs.timeZone,
    dateFormat: isDateFormat(next.dateFormat) ? next.dateFormat : prefs.dateFormat,
  }
}

export function getDatePrefs(): DatePrefs {
  return prefs
}

function isDateFormat(v: unknown): v is DateFormatPref {
  return v === 'ISO' || v === 'US' || v === 'EU'
}

function normalizeTz(tz: string | null): string | null {
  if (!tz || tz === 'UTC') return tz ?? null
  try {
    // Throws on invalid IANA names — fall back to browser local
    new Intl.DateTimeFormat('en-US', { timeZone: tz })
    return tz
  } catch {
    return null
  }
}
