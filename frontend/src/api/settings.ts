import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, put, post } from './client.ts'

// --- Types ---

interface Profile {
  id: string
  name: string
  email: string
  role: string
  timezone: string
  start_of_week: string
  date_format: string
}

interface SystemSettings {
  company_name: string
  default_timezone: string
  sync_enabled: string
  default_phone_country: string
  allow_self_registration: string
  email_history_window: string
}

interface UserRecord {
  id: string
  customer_id: string
  email: string
  name: string
  role: string
  is_active: number
  created_at: string
  updated_at: string
}

interface ProviderAccount {
  id: string
  provider: string
  email_address: string
  display_name: string | null
  is_active: number
  created_at: string
  updated_at: string
}

interface CalendarAccount extends ProviderAccount {
  selected_calendars: string[]
}

interface ReferenceData {
  timezones: string[]
  countries: Array<{ code: string; name: string }>
  email_history_options: Array<{ value: string; label: string }>
  roles: Array<{ id: string; name: string }>
}

// --- Profile ---

export function useProfile() {
  return useQuery({
    queryKey: ['settings', 'profile'],
    queryFn: () => get<Profile>('/settings/profile'),
    staleTime: 60 * 1000,
  })
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Profile>) =>
      put<{ ok: boolean }>('/settings/profile', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'profile'] })
    },
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: {
      current_password: string
      new_password: string
      confirm_password: string
    }) => put<{ ok: boolean }>('/settings/password', data),
  })
}

// --- System Settings ---

export function useSystemSettings() {
  return useQuery({
    queryKey: ['settings', 'system'],
    queryFn: () => get<SystemSettings>('/settings/system'),
    staleTime: 60 * 1000,
  })
}

export function useUpdateSystemSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<SystemSettings>) =>
      put<{ ok: boolean }>('/settings/system', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'system'] })
    },
  })
}

// --- Users ---

export function useUsers() {
  return useQuery({
    queryKey: ['settings', 'users'],
    queryFn: () => get<UserRecord[]>('/settings/users'),
    staleTime: 30 * 1000,
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      email: string
      name: string
      role: string
      password?: string
    }) => post<UserRecord>('/settings/users', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'users'] })
    },
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      ...data
    }: {
      userId: string
      name?: string
      role?: string
    }) => put<UserRecord>(`/settings/users/${userId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'users'] })
    },
  })
}

export function useSetUserPassword() {
  return useMutation({
    mutationFn: ({
      userId,
      new_password,
    }: {
      userId: string
      new_password: string
    }) => put<{ ok: boolean }>(`/settings/users/${userId}/password`, { new_password }),
  })
}

export function useToggleUserActive() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) =>
      post<{ ok: boolean; is_active: number }>(
        `/settings/users/${userId}/toggle-active`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'users'] })
    },
  })
}

// --- Accounts ---

export function useAccounts() {
  return useQuery({
    queryKey: ['settings', 'accounts'],
    queryFn: () => get<ProviderAccount[]>('/settings/accounts'),
    staleTime: 30 * 1000,
  })
}

export function useUpdateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      accountId,
      display_name,
    }: {
      accountId: string
      display_name: string
    }) => put<{ ok: boolean }>(`/settings/accounts/${accountId}`, { display_name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'accounts'] })
    },
  })
}

export function useToggleAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) =>
      post<{ ok: boolean; is_active: number }>(
        `/settings/accounts/${accountId}/toggle-active`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'accounts'] })
      qc.invalidateQueries({ queryKey: ['settings', 'calendars'] })
    },
  })
}

// --- Calendars ---

export function useCalendars() {
  return useQuery({
    queryKey: ['settings', 'calendars'],
    queryFn: () => get<CalendarAccount[]>('/settings/calendars'),
    staleTime: 30 * 1000,
  })
}

export function useFetchCalendars() {
  return useMutation({
    mutationFn: (accountId: string) =>
      post<{ calendars: Array<{ id: string; summary: string }> }>(
        `/settings/calendars/${accountId}/fetch`,
      ),
  })
}

export function useSaveCalendars() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      accountId,
      calendar_ids,
    }: {
      accountId: string
      calendar_ids: string[]
    }) =>
      put<{ ok: boolean }>(`/settings/calendars/${accountId}`, { calendar_ids }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'calendars'] })
    },
  })
}

// --- Reference Data ---

export function useReferenceData() {
  return useQuery({
    queryKey: ['settings', 'reference-data'],
    queryFn: () => get<ReferenceData>('/settings/reference-data'),
    staleTime: 5 * 60 * 1000,
  })
}
