import { useQuery, useQueryClient } from '@tanstack/react-query'
import { del, get, post, put } from './client.ts'

export interface NoteEntityLink {
  entity_type: string
  entity_id: string
  entity_name?: string | null
  is_pinned: number
}

export interface Note {
  id: string
  title: string | null
  content_json: string | null
  content_html: string | null
  author_name?: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  revision_number?: number
  is_pinned: number
  entities?: NoteEntityLink[]
}

export interface NoteRevision {
  id: string
  note_id: string
  revision_number: number
  content_json?: string | null
  content_html?: string | null
  revised_by_name?: string | null
  created_at: string
}

export interface MentionHit {
  id: string
  name: string
  detail?: string
}

export function useEntityNotes(entityType: string, entityId: string) {
  return useQuery({
    queryKey: ['notes', entityType, entityId],
    queryFn: () =>
      get<{ notes: Note[] }>(
        `/notes?entity_type=${entityType}&entity_id=${encodeURIComponent(entityId)}`,
      ),
  })
}

export function useInvalidateNotes(entityType: string, entityId: string) {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['notes', entityType, entityId] })
    // Full views embed note lists in their own payloads
    qc.invalidateQueries({ queryKey: ['conversation-full'] })
    qc.invalidateQueries({ queryKey: ['entity-detail', entityType, entityId] })
  }
}

export const notesApi = {
  create: (body: {
    entity_type: string
    entity_id: string
    title?: string
    content_json?: string
    content_html?: string
    attachment_ids?: string[]
  }) => post<Note>('/notes', body),

  update: (noteId: string, body: {
    title?: string
    content_json?: string
    content_html?: string
    attachment_ids?: string[]
  }) => put<Note>(`/notes/${noteId}`, body),

  full: (noteId: string) => get<Note>(`/notes/${noteId}/full`),

  remove: (noteId: string) => del<{ ok: boolean }>(`/notes/${noteId}`),

  pin: (noteId: string, entityType: string, entityId: string) =>
    post<{ note: Note; is_pinned: boolean }>(`/notes/${noteId}/pin`, {
      entity_type: entityType,
      entity_id: entityId,
    }),

  revisions: (noteId: string) =>
    get<{ revisions: NoteRevision[]; current_revision_id: string | null }>(
      `/notes/${noteId}/revisions`,
    ),

  revision: (noteId: string, revisionId: string) =>
    get<NoteRevision>(`/notes/${noteId}/revisions/${revisionId}`),

  upload: async (file: File): Promise<{ id: string; url: string; original_name: string }> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/v1/notes/upload', {
      method: 'POST',
      body: form,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.error || `Upload failed (${res.status})`)
    }
    return res.json()
  },

  mentions: (q: string, type = 'user') =>
    get<MentionHit[]>(
      `/notes/mentions?q=${encodeURIComponent(q)}&type=${type}`,
    ),
}
