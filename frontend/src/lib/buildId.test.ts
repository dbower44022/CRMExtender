import { describe, expect, it } from 'vitest'
import { loadedBuildId, shouldReload } from './buildId.ts'

describe('buildId (v10.43)', () => {
  it('reads the bundle name from the page scripts', () => {
    const doc = document.implementation.createHTMLDocument('t')
    const s = doc.createElement('script'); s.setAttribute('src', '/app/assets/index-Cu-zHl_g.js'); doc.head.appendChild(s)
    expect(loadedBuildId(doc)).toBe('index-Cu-zHl_g')
    expect(loadedBuildId(document.implementation.createHTMLDocument('e'))).toBeNull()
  })

  it('reloads only on a real change and never over an open composer', () => {
    expect(shouldReload('index-a', 'index-b', false)).toBe(true)
    expect(shouldReload('index-a', 'index-a', false)).toBe(false)
    expect(shouldReload('index-a', 'index-b', true)).toBe(false)
    expect(shouldReload(null, 'index-b', false)).toBe(false)
    expect(shouldReload('index-a', null, false)).toBe(false)
  })
})
