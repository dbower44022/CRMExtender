import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'
import type { CommunicationPreviewData } from '../types/api.ts'

export function useCommunicationPreview(commId: string | null) {
  return useQuery({
    queryKey: ['communication-preview', commId],
    queryFn: () =>
      get<CommunicationPreviewData>(`/communications/${commId}/preview`),
    enabled: !!commId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
