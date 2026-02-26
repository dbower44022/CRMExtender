import { create } from 'zustand'

export type ComposeMode = 'new' | 'reply' | 'reply_all' | 'forward'

interface ComposeContext {
  communicationId?: string
  conversationId?: string
}

interface ComposeState {
  isOpen: boolean
  mode: ComposeMode | null
  context: ComposeContext | null
  draftId: string | null

  openCompose: (mode: ComposeMode, context?: ComposeContext) => void
  closeCompose: () => void
  setDraftId: (id: string | null) => void
}

export const useComposeStore = create<ComposeState>()((set) => ({
  isOpen: false,
  mode: null,
  context: null,
  draftId: null,

  openCompose: (mode, context) =>
    set({ isOpen: true, mode, context: context ?? null, draftId: null }),

  closeCompose: () =>
    set({ isOpen: false, mode: null, context: null, draftId: null }),

  setDraftId: (id) => set({ draftId: id }),
}))
