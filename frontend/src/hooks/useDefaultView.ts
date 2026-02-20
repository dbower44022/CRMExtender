import { useEffect } from 'react'
import { useNavigationStore } from '../stores/navigation.ts'
import { useViews } from '../api/views.ts'

export function useDefaultView() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const setActiveViewId = useNavigationStore((s) => s.setActiveViewId)
  const { data: views } = useViews(activeEntityType)

  useEffect(() => {
    if (!activeViewId && views && views.length > 0) {
      const defaultView = views.find((v) => v.is_default) ?? views[0]
      setActiveViewId(defaultView.id)
    }
  }, [activeViewId, views, setActiveViewId])
}
