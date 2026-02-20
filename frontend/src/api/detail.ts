import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'
import type { EntityDetailResponse } from '../types/api.ts'

export function useEntityDetail(
  entityType: string | null,
  entityId: string | null,
) {
  return useQuery({
    queryKey: ['entity-detail', entityType, entityId],
    queryFn: () =>
      get<EntityDetailResponse>(`/${entityType}s/${entityId}`),
    enabled: !!entityType && !!entityId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
