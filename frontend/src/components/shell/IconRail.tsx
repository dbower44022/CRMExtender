import { Home, Settings, Users } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useLayoutStore } from '../../stores/layout.ts'
import { identity } from '../../api/workflows.ts'
import { ENTITY_ICONS, ENTITY_LABELS } from '../../lib/entityIcons.ts'

const NAV_ITEMS = Object.entries(ENTITY_ICONS).map(([key, icon]) => ({
  key,
  label: ENTITY_LABELS[key] ?? key,
  icon,
}))

export function IconRail() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const settingsMode = useNavigationStore((s) => s.settingsMode)
  const openSettings = useNavigationStore((s) => s.openSettings)
  const dashboardMode = useNavigationStore((s) => s.dashboardMode)
  const openDashboard = useNavigationStore((s) => s.openDashboard)
  const reviewMode = useNavigationStore((s) => s.reviewMode)
  const openReview = useNavigationStore((s) => s.openReview)
  const { data: reviewData } = useQuery({
    queryKey: ['review-count'],
    queryFn: () => identity.reviewQueue(),
    staleTime: 30_000,
  })
  const pendingCount = reviewData?.pending_count ?? 0
  const actionPanelVisible = useLayoutStore((s) => s.actionPanelVisible)
  const toggleActionPanel = useLayoutStore((s) => s.toggleActionPanel)

  const handleClick = (key: string) => {
    if (key === activeEntityType && !settingsMode && !dashboardMode && !reviewMode) {
      toggleActionPanel()
    } else {
      setActiveEntityType(key)
    }
  }

  const handleSettingsClick = () => {
    if (settingsMode) {
      toggleActionPanel()
    } else {
      openSettings()
      if (!actionPanelVisible) toggleActionPanel()
    }
  }

  return (
    <div className="flex h-full w-[60px] flex-col items-center border-r border-surface-200 bg-surface-50 py-2">
      <div className="flex flex-1 flex-col gap-1">
        <button
          onClick={openDashboard}
          title="Dashboard"
          className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
            dashboardMode
              ? 'bg-primary-100 text-primary-700'
              : 'text-surface-500 hover:bg-surface-100 hover:text-surface-700'
          }`}
        >
          <Home size={20} strokeWidth={dashboardMode ? 2.2 : 1.8} />
        </button>
        <div className="mx-auto my-1 h-px w-6 bg-surface-200" />
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive = item.key === activeEntityType
          return (
            <button
              key={item.key}
              onClick={() => handleClick(item.key)}
              title={item.label}
              className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
                isActive && !settingsMode && !dashboardMode
                  ? 'bg-primary-100 text-primary-700'
                  : 'text-surface-500 hover:bg-surface-100 hover:text-surface-700'
              }`}
            >
              <Icon size={20} strokeWidth={isActive && !settingsMode && !dashboardMode ? 2.2 : 1.8} />
            </button>
          )
        })}
        <div className="mx-auto my-1 h-px w-6 bg-surface-200" />
        <button
          onClick={openReview}
          title="Duplicate Review"
          className={`relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
            reviewMode
              ? 'bg-primary-100 text-primary-700'
              : 'text-surface-500 hover:bg-surface-100 hover:text-surface-700'
          }`}
        >
          <Users size={20} strokeWidth={reviewMode ? 2.2 : 1.8} />
          {pendingCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-semibold text-white">
              {pendingCount > 99 ? '99+' : pendingCount}
            </span>
          )}
        </button>
      </div>
      <div className="mt-auto pb-2">
        <button
          onClick={handleSettingsClick}
          title="Settings"
          className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
            settingsMode
              ? 'bg-primary-100 text-primary-700'
              : 'text-surface-400 hover:bg-surface-100 hover:text-surface-600'
          }`}
        >
          <Settings size={20} strokeWidth={settingsMode ? 2.2 : 1.8} />
        </button>
      </div>
    </div>
  )
}
