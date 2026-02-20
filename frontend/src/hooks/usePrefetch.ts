import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { get } from '../api/client.ts'
import { PLURAL } from '../api/detail.ts'
import type { EntityDetailResponse } from '../types/api.ts'

interface UsePrefetchOptions {
  rows: Record<string, unknown>[]
  selectedRowId: string | null
  entityType: string
}

export function usePrefetch({
  rows,
  selectedRowId,
  entityType,
}: UsePrefetchOptions) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!selectedRowId || rows.length === 0) return

    const currentIndex = rows.findIndex(
      (r) => String(r.id) === selectedRowId,
    )
    if (currentIndex === -1) return

    // Prefetch ±2 adjacent records
    const adjacentIndices = [
      currentIndex - 2,
      currentIndex - 1,
      currentIndex + 1,
      currentIndex + 2,
    ].filter((i) => i >= 0 && i < rows.length)

    for (const idx of adjacentIndices) {
      const rowId = String(rows[idx].id)
      queryClient.prefetchQuery({
        queryKey: ['entity-detail', entityType, rowId],
        queryFn: () =>
          get<EntityDetailResponse>(`/${PLURAL[entityType] ?? `${entityType}s`}/${rowId}`),
        staleTime: 30 * 1000,
      })
    }
  }, [selectedRowId, rows, entityType, queryClient])
}
