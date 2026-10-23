/** Composer state (Mail Client MAIL-33/34/35).
 *
 * Up to three composers at once. Each is either docked (bottom-right panel
 * that can be minimized) or inline (at the bottom of the thread it replies
 * to). A composer that leaves its thread is re-docked. Pending sends are the
 * messages inside their undo window.
 */

import { create } from 'zustand'
import type { OutboundDraft } from '../api/outbound.ts'

export type ComposeMode = 'new' | 'reply' | 'reply_all' | 'forward'
export type ComposePlacement = 'dock' | 'inline'

export interface ComposeContext {
  communicationId?: string
  conversationId?: string
  /** Inline composers belong to one thread: `${accountId}:${threadId}`. */
  threadKey?: string
}

export interface Composer {
  id: string
  mode: ComposeMode
  context: ComposeContext | null
  draftId: string | null
  placement: ComposePlacement
  minimized: boolean
  /** A saved draft being resumed (MAIL-35). */
  resume: OutboundDraft | null
}

export interface PendingSend {
  draftId: string
  subject: string
  sendAt: number        // epoch ms
  scheduled: boolean    // true = scheduled send, false = undo window
}

export const MAX_COMPOSERS = 3

interface ComposeState {
  composers: Composer[]
  pendingSends: PendingSend[]

  openCompose: (mode: ComposeMode, context?: ComposeContext, placement?: ComposePlacement) => string | null
  resumeDraft: (draft: OutboundDraft) => string | null
  closeCompose: (id: string) => void
  setDraftId: (id: string, draftId: string | null) => void
  setMinimized: (id: string, minimized: boolean) => void
  dockComposer: (id: string) => void
  addPendingSend: (p: PendingSend) => void
  removePendingSend: (draftId: string) => void
}

let seq = 0
const nextId = () => `c${++seq}-${Date.now().toString(36)}`

export const useComposeStore = create<ComposeState>()((set, get) => ({
  composers: [],
  pendingSends: [],

  openCompose: (mode, context, placement = 'dock') => {
    const { composers } = get()
    // One inline composer per thread: re-use it rather than stacking.
    if (placement === 'inline' && context?.threadKey) {
      const existing = composers.find((c) => c.placement === 'inline' && c.context?.threadKey === context.threadKey)
      if (existing) {
        set({ composers: composers.map((c) => (c.id === existing.id ? { ...c, mode, context, minimized: false } : c)) })
        return existing.id
      }
    }
    if (composers.length >= MAX_COMPOSERS) return null
    const id = nextId()
    set({ composers: [...composers, { id, mode, context: context ?? null, draftId: null, placement, minimized: false, resume: null }] })
    return id
  },

  resumeDraft: (draft) => {
    const { composers } = get()
    const open = composers.find((c) => c.draftId === draft.id)
    if (open) {
      set({ composers: composers.map((c) => (c.id === open.id ? { ...c, minimized: false } : c)) })
      return open.id
    }
    if (composers.length >= MAX_COMPOSERS) return null
    const id = nextId()
    const mode: ComposeMode = draft.source_type === 'reply' ? 'reply' : draft.source_type === 'forward' ? 'forward' : 'new'
    set({ composers: [...composers, { id, mode, context: null, draftId: draft.id, placement: 'dock', minimized: false, resume: draft }] })
    return id
  },

  closeCompose: (id) => set((s) => ({ composers: s.composers.filter((c) => c.id !== id) })),

  setDraftId: (id, draftId) =>
    set((s) => ({ composers: s.composers.map((c) => (c.id === id ? { ...c, draftId } : c)) })),

  setMinimized: (id, minimized) =>
    set((s) => ({ composers: s.composers.map((c) => (c.id === id ? { ...c, minimized } : c)) })),

  dockComposer: (id) =>
    set((s) => ({ composers: s.composers.map((c) => (c.id === id ? { ...c, placement: 'dock', minimized: true } : c)) })),

  addPendingSend: (p) =>
    set((s) => ({ pendingSends: [...s.pendingSends.filter((x) => x.draftId !== p.draftId), p] })),

  removePendingSend: (draftId) =>
    set((s) => ({ pendingSends: s.pendingSends.filter((x) => x.draftId !== draftId) })),
}))
