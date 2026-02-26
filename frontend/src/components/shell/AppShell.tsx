import { useEffect } from 'react'
import {
  Group,
  Panel,
  Separator,
  useDefaultLayout,
  usePanelRef,
} from 'react-resizable-panels'
import { toast } from 'sonner'
import { useLayoutStore } from '../../stores/layout.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useViewConfig } from '../../api/views.ts'
import { IconRail } from './IconRail.tsx'
import { TopHeaderBar } from './TopHeaderBar.tsx'
import { ActionPanel } from './ActionPanel.tsx'
import { ContentArea } from './ContentArea.tsx'
import { DetailPanel } from './DetailPanel.tsx'
import { GlobalSearchModal } from '../search/GlobalSearchModal.tsx'
import { ComposePanel } from '../compose/ComposePanel.tsx'
import { useDefaultView } from '../../hooks/useDefaultView.ts'

const PREVIEW_PANEL_SIZE_MAP: Record<string, string> = {
  none: '0%',
  small: '20%',
  medium: '30%',
  large: '45%',
  huge: '55%',
}

export function AppShell() {
  const actionPanelVisible = useLayoutStore((s) => s.actionPanelVisible)
  const detailPanelVisible = useLayoutStore((s) => s.detailPanelVisible)
  const detailPanelExpanded = useLayoutStore((s) => s.detailPanelExpanded)
  const searchModalOpen = useLayoutStore((s) => s.searchModalOpen)
  const openSearchModal = useLayoutStore((s) => s.openSearchModal)
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const settingsMode = useNavigationStore((s) => s.settingsMode)
  const { data: viewConfig } = useViewConfig(activeViewId)

  useDefaultView()

  // If redirected back from OAuth connect, open Settings > Accounts
  const openSettings = useNavigationStore((s) => s.openSettings)
  const setSettingsTab = useNavigationStore((s) => s.setSettingsTab)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('connected') === '1') {
      openSettings()
      setSettingsTab('accounts')
      toast.success('Google account connected successfully')
      const url = new URL(window.location.href)
      url.searchParams.delete('connected')
      window.history.replaceState({}, '', url.pathname + url.hash)
    }
  }, [openSettings, setSettingsTab])

  const actionRef = usePanelRef()
  const detailRef = usePanelRef()

  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    storage: localStorage,
    id: 'crm-layout',
  })

  // Sync Zustand visibility with panel sizes
  useEffect(() => {
    const panel = actionRef.current
    if (!panel) return
    if (actionPanelVisible) {
      panel.resize('20%')
    } else {
      panel.resize('0%')
    }
  }, [actionPanelVisible, actionRef])

  useEffect(() => {
    const panel = detailRef.current
    if (!panel) return
    if (settingsMode) {
      panel.resize('0%')
    } else if (detailPanelExpanded && detailPanelVisible) {
      panel.resize('65%')
    } else if (detailPanelVisible) {
      const previewSize = viewConfig?.preview_panel_size ?? 'medium'
      const size = PREVIEW_PANEL_SIZE_MAP[previewSize] ?? '30%'
      panel.resize(size)
    } else {
      panel.resize('0%')
    }
  }, [detailPanelVisible, detailPanelExpanded, detailRef, viewConfig?.preview_panel_size, settingsMode])

  // Ctrl+K / Cmd+K to open search modal
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        openSearchModal()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [openSearchModal])

  return (
    <>
    <div className="flex h-full w-full">
      <IconRail />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopHeaderBar />
        <Group
          orientation="horizontal"
          id="crm-main"
          defaultLayout={defaultLayout}
          onLayoutChanged={onLayoutChanged}
        >
          <Panel
            id="action"
            panelRef={actionRef}
            defaultSize="20%"
            minSize="0%"
            maxSize="30%"
            collapsible
            collapsedSize="0%"
          >
            <ActionPanel />
          </Panel>
          <Separator className="separator-handle" />
          <Panel id="content" defaultSize="50%" minSize="20%">
            <ContentArea />
          </Panel>
          <Separator className="separator-handle" />
          <Panel
            id="detail"
            panelRef={detailRef}
            defaultSize="0%"
            minSize="0%"
            maxSize="80%"
            collapsible
            collapsedSize="0%"
          >
            <DetailPanel />
          </Panel>
        </Group>
      </div>
    </div>
    {searchModalOpen && <GlobalSearchModal />}
    <ComposePanel />
    </>
  )
}
