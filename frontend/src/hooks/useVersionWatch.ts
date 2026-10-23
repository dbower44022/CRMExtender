/** Reload the page when the server starts serving a newer build (v10.43).
 *
 * Checks the version route once a minute and whenever the live event
 * stream reconnects (which is what happens right after a server restart).
 * A newer bundle reloads the page at once unless a composer is open; then
 * a pop-up offers the reload and the page reloads when the composer closes.
 */

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { get } from '../api/client.ts'
import { useComposeStore } from '../stores/compose.ts'
import { useLiveStore } from '../stores/live.ts'
import { loadedBuildId, shouldReload } from '../lib/buildId.ts'

interface VersionInfo { version: string; build?: string | null }

export function useVersionWatch() {
  const connected = useLiveStore((s) => s.connected)
  const composing = useComposeStore((s) => s.composers.length > 0)
  const [loaded] = useState<string | null>(() => (typeof document !== 'undefined' ? loadedBuildId() : null))
  const toasted = useRef(false)

  const q = useQuery({
    queryKey: ['server-version'],
    queryFn: () => get<VersionInfo>('/version'),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
  const refetch = q.refetch

  // The stream reconnects after a restart: check right away.
  useEffect(() => { if (connected) void refetch() }, [connected, refetch])

  const served = q.data?.build
  const version = q.data?.version
  useEffect(() => {
    if (!loaded || !served || served === loaded) return
    if (shouldReload(loaded, served, composing)) {
      window.location.reload()
      return
    }
    if (!toasted.current) {
      toasted.current = true
      toast(`CRMExtender v${version ?? ''} is ready`, {
        description: 'The page reloads when you close the composer, or now.',
        duration: Infinity,
        action: { label: 'Reload now', onClick: () => window.location.reload() },
      })
    }
  }, [served, version, composing, loaded])
}
