/** Isolated rendering of mail bodies (Mail Client PRD MAIL-25; TDD D-08).
 *
 * Pipeline: DOMPurify strips scripts, handlers, forms, and dangerous
 * URLs; remote images are rewritten to a placeholder unless the viewer
 * allowed them (per message or per sender); the result is wrapped in a
 * srcdoc document with a strict Content Security Policy and rendered in
 * a sandboxed <iframe> with an opaque origin, so mail CSS and markup can
 * never touch the application. A small script inside the frame reports
 * its height and relays link clicks to the parent, which opens them in
 * a new tab.
 */

import DOMPurify from 'dompurify'

export const FRAME_MESSAGE_TYPE = 'crm-mail-frame'
const PLACEHOLDER_ATTR = 'data-crm-src'

/** 1×1 transparent GIF used in place of blocked remote images. */
const BLOCKED_IMG = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'

export interface RenderResult {
  html: string
  blockedImages: number
}

function isRemote(url: string): boolean {
  const u = url.trim().toLowerCase()
  return u.startsWith('http://') || u.startsWith('https://') || u.startsWith('//')
}

/** Sanitize a mail body and, unless `allowRemote`, neutralize remote images. */
export function sanitizeMailHtml(html: string, allowRemote: boolean): RenderResult {
  let blocked = 0
  const hook = (node: Element) => {
    if (node.tagName === 'IMG') {
      const src = node.getAttribute('src') || ''
      const srcset = node.getAttribute('srcset')
      if (srcset) node.removeAttribute('srcset')
      if (isRemote(src) && !allowRemote) {
        node.setAttribute(PLACEHOLDER_ATTR, src)
        node.setAttribute('src', BLOCKED_IMG)
        node.setAttribute('alt', node.getAttribute('alt') || 'blocked image')
        blocked += 1
      }
    }
    // Inline CSS background images are another remote-load vector
    const style = node.getAttribute && node.getAttribute('style')
    if (style && /url\s*\(/i.test(style) && !allowRemote) {
      node.setAttribute('style', style.replace(/url\s*\([^)]*\)/gi, 'none'))
    }
  }
  DOMPurify.addHook('afterSanitizeAttributes', hook)
  try {
    const clean = DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ['form', 'input', 'button', 'select', 'textarea', 'iframe', 'object', 'embed', 'base', 'meta', 'link'],
      FORBID_ATTR: ['target', 'formaction'],
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel|cid|data):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
      ADD_ATTR: [PLACEHOLDER_ATTR],
    })
    return { html: String(clean), blockedImages: blocked }
  } finally {
    DOMPurify.removeHook('afterSanitizeAttributes')
  }
}

/** The script that runs inside the frame: height reports and link relay. */
const FRAME_SCRIPT = `
(function () {
  var last = 0;
  function report() {
    // Measure the content, not the viewport: scrollHeight is never below the
    // frame's own height, which would grow the frame by its margin forever.
    var body = document.body;
    var h = body ? Math.ceil(body.getBoundingClientRect().height) : 0;
    if (!h) { h = document.documentElement.scrollHeight; }
    // A horizontal scrollbar (wide promotional layouts) takes height from the
    // viewport; add its thickness so the content never needs a vertical one.
    var root = document.documentElement;
    if (root.scrollWidth > root.clientWidth) { h += Math.max(0, window.innerHeight - root.clientHeight); }
    if (h !== last) { last = h; parent.postMessage({ type: '${FRAME_MESSAGE_TYPE}', kind: 'height', id: FRAME_ID, height: h }, '*'); }
  }
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    e.preventDefault();
    parent.postMessage({ type: '${FRAME_MESSAGE_TYPE}', kind: 'link', id: FRAME_ID, href: a.getAttribute('href') }, '*');
  }, true);
  window.addEventListener('load', report);
  window.addEventListener('resize', report);
  if (window.ResizeObserver) {
    var ro = new ResizeObserver(report);
    ro.observe(document.documentElement);
    if (document.body) { ro.observe(document.body); }
  }
  setTimeout(report, 50); setTimeout(report, 500);
})();
`

/** Build the srcdoc for one body. `cidBase` resolves cid: images to the attachment route. */
export function buildFrameDocument(bodyHtml: string, frameId: string, opts: { cidBase?: string } = {}): string {
  let html = bodyHtml
  if (opts.cidBase) {
    html = html.replace(/src=(["'])cid:([^"']+)\1/gi, (_m, q, id) => `src=${q}${opts.cidBase}${encodeURIComponent(id)}${q}`)
  }
  const csp = [
    "default-src 'none'",
    "img-src data: blob: http: https:",
    "style-src 'unsafe-inline'",
    "font-src data: https:",
    "script-src 'unsafe-inline'",
    "form-action 'none'",
    "base-uri 'none'",
  ].join('; ')
  return (
    '<!doctype html><html><head><meta charset="utf-8">' +
    `<meta http-equiv="Content-Security-Policy" content="${csp}">` +
    // Light controls and scrollbars whatever the desktop theme (a dark GTK
    // theme painted the frame's scrollbar as a black bar, 10-11-26).
    '<meta name="color-scheme" content="light">' +
    '<style>' +
    'html,body{margin:0;padding:0;background:transparent;color:#1f2326;}' +
    // The reading pane scrolls; the frame never shows a vertical scrollbar.
    // Wide layouts may scroll sideways inside the frame.
    'html{overflow-y:hidden;overflow-x:auto;}' +
    'body{font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;word-wrap:break-word;overflow-wrap:anywhere;padding:1px 0;}' +
    'img{max-width:100%;height:auto;}' +
    'blockquote{margin:0 0 0 .5em;padding-left:.75em;border-left:2px solid #d8d3c6;color:#5d6670;}' +
    'pre{white-space:pre-wrap;}' +
    'table{max-width:100%;}' +
    '</style></head><body>' +
    html +
    `<script>var FRAME_ID=${JSON.stringify(frameId)};${FRAME_SCRIPT}</script>` +
    '</body></html>'
  )
}

// ---------------------------------------------------------------------------
// Per-sender remote-image allow list (per viewer, in this browser; MAIL-25 V1)
// ---------------------------------------------------------------------------

const ALLOW_KEY = 'crm.mail.remoteImageSenders'

export function allowedSenders(): Set<string> {
  try {
    const raw = localStorage.getItem(ALLOW_KEY)
    return new Set(raw ? (JSON.parse(raw) as string[]) : [])
  } catch {
    return new Set()
  }
}

export function allowSender(address: string): void {
  try {
    const set = allowedSenders()
    set.add(address.toLowerCase())
    localStorage.setItem(ALLOW_KEY, JSON.stringify([...set]))
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
}
