import { describe, expect, it } from 'vitest'
import { allowSender, allowedSenders, buildFrameDocument, sanitizeMailHtml } from './mailRender.ts'

describe('sanitizeMailHtml (MAIL-25)', () => {
  it('strips scripts, handlers, forms, and javascript: links', () => {
    const r = sanitizeMailHtml(
      '<p onclick="x()">hi</p><script>alert(1)</script><form><input></form><a href="javascript:evil()">l</a><iframe src="x"></iframe>',
      true,
    )
    expect(r.html).not.toMatch(/script|onclick|<form|<input|<iframe|javascript:/i)
    expect(r.html).toContain('hi')
  })

  it('blocks remote images until allowed and counts them', () => {
    const html = '<img src="https://t.example/pixel.gif"><img src="cid:logo1"><div style="background:url(https://x/y.png)">x</div>'
    const blocked = sanitizeMailHtml(html, false)
    expect(blocked.blockedImages).toBe(1)
    expect(blocked.html).toContain('data-crm-src="https://t.example/pixel.gif"')
    expect(blocked.html).not.toContain('url(https://x/y.png)')
    expect(blocked.html).toContain('cid:logo1')
    const allowed = sanitizeMailHtml(html, true)
    expect(allowed.blockedImages).toBe(0)
    expect(allowed.html).toContain('src="https://t.example/pixel.gif"')
  })

  it('keeps mailto and https links but drops target', () => {
    const r = sanitizeMailHtml('<a href="https://a.test" target="_blank">a</a><a href="mailto:x@y.z">m</a>', true)
    expect(r.html).toContain('href="https://a.test"')
    expect(r.html).toContain('href="mailto:x@y.z"')
    expect(r.html).not.toContain('target=')
  })
})

describe('buildFrameDocument', () => {
  it('wraps with a CSP, the frame script, and resolves cid: to the attachment route', () => {
    const doc = buildFrameDocument('<img src="cid:abc@x">', 'f1', { cidBase: '/api/v1/mail/attachments/cid/m1/' })
    expect(doc).toContain('Content-Security-Policy')
    expect(doc).toContain("default-src 'none'")
    expect(doc).toContain('src="/api/v1/mail/attachments/cid/m1/abc%40x"')
    expect(doc).toContain('var FRAME_ID="f1"')
  })

  it('never scrolls vertically inside the frame and keeps light controls', () => {
    const doc = buildFrameDocument('<p>x</p>', 'f2')
    expect(doc).toContain('html{overflow-y:hidden;overflow-x:auto;}')
    expect(doc).toContain('<meta name="color-scheme" content="light">')
    expect(doc).toContain('getBoundingClientRect')
  })
})

describe('per-sender allow list', () => {
  it('persists in localStorage', () => {
    localStorage.clear()
    expect(allowedSenders().size).toBe(0)
    allowSender('Ada@Example.com')
    expect(allowedSenders().has('ada@example.com')).toBe(true)
  })
})
