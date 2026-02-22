/**
 * React Query hooks for layout override CRUD.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, put, del } from './client.ts'
import type { LayoutOverride, DisplayTier } from '../types/api.ts'

export function useLayoutOverrides(viewId: string | null) {
  return useQuery({
    queryKey: ['layout-overrides', viewId],
    queryFn: () =>
      get<LayoutOverride[]>(`/views/${viewId}/layout-overrides`),
    enabled: !!viewId,
    staleTime: 60 * 1000,
  })
}

export function useUpsertLayoutOverride(viewId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      displayTier,
      ...body
    }: {
      displayTier: DisplayTier
      splitter_pct?: number | null
      density?: string | null
      column_overrides?: Record<string, Record<string, unknown>>
    }) =>
      put<LayoutOverride>(
        `/views/${viewId}/layout-overrides/${displayTier}`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['layout-overrides', viewId] })
    },
  })
}

export function useResetLayoutOverrides(viewId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      del<{ ok: boolean; deleted: number }>(
        `/views/${viewId}/layout-overrides`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['layout-overrides', viewId] })
    },
  })
}
