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
