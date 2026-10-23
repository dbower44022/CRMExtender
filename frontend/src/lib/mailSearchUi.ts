/** Mail search box helpers (MAIL-31): saved searches (per browser) and operator tokenizing. */

export interface SavedSearch { name: string; query: string }
const SAVED_KEY = 'crm.mail.savedSearches'

export function loadSavedSearches(): SavedSearch[] {
  try {
    const raw = localStorage.getItem(SAVED_KEY)
    return raw ? (JSON.parse(raw) as SavedSearch[]) : []
  } catch {
    return []
  }
}

export function storeSavedSearches(list: SavedSearch[]): void {
  try {
    localStorage.setItem(SAVED_KEY, JSON.stringify(list))
  } catch {
    /* storage unavailable */
  }
}

/** Highlight operator tokens in a query for the hint line. */
export function tokenize(q: string): { text: string; op: boolean }[] {
  return q.split(/(\s+)/).filter((t) => t.length > 0).map((t) => ({ text: t, op: /^[a-z_]+:\S*/i.test(t) }))
}
