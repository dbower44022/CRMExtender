import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'
import type { CommunicationFullData } from '../types/api.ts'

export function useCommunicationFull(commId: string | null) {
  return useQuery({
    queryKey: ['communication-full', commId],
    queryFn: () =>
      get<CommunicationFullData>(`/communications/${commId}/full`),
    enabled: !!commId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
