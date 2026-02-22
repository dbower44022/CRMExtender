import { useMutation, useQueryClient } from '@tanstack/react-query'
import { post } from './client.ts'
import type { CreateCompanyRequest, CompanyMergePreview, CompanyMergeRequest, CompanyMergeResult } from '../types/api.ts'

export function useCreateCompany() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: CreateCompanyRequest) =>
      post<Record<string, unknown>>('/companies', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
    },
  })
}

export function useCompanyMergePreview() {
  return useMutation({
    mutationFn: (companyIds: string[]) =>
      post<CompanyMergePreview>('/companies/merge-preview', { company_ids: companyIds }),
  })
}

export function useMergeCompanies() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: CompanyMergeRequest) =>
      post<CompanyMergeResult>('/companies/merge', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
    },
  })
}
