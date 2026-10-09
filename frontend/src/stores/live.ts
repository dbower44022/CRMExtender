/** Live-update connection state (MAIL-37): whether the browser is on the
 * event stream or back on polling, and the last event seen. */

import { create } from 'zustand'

export interface LiveEvent {
  id: number
  type: string
  at: string
  account_id?: string
  email?: string
  error?: string | null
  result?: Record<string, number> | null
}

interface LiveState {
  connected: boolean
  lastEvent: LiveEvent | null
  syncing: Record<string, boolean>   // account_id -> running
  setConnected: (v: boolean) => void
  recordEvent: (e: LiveEvent) => void
}

export const useLiveStore = create<LiveState>()((set) => ({
  connected: false,
  lastEvent: null,
  syncing: {},
  setConnected: (connected) => set({ connected }),
  recordEvent: (e) =>
    set((s) => ({
      lastEvent: e,
      syncing: e.account_id
        ? { ...s.syncing, [e.account_id]: e.type === 'sync.started' }
        : s.syncing,
    })),
}))
