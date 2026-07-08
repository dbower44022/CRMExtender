import { useQuery, useQueryClient } from '@tanstack/react-query'
import { del, get, post, put } from './client.ts'
import { PLURAL } from './detail.ts'

export interface PhoneRow {
  id: string
  number: string
  display: string
  phone_type: string
  is_primary: number
  is_current: number
}

export interface AddressRow {
  id: string
  address_type: string
  street: string
  city: string
  state: string
  postal_code: string
  country: string
  is_primary: number
  is_current: number
}

export interface IdentifierRow {
  id: string
  type: string
  value: string
  label?: string | null
  is_primary: number
  is_current?: number
}

export interface AffiliationRow {
  id: string
  company_id: string
  company_name: string
  role_id: string | null
  role_name: string | null
  title: string | null
  department: string | null
  is_primary: number
  is_current: number
}

export interface ContactCompanyRole {
  id: string
  name: string
}

export interface HierarchyRow {
  id: string
  parent_company_id: string
  child_company_id: string
  hierarchy_type: string
  parent_name?: string
  child_name?: string
}

export interface ContactCore {
  name: string | null
  first_name: string | null
  last_name: string | null
  lead_status: string | null
  lead_source: string | null
  status: string
  source: string | null
}

export interface Subresources {
  core?: ContactCore | null
  phones: PhoneRow[]
  addresses: AddressRow[]
  identifiers: IdentifierRow[]
  affiliations?: AffiliationRow[]
  emails?: (IdentifierRow & { address: string; email_type: string })[]
  hierarchy?: { parents: HierarchyRow[]; children: HierarchyRow[] }
}

const base = (entityType: string, entityId: string) =>
  `/${PLURAL[entityType] ?? `${entityType}s`}/${entityId}`

export function useSubresources(entityType: string, entityId: string, enabled = true) {
  return useQuery({
    queryKey: ['subresources', entityType, entityId],
    queryFn: () => get<Subresources>(`${base(entityType, entityId)}/subresources`),
    enabled,
  })
}

/** Invalidate everything a sub-resource edit can affect. */
export function useInvalidateRecord(entityType: string, entityId: string) {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['subresources', entityType, entityId] })
    qc.invalidateQueries({ queryKey: ['entity-detail', entityType, entityId] })
    qc.invalidateQueries({ queryKey: ['view-data'] })
  }
}

export const sub = {
  add: (entityType: string, entityId: string, kind: string, body: unknown) =>
    post(`${base(entityType, entityId)}/${kind}`, body),
  update: (entityType: string, entityId: string, kind: string, rowId: string, body: unknown) =>
    put(`${base(entityType, entityId)}/${kind}/${rowId}`, body),
  remove: (entityType: string, entityId: string, kind: string, rowId: string) =>
    del(`${base(entityType, entityId)}/${kind}/${rowId}`),
}

export function deleteEntity(entityType: string, entityId: string) {
  return del(`${base(entityType, entityId)}`)
}

export function recomputeScore(entityType: string, entityId: string) {
  return post(`${base(entityType, entityId)}/score`, {})
}
