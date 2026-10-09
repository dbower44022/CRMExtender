import { describe, expect, it } from 'vitest'
import { buildMailPath, parseMailPath } from './appRoutes.ts'
import { splitEmailZones } from './emailZones.ts'

describe('mail routes (MAIL-21)', () => {
  it('round-trips account, folder, and thread', () => {
    const p = buildMailPath('acct-1', 'label:L 7', 't/1')
    expect(p).toBe('/app/mail/acct-1/label%3AL%207/t%2F1')
    expect(parseMailPath(p)).toEqual({ accountId: 'acct-1', folder: 'label:L 7', threadId: 't/1' })
  })
  it('bare /app/mail is the unified inbox', () => {
    expect(parseMailPath('/app/mail')).toEqual({ accountId: 'unified', folder: 'inbox', threadId: null })
    expect(parseMailPath('/app/contacts')).toBeNull()
  })
})

describe('splitEmailZones (MAIL-24)', () => {
  it('splits at a Gmail quote container and keeps the new text', () => {
    const z = splitEmailZones('<div>Thanks!</div><div class="gmail_quote">On Mon, Ada wrote:<blockquote>old</blockquote></div>')
    expect(z.primaryHtml).toBe('<div>Thanks!</div>')
    expect(z.quotedHtml).toContain('gmail_quote')
  })
  it('keeps everything primary when nothing precedes the quote', () => {
    const z = splitEmailZones('<blockquote>only quoted</blockquote>')
    expect(z.quotedHtml).toBeNull()
  })
})
