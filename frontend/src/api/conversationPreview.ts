import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'
import type { ConversationPreviewData } from '../types/api.ts'

export function useConversationPreview(convId: string | null) {
  return useQuery({
    queryKey: ['conversation-preview', convId],
    queryFn: () =>
      get<ConversationPreviewData>(`/conversations/${convId}/preview`),
    enabled: !!convId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
