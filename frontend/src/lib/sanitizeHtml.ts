/** Sanitize email HTML for safe inline rendering within the app's DOM. */
export function sanitizeHtml(rawHtml: string): string {
  let html = rawHtml
  // Remove <script> tags and contents
  html = html.replace(/<script\b[^]*?<\/script\s*>/gi, '')
  // Remove event handler attributes (onclick, onerror, onload, etc.)
  html = html.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '')
  // Remove javascript: URLs
  html = html.replace(/href\s*=\s*"javascript:[^"]*"/gi, 'href="#"')
  html = html.replace(/href\s*=\s*'javascript:[^']*'/gi, "href='#'")
  // Remove @font-face blocks (CORS failures from external font loads)
  html = html.replace(/@font-face\s*\{[^}]*\}/gi, '')
  // Remove <base> tags — email base href hijacks all relative URL resolution on the page (API fetches, links)
  html = html.replace(/<base\b[^>]*\/?>/gi, '')
  // Remove <meta> tags — email meta (charset, Content-Type with ";") conflicts with page-level parsing
  html = html.replace(/<meta\b[^>]*\/?>/gi, '')
  // Remove <link> tags — email preload/stylesheet links cause unused-resource warnings and CORS errors
  html = html.replace(/<link\b[^>]*\/?>/gi, '')
  // Remove cid: URL references — Content-ID scheme only works in email clients, causes ERR_UNKNOWN_URL_SCHEME
  html = html.replace(/\s(?:src|href)\s*=\s*["']cid:[^"']*["']/gi, '')
  // Remove tracking pixel images (1x1 or hidden) — prevents ERR_BLOCKED_BY_CLIENT from ad blockers
  html = html.replace(/<img\b[^>]*\b(?:width|height)\s*=\s*["']?1(?:px)?["']?[^>]*\/?>/gi, '')
  html = html.replace(/<img\b[^>]*style\s*=\s*["'][^"']*(?:display\s*:\s*none|visibility\s*:\s*hidden)[^"']*["'][^>]*\/?>/gi, '')
  // Remove known tracking pixel URLs and common spacer/beacon image filenames
  html = html.replace(/<img\b[^>]*\bsrc\s*=\s*["'][^"']*(?:\/open[?.]|\/track[?.]|email_open_log|\/pixel[?.]|\/beacon[?.]|\.gif\?|\/transparent\.gif|\/spacer\.gif|\/blank\.gif|\/clear\.gif)[^"']*["'][^>]*\/?>/gi, '')
  return html
}
