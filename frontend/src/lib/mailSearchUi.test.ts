import { describe, expect, it } from 'vitest'
import { loadSavedSearches, storeSavedSearches, tokenize } from './mailSearchUi.ts'

describe('mail search helpers (MAIL-31)', () => {
  it('marks operator tokens', () => {
    expect(tokenize('from:ada budget is:unread')).toEqual([
      { text: 'from:ada', op: true }, { text: ' ', op: false }, { text: 'budget', op: false },
      { text: ' ', op: false }, { text: 'is:unread', op: true },
    ])
  })
  it('persists saved searches in this browser', () => {
    localStorage.clear()
    expect(loadSavedSearches()).toEqual([])
    storeSavedSearches([{ name: 'Unread from Ada', query: 'from:ada is:unread' }])
    expect(loadSavedSearches()).toEqual([{ name: 'Unread from Ada', query: 'from:ada is:unread' }])
  })
})
