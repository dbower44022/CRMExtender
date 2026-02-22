import { Home, Settings } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useLayoutStore } from '../../stores/layout.ts'
import { ENTITY_ICONS, ENTITY_LABELS } from '../../lib/entityIcons.ts'

const NAV_ITEMS = Object.entries(ENTITY_ICONS).map(([key, icon]) => ({
  key,
  label: ENTITY_LABELS[key] ?? key,
  icon,
}))

export function IconRail() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const toggleActionPanel = useLayoutStore((s) => s.toggleActionPanel)

  const handleClick = (key: string) => {
    if (key === activeEntityType) {
      toggleActionPanel()
    } else {
      setActiveEntityType(key)
    }
  }

  return (
    <div className="flex h-full w-[60px] flex-col items-center border-r border-surface-200 bg-surface-50 py-2">
      <div className="flex flex-1 flex-col gap-1">
        <a
          href="/"
          title="Dashboard"
          className="flex h-10 w-10 items-center justify-center rounded-lg text-surface-500 transition-colors hover:bg-surface-100 hover:text-surface-700"
        >
          <Home size={20} strokeWidth={1.8} />
        </a>
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
                isActive
                  ? 'bg-primary-100 text-primary-700'
                  : 'text-surface-500 hover:bg-surface-100 hover:text-surface-700'
              }`}
            >
              <Icon size={20} strokeWidth={isActive ? 2.2 : 1.8} />
            </button>
          )
        })}
      </div>
      <div className="mt-auto pb-2">
        <a
          href="/settings"
          title="Settings"
          className="flex h-10 w-10 items-center justify-center rounded-lg text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
        >
          <Settings size={20} strokeWidth={1.8} />
        </a>
      </div>
    </div>
  )
}
