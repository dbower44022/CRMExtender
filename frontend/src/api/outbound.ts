import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, patch, del } from './client.ts'

// --- Types ---

export interface Recipient {
  email: string
  contact_id?: string | null
  name?: string | null
}

export interface OutboundDraft {
  id: string
  from_account_id: string
  to_addresses: Recipient[]
  cc_addresses: Recipient[]
  bcc_addresses: Recipient[]
  subject: string
  body_json: string
  body_html: string
  body_text: string
  source_type: string
  status: string
  signature_id: string | null
  reply_to_communication_id: string | null
  forward_of_communication_id: string | null
  conversation_id: string | null
  created_at: string
  updated_at: string
}

export interface ComposeContextData {
  to_addresses: Recipient[]
  cc_addresses: Recipient[]
  subject: string
  quoted_html: string
  in_reply_to: string | null
  references: string | null
  thread_id: string | null
  conversation_id: string | null
  default_account_id: string | null
  reply_to_communication_id?: string | null
  forward_of_communication_id?: string | null
}

export interface SendResult {
  queue_id: string
  status: string
  communication_id?: string
  failure_reason?: string
}

export interface Signature {
  id: string
  name: string
  body_json: string
  body_html: string
  provider_account_id: string | null
  is_default: number
  created_at: string
  updated_at: string
}

// --- Drafts ---

export function useCreateDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      from_account_id: string
      to_addresses: Recipient[]
      cc_addresses?: Recipient[]
      bcc_addresses?: Recipient[]
      subject: string
      body_json: string
      body_html: string
      body_text: string
      source_type?: string
      reply_to_communication_id?: string | null
      forward_of_communication_id?: string | null
      conversation_id?: string | null
      signature_id?: string | null
    }) => post<OutboundDraft>('/outbound-emails', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['outbound-drafts'] })
    },
  })
}

export function useUpdateDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      draftId,
      ...data
    }: {
      draftId: string
      to_addresses?: Recipient[]
      cc_addresses?: Recipient[]
      bcc_addresses?: Recipient[]
      subject?: string
      body_json?: string
      body_html?: string
      body_text?: string
      signature_id?: string | null
    }) => patch<OutboundDraft>(`/outbound-emails/${draftId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['outbound-drafts'] })
    },
  })
}

export function useSendEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (draftId: string) =>
      post<SendResult>(`/outbound-emails/${draftId}/send`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['outbound-drafts'] })
    },
  })
}

export function useCancelDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (draftId: string) =>
      post<{ ok: boolean }>(`/outbound-emails/${draftId}/cancel`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['outbound-drafts'] })
    },
  })
}

export function useListDrafts() {
  return useQuery({
    queryKey: ['outbound-drafts'],
    queryFn: () => get<OutboundDraft[]>('/outbound-emails/drafts'),
    staleTime: 30 * 1000,
  })
}

// --- Compose Context ---

export function useComposeContext(
  communicationId: string | null | undefined,
  action: string | null | undefined,
) {
  const params = new URLSearchParams()
  if (communicationId) params.set('communication_id', communicationId)
  if (action) params.set('action', action)

  return useQuery({
    queryKey: ['compose-context', communicationId, action],
    queryFn: () =>
      get<ComposeContextData>(`/outbound-emails/compose-context?${params.toString()}`),
    enabled: !!communicationId && !!action,
    staleTime: 60 * 1000,
  })
}

// --- Sender Resolution ---

export function useResolveSender(params: {
  reply_to_communication_id?: string | null
  to_email?: string | null
}) {
  return useQuery({
    queryKey: ['resolve-sender', params.reply_to_communication_id, params.to_email],
    queryFn: () =>
      post<{ account_id: string | null }>('/outbound-emails/resolve-sender', params),
    enabled: false, // manual trigger only
  })
}

// --- Signatures ---

export function useSignatures() {
  return useQuery({
    queryKey: ['signatures'],
    queryFn: () => get<Signature[]>('/signatures'),
    staleTime: 60 * 1000,
  })
}

export function useCreateSignature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      name: string
      body_json: string
      body_html: string
      provider_account_id?: string | null
      is_default?: boolean
    }) => post<Signature>('/signatures', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['signatures'] })
    },
  })
}

export function useUpdateSignature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      signatureId,
      ...data
    }: {
      signatureId: string
      name?: string
      body_json?: string
      body_html?: string
      provider_account_id?: string | null
      is_default?: boolean
    }) => patch<Signature>(`/signatures/${signatureId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['signatures'] })
    },
  })
}

export function useDeleteSignature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (signatureId: string) =>
      del<{ ok: boolean }>(`/signatures/${signatureId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['signatures'] })
    },
  })
}
