/** URL mapping between SPA state and /app/ paths (Legacy UI Migration PRD, Phase 0). */

import { PLURAL } from '../api/detail.ts'

const SINGULAR: Record<string, string> = Object.fromEntries(
  Object.entries(PLURAL).map(([singular, plural]) => [plural, singular]),
)

export interface AppRoute {
  entityType: string
  entityId: string | null
}

/** Build the /app/ path for an entity type and optional selected record. */
export function buildAppPath(entityType: string, entityId?: string | null): string {
  const plural = PLURAL[entityType] ?? `${entityType}s`
  return entityId ? `/app/${plural}/${entityId}` : `/app/${plural}`
}

/** Parse an /app/{plural}[/{id}] pathname. Returns null for anything else. */
export function parseAppPath(pathname: string): AppRoute | null {
  const m = pathname.match(/^\/app\/([^/]+)(?:\/([^/?#]+))?\/?$/)
  if (!m) return null
  const entityType = SINGULAR[m[1]]
  if (!entityType) return null
  return { entityType, entityId: m[2] ?? null }
}

// --- Mail surface (Mail Client PRD MAIL-21) ---------------------------------

export interface MailRoute {
  accountId: string
  folder: string
  threadId: string | null
}

/** /app/mail/{account|unified}/{folder}[/{thread}]; folder may be `label:<id>`. */
export function buildMailPath(accountId: string, folder: string, threadId?: string | null): string {
  const base = `/app/mail/${encodeURIComponent(accountId)}/${encodeURIComponent(folder)}`
  return threadId ? `${base}/${encodeURIComponent(threadId)}` : base
}

/** Parse a mail path. `/app/mail` alone means the unified inbox. */
export function parseMailPath(pathname: string): MailRoute | null {
  if (pathname === '/app/mail' || pathname === '/app/mail/') {
    return { accountId: 'unified', folder: 'inbox', threadId: null }
  }
  const m = pathname.match(/^\/app\/mail\/([^/]+)\/([^/]+)(?:\/([^/?#]+))?\/?$/)
  if (!m) return null
  return {
    accountId: decodeURIComponent(m[1]),
    folder: decodeURIComponent(m[2]),
    threadId: m[3] ? decodeURIComponent(m[3]) : null,
  }
}

/**
 * Interpret a legacy server-rendered detail URL (e.g. /contacts/{id}) as an
 * in-app route. Returns null when the href is not a legacy entity page.
 */
export function parseLegacyEntityHref(href: string): AppRoute | null {
  const m = href.match(/^\/([^/]+)\/([^/?#]+)\/?$/)
  if (!m) return null
  const entityType = SINGULAR[m[1]]
  if (!entityType) return null
  return { entityType, entityId: m[2] }
}
