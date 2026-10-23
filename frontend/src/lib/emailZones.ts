/** Split an email body into the new text and the quoted/forwarded remainder.
 *
 * Shared by the Communication full view and the Mail reading pane (MAIL-24).
 * Heuristics: client-specific containers (Gmail, Outlook), "On ... wrote:",
 * forwarded/original-message separators, and the first <blockquote>.
 */

export function splitEmailZones(html: string): { primaryHtml: string; quotedHtml: string | null } {
  // Text-based patterns (match inline text within the HTML)
  const textPatterns = [
    /On\s+.{5,80}\s+wrote:\s*/i,
    /-{5,}\s*Forwarded message\s*-{5,}/,
    /-{3,}\s*Original Message\s*-{3,}/,
  ]

  // HTML-structural patterns (match container elements used by email clients)
  const htmlPatterns = [
    /<div[^>]+\bid\s*=\s*["']?divRplyFwdMsg["']?[^>]*>/i,          // Outlook forward container
    /<div[^>]+\bid\s*=\s*["']?appendonsend["']?[^>]*>/i,           // Outlook Mobile cutoff
    /<div[^>]+class\s*=\s*["'][^"']*gmail_quote[^"']*["'][^>]*>/i, // Gmail quoted/forward
    /<div[^>]*border-top\s*:\s*solid[^>]*>/i,                      // Outlook styled separator
  ]

  let earliestIdx = -1

  for (const pattern of textPatterns) {
    const match = html.search(pattern)
    if (match !== -1 && (earliestIdx === -1 || match < earliestIdx)) {
      earliestIdx = match
    }
  }

  for (const pattern of htmlPatterns) {
    const match = html.search(pattern)
    if (match !== -1 && (earliestIdx === -1 || match < earliestIdx)) {
      earliestIdx = match
    }
  }

  const blockquoteIdx = html.search(/<blockquote[\s>]/i)
  if (blockquoteIdx !== -1 && (earliestIdx === -1 || blockquoteIdx < earliestIdx)) {
    earliestIdx = blockquoteIdx
  }

  if (earliestIdx === -1 || earliestIdx === 0) {
    return { primaryHtml: html, quotedHtml: null }
  }

  // Try to back up to a parent <div> wrapper (common in Outlook forwarding structure)
  const before = html.slice(Math.max(0, earliestIdx - 10), earliestIdx)
  const parentDiv = before.match(/<div>\s*$/)
  if (parentDiv) {
    earliestIdx -= parentDiv[0].length
  }

  const primaryHtml = html.slice(0, earliestIdx)

  // If primary zone has no meaningful text (e.g. a forward with no personal note),
  // treat the entire body as primary so the user sees content immediately
  const primaryText = primaryHtml
    .replace(/<style\b[^]*?<\/style\s*>/gi, '')
    .replace(/<title\b[^]*?<\/title\s*>/gi, '')
    .replace(/<[^>]*>/g, '')
    .replace(/&\w+;/g, ' ')
    .replace(/&#\d+;/g, ' ')
    .trim()
  if (primaryText.length === 0) {
    return { primaryHtml: html, quotedHtml: null }
  }

  return {
    primaryHtml,
    quotedHtml: html.slice(earliestIdx),
  }
}

