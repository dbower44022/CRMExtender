import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface LayoutState {
  actionPanelVisible: boolean
  detailPanelVisible: boolean
  actionPanelSize: number
  detailPanelSize: number
  searchModalOpen: boolean
  toggleActionPanel: () => void
  toggleDetailPanel: () => void
  setActionPanelSize: (size: number) => void
  setDetailPanelSize: (size: number) => void
  showDetailPanel: () => void
  hideDetailPanel: () => void
  openSearchModal: () => void
  closeSearchModal: () => void
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      actionPanelVisible: true,
      detailPanelVisible: false,
      actionPanelSize: 18,
      detailPanelSize: 30,
      searchModalOpen: false,
      toggleActionPanel: () =>
        set((s) => ({ actionPanelVisible: !s.actionPanelVisible })),
      toggleDetailPanel: () =>
        set((s) => ({ detailPanelVisible: !s.detailPanelVisible })),
      setActionPanelSize: (size) => set({ actionPanelSize: size }),
      setDetailPanelSize: (size) => set({ detailPanelSize: size }),
      showDetailPanel: () => set({ detailPanelVisible: true }),
      hideDetailPanel: () => set({ detailPanelVisible: false }),
      openSearchModal: () => set({ searchModalOpen: true }),
      closeSearchModal: () => set({ searchModalOpen: false }),
    }),
    {
      name: 'crm-layout',
      partialize: (s) => ({
        actionPanelVisible: s.actionPanelVisible,
        actionPanelSize: s.actionPanelSize,
        detailPanelSize: s.detailPanelSize,
      }),
    },
  ),
)
