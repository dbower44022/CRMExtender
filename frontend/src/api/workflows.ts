import { del, get, post } from './client.ts'

export interface RelationshipTypeRow {
  id: string
  name: string
  from_entity_type: string
  to_entity_type: string
  forward_label: string
  reverse_label: string
  is_system: number
  is_bidirectional: number
  description: string | null
}

export interface TopicRow {
  id: string
  name: string
  project_id: string
  project_name?: string
  description?: string | null
  conversation_count?: number
}

export const workflows = {
  // Topics & assignment
  topics: (projectId = '') =>
    get<{ topics: TopicRow[] }>(
      `/topics${projectId ? `?project_id=${projectId}` : ''}`),
  assignTopic: (conversationId: string, topicId: string) =>
    post(`/conversations/${conversationId}/topic`, { topic_id: topicId }),
  unassignTopic: (conversationId: string) =>
    del(`/conversations/${conversationId}/topic`),

  // Communications bulk
  assignTargets: (q: string) =>
    get<{ conversations: { id: string; title: string; last_activity_at: string }[] }>(
      `/communications/assign-targets?q=${encodeURIComponent(q)}`),
  archiveCommunications: (ids: string[]) =>
    post<{ archived: number; conversations_dismissed: number }>(
      '/communications/archive', { ids }),
  assignCommunications: (ids: string[], conversationId: string) =>
    post<{ assigned: number; skipped_existing: number }>(
      '/communications/assign', { ids, conversation_id: conversationId }),

  // Projects & topics
  createProject: (name: string, description: string) =>
    post<{ id: string; name: string }>('/projects', { name, description }),
  createTopic: (projectId: string, name: string, description = '') =>
    post<TopicRow>(`/projects/${projectId}/topics`, { name, description }),
  deleteTopic: (projectId: string, topicId: string) =>
    del<{ conversations_unassigned: number }>(
      `/projects/${projectId}/topics/${topicId}`),
  autoAssignPreview: (projectId: string) =>
    post<{
      project_name: string
      total_candidates: number
      matched: number
      unmatched: number
      assignments: {
        conversation_id: string
        conversation_title: string
        topic_name: string
        score: number
      }[]
    }>(`/projects/${projectId}/auto-assign/preview`, {}),
  autoAssignApply: (projectId: string) =>
    post<{ assigned: number }>(`/projects/${projectId}/auto-assign/apply`, {}),

  // Events
  createEvent: (body: Record<string, unknown>) =>
    post<{ id: string; title: string }>('/events', body),
  calendarSync: () => post<{ status: string }>('/events/sync', {}),
  calendarSyncStatus: () =>
    get<{ running: boolean; result: Record<string, unknown> | null; error: string | null }>(
      '/events/sync/status'),

  // Relationships
  relationshipTypes: (fromType = '', toType = '') =>
    get<{ types: RelationshipTypeRow[] }>(
      `/relationship-types?from_entity_type=${fromType}&to_entity_type=${toType}`),
  createRelationshipType: (body: Record<string, unknown>) =>
    post<RelationshipTypeRow>('/relationship-types', body),
  deleteRelationshipType: (typeId: string) =>
    del(`/relationship-types/${typeId}`),
  createRelationships: (body: {
    relationship_type_id: string
    to_entity_id: string
    from_entity_ids: string[]
  }) =>
    post<{ results: { status: string; reason?: string }[]; created: number }>(
      '/relationships', body),
  inferRelationships: () =>
    post<{ count: number }>('/relationships/infer', {}),

  // Import & company ops
  importVcards: (path: string, recursive: boolean) =>
    post<Record<string, unknown>>('/contacts/import-vcards', { path, recursive }),
  resolveDomains: () =>
    post<{ contacts_checked: number; contacts_linked: number }>(
      '/companies/resolve-domains', {}),
  companyDuplicates: () =>
    get<{ groups: { domain: string; companies: { id: string; name: string }[] }[] }>(
      '/companies/duplicates'),
  enrichCompany: (companyId: string) =>
    post<{ status: string; fields_discovered: number; fields_applied: number }>(
      `/companies/${companyId}/enrich`, {}),
}

export interface MatchSignal {
  name: string
  weight: number
  value_a: string
  value_b: string
}

export interface MatchCandidate {
  id: string
  contact_a_id: string
  contact_b_id: string
  name_a: string
  name_b: string
  email_a: string | null
  email_b: string | null
  confidence: number
  signals: MatchSignal[]
  source: string | null
}

export const identity = {
  scan: () =>
    post<{ contacts: number; pairs_scored: number; candidates_created: number }>(
      '/contacts/duplicate-scan', {}),
  reviewQueue: (sort = 'confidence') =>
    get<{ candidates: MatchCandidate[]; pending_count: number }>(
      `/contacts/review-queue?sort=${sort}`),
  reject: (candidateId: string) =>
    post<{ status: string }>(`/contacts/review-queue/${candidateId}/reject`, {}),
  restore: (candidateId: string) =>
    post<{ status: string }>(`/contacts/review-queue/${candidateId}/restore`, {}),
}
