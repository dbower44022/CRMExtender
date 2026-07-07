import { useQuery } from '@tanstack/react-query'
import { get, post } from './client.ts'

export interface DashboardData {
  counts: {
    conversations_total: number
    conversations_open: number
    conversations_closed: number
    contacts: number
    companies: number
    projects: number
    events: number
  }
  recent_conversations: {
    id: string
    title: string | null
    status: string | null
    communication_count: number
    participant_count: number
    last_activity_at: string | null
  }[]
  top_companies: {
    id: string
    name: string
    domain: string | null
    score: number
  }[]
  top_contacts: {
    id: string
    name: string
    email: string | null
    company_name: string | null
    score: number
  }[]
}

export interface SyncStatus {
  running: boolean
  started_at: string | null
  completed_at: string | null
  result: {
    accounts: number
    contacts: number
    emails_fetched: number
    triaged: number
    summarized: number
    enriched: number
    errors: string[]
  } | null
  error: string | null
}

export function useDashboard(enabled: boolean) {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: () => get<DashboardData>('/dashboard'),
    enabled,
    staleTime: 30_000,
  })
}

export function triggerSync(): Promise<{ status: string }> {
  return post<{ status: string }>('/sync', {})
}

export function getSyncStatus(): Promise<SyncStatus> {
  return get<SyncStatus>('/sync/status')
}
