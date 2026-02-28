/**
 * Deterministic participant color mapping for conversation views.
 * Account owner gets a fixed blue tint; others hash to a 10-color palette.
 */

const PALETTE_HUES = [0, 30, 60, 120, 160, 200, 270, 300, 330, 45] as const
const OWNER_HUE = 220

function hashToIndex(s: string): number {
  let hash = 0
  for (let i = 0; i < s.length; i++) {
    hash = s.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash) % PALETTE_HUES.length
}

export interface ParticipantColorMap {
  getHue(address: string): number
  getCircleStyle(address: string): { backgroundColor: string; color: string }
  getRowTint(address: string): string
  isAccountOwner(address: string): boolean
}

export function buildParticipantColorMap(
  participants: { address: string; contact_id?: string | null }[],
  accountOwnerEmail: string | null,
): ParticipantColorMap {
  const ownerNorm = accountOwnerEmail?.toLowerCase() ?? ''
  const hueCache = new Map<string, number>()

  // Pre-assign hues to avoid collisions
  let nextIdx = 0
  const usedIndices = new Set<number>()

  for (const p of participants) {
    const norm = p.address.toLowerCase()
    if (norm === ownerNorm) {
      hueCache.set(norm, OWNER_HUE)
      continue
    }
    const key = p.contact_id || p.address
    const idx = hashToIndex(key)
    if (!usedIndices.has(idx)) {
      hueCache.set(norm, PALETTE_HUES[idx])
      usedIndices.add(idx)
    } else {
      // Find next available slot
      while (usedIndices.has(nextIdx % PALETTE_HUES.length)) nextIdx++
      const fallback = nextIdx % PALETTE_HUES.length
      hueCache.set(norm, PALETTE_HUES[fallback])
      usedIndices.add(fallback)
      nextIdx++
    }
  }

  function getHue(address: string): number {
    const norm = address.toLowerCase()
    if (hueCache.has(norm)) return hueCache.get(norm)!
    // Unknown participant — hash on the fly
    return PALETTE_HUES[hashToIndex(address)]
  }

  return {
    getHue,
    getCircleStyle(address: string) {
      const hue = getHue(address)
      return {
        backgroundColor: `hsl(${hue}, 55%, 50%)`,
        color: '#fff',
      }
    },
    getRowTint(address: string) {
      const hue = getHue(address)
      return `hsl(${hue}, 30%, 97%)`
    },
    isAccountOwner(address: string) {
      return !!ownerNorm && address.toLowerCase() === ownerNorm
    },
  }
}
