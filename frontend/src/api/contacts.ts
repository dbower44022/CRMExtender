import { useMutation, useQueryClient } from '@tanstack/react-query'
import { post } from './client.ts'
import type { MergePreview, MergeRequest, MergeResult } from '../types/api.ts'

export function useMergePreview() {
  return useMutation({
    mutationFn: (contactIds: string[]) =>
      post<MergePreview>('/contacts/merge-preview', { contact_ids: contactIds }),
  })
}

export function useMergeContacts() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: MergeRequest) =>
      post<MergeResult>('/contacts/merge', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
    },
  })
}
