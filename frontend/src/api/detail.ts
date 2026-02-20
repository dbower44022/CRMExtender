import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'
import type { EntityDetailResponse } from '../types/api.ts'

export const PLURAL: Record<string, string> = {
  contact: 'contacts',
  company: 'companies',
  conversation: 'conversations',
  event: 'events',
  communication: 'communications',
  project: 'projects',
  relationship: 'relationships',
  note: 'notes',
}

export function useEntityDetail(
  entityType: string | null,
  entityId: string | null,
) {
  const plural = entityType ? (PLURAL[entityType] ?? `${entityType}s`) : ''
  return useQuery({
    queryKey: ['entity-detail', entityType, entityId],
    queryFn: () =>
      get<EntityDetailResponse>(`/${plural}/${entityId}`),
    enabled: !!entityType && !!entityId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
