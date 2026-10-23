/** External participants of a thread, for the context column (MAIL-32). */

import type { ThreadDetail } from '../api/mail.ts'

export interface ExternalParticipant {
  address: string
  name: string | null
  contact_id: string | null
  contact_name: string | null
}

/** Distinct external participants, senders first, at most `max`. */
export function externalParticipants(t: ThreadDetail, max = 3): ExternalParticipant[] {
  const me = t.account_email.toLowerCase()
  const seen = new Map<string, ExternalParticipant>()
  for (const m of [...t.messages].reverse()) {
    const s = m.sender
    if (s.address && !s.is_me && s.address.toLowerCase() !== me && !seen.has(s.address.toLowerCase())) {
      seen.set(s.address.toLowerCase(), { address: s.address, name: s.name, contact_id: s.contact_id, contact_name: s.contact_name })
    }
  }
  for (const m of t.messages) {
    for (const p of m.participants) {
      const a = p.address.toLowerCase()
      if (a === me || seen.has(a)) continue
      seen.set(a, { address: p.address, name: p.name, contact_id: p.contact_id, contact_name: p.contact_name })
    }
  }
  return [...seen.values()].slice(0, max)
}
