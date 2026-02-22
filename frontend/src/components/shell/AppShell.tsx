import { useEffect } from 'react'
import {
  Group,
  Panel,
  Separator,
  useDefaultLayout,
  usePanelRef,
} from 'react-resizable-panels'
import { useLayoutStore } from '../../stores/layout.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useViewConfig } from '../../api/views.ts'
import { IconRail } from './IconRail.tsx'
import { TopHeaderBar } from './TopHeaderBar.tsx'
import { ActionPanel } from './ActionPanel.tsx'
import { ContentArea } from './ContentArea.tsx'
import { DetailPanel } from './DetailPanel.tsx'
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
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const { data: viewConfig } = useViewConfig(activeViewId)

  useDefaultView()

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
    if (detailPanelVisible) {
      const previewSize = viewConfig?.preview_panel_size ?? 'medium'
      const size = PREVIEW_PANEL_SIZE_MAP[previewSize] ?? '30%'
      panel.resize(size)
    } else {
      panel.resize('0%')
    }
  }, [detailPanelVisible, detailRef, viewConfig?.preview_panel_size])

  return (
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
            maxSize="60%"
            collapsible
            collapsedSize="0%"
          >
            <DetailPanel />
          </Panel>
        </Group>
      </div>
    </div>
  )
}
