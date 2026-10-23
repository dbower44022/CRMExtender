/** Two-way sync between navigation state and the URL (Legacy UI Migration PRD, Phase 0).
 *
 * URL shape: /app/{entity-plural}[/{record-id}]. On boot and popstate the URL
 * drives the store (deep links, back/forward); on store changes the URL is
 * pushed. Settings mode and view/sort/search state are intentionally not
 * URL-encoded in Phase 0.
 */

import { useEffect, useRef } from 'react'
import { useNavigationStore } from '../stores/navigation.ts'
import { buildAppPath, buildMailPath, parseAppPath, parseMailPath } from '../lib/appRoutes.ts'

export function useUrlSync() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)
  const dashboardMode = useNavigationStore((s) => s.dashboardMode)
  const reviewMode = useNavigationStore((s) => s.reviewMode)
  const mailMode = useNavigationStore((s) => s.mailMode)
  const mailAccountId = useNavigationStore((s) => s.mailAccountId)
  const mailFolder = useNavigationStore((s) => s.mailFolder)
  const mailThreadId = useNavigationStore((s) => s.mailThreadId)
  // True while we are applying a URL to the store (boot/popstate), so the
  // store→URL effect doesn't push a duplicate history entry.
  const applyingUrl = useRef(false)

  // URL → store, on boot and on back/forward
  useEffect(() => {
    const applyUrl = () => {
      const nav = useNavigationStore.getState()
      if (window.location.pathname === '/app/dashboard') {
        applyingUrl.current = true
        if (!nav.dashboardMode) nav.openDashboard()
        queueMicrotask(() => {
          applyingUrl.current = false
        })
        return
      }
      if (window.location.pathname === '/app/review') {
        applyingUrl.current = true
        if (!nav.reviewMode) nav.openReview()
        queueMicrotask(() => {
          applyingUrl.current = false
        })
        return
      }
      const mail = parseMailPath(window.location.pathname)
      if (mail) {
        applyingUrl.current = true
        nav.openMail(mail.accountId, mail.folder, mail.threadId)
        queueMicrotask(() => {
          applyingUrl.current = false
        })
        return
      }
      const route = parseAppPath(window.location.pathname)
      if (!route) return
      applyingUrl.current = true
      if (nav.dashboardMode) nav.closeDashboard()
      if (nav.reviewMode) nav.closeReview()
      if (nav.mailMode) nav.closeMail()
      if (nav.activeEntityType !== route.entityType) {
        nav.setActiveEntityType(route.entityType)
      }
      if (route.entityId) {
        nav.setPendingNavigation({
          entityType: route.entityType,
          entityId: route.entityId,
        })
      } else if (nav.selectedRowId) {
        nav.setSelectedRow(null, -1)
      }
      // Release after the store updates flush
      queueMicrotask(() => {
        applyingUrl.current = false
      })
    }

    applyUrl()
    window.addEventListener('popstate', applyUrl)
    return () => window.removeEventListener('popstate', applyUrl)
  }, [])

  // Store → URL
  useEffect(() => {
    if (applyingUrl.current) return
    const path = dashboardMode
      ? '/app/dashboard'
      : reviewMode
        ? '/app/review'
        : mailMode
          ? buildMailPath(mailAccountId, mailFolder, mailThreadId)
          : buildAppPath(activeEntityType, selectedRowId)
    if (window.location.pathname === path) return
    // Selecting a row within the same entity replaces (arrow-key browsing
    // shouldn't flood history); switching entity type pushes. Likewise a
    // thread within the same mail folder replaces.
    const current = parseAppPath(window.location.pathname)
    const sameEntity = !dashboardMode && !reviewMode && !mailMode && current?.entityType === activeEntityType
    const currentMail = parseMailPath(window.location.pathname)
    const sameFolder = mailMode && currentMail?.accountId === mailAccountId && currentMail?.folder === mailFolder
    if ((sameEntity && current?.entityId && selectedRowId) || (sameFolder && currentMail?.threadId && mailThreadId)) {
      window.history.replaceState({}, '', path)
    } else {
      window.history.pushState({}, '', path)
    }
  }, [activeEntityType, selectedRowId, dashboardMode, reviewMode, mailMode, mailAccountId, mailFolder, mailThreadId])
}
