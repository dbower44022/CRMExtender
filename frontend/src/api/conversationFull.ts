import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'
import type { ConversationFullData } from '../types/api.ts'

export function useConversationFull(convId: string | null) {
  return useQuery({
    queryKey: ['conversation-full', convId],
    queryFn: () =>
      get<ConversationFullData>(`/conversations/${convId}/full`),
    enabled: !!convId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
