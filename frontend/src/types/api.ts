export interface FieldDef {
  label: string
  type: 'text' | 'number' | 'datetime' | 'select' | 'hidden'
  sortable: boolean
  filterable: boolean
  link: string | null
  editable: boolean
  db_column: string | null
  select_options: string[] | null
}

export interface EntityDef {
  label: string
  detail_url: string
  fields: Record<string, FieldDef>
  default_columns: string[]
  default_sort: [string, string]
  search_fields: string[]
}

export interface ViewColumn {
  id: string
  view_id: string
  field_key: string
  position: number
  label_override: string | null
  width_px: number | null
}

export interface ViewFilter {
  id: string
  view_id: string
  field_key: string
  operator: string
  value: string | null
  position: number
}

export interface View {
  id: string
  customer_id: string
  data_source_id: string
  name: string
  view_type: string
  owner_id: string
  visibility: 'personal' | 'shared'
  is_default: number
  sort_field: string
  sort_direction: 'asc' | 'desc'
  per_page: number
  entity_type: string
  preview_panel_size: 'none' | 'small' | 'medium' | 'large' | 'huge'
  auto_density: number
  column_auto_sizing: number
  column_demotion: number
  primary_identifier_field: string | null
  created_at: string
  updated_at: string
  columns: ViewColumn[]
  filters: ViewFilter[]
}

export interface ViewDataResponse {
  rows: Record<string, unknown>[]
  total: number
  page: number
  per_page: number
  has_more: boolean
}

export interface EntityDetailResponse {
  identity: Record<string, unknown>
  context: Record<string, unknown>
  timeline: TimelineEntry[]
}

export interface TimelineEntry {
  type: 'communication' | 'conversation' | 'event' | 'note'
  id: string
  title: string
  date: string
  summary?: string
  icon?: string
}

export interface HealthResponse {
  status: string
  version: string
}

// --- View mutation types ---

export interface CreateViewRequest {
  entity_type: string
  name: string
}

export interface UpdateViewRequest {
  name?: string
  sort_field?: string
  sort_direction?: 'asc' | 'desc'
  per_page?: number
  visibility?: 'personal' | 'shared'
}

export interface UpdateColumnsRequest {
  columns: (string | { key: string; label?: string; width?: number })[]
}

export interface UpdateFiltersRequest {
  filters: { field_key: string; operator: string; value?: string | null }[]
}

export interface CellEditRequest {
  entity_type: string
  entity_id: string
  field_key: string
  value: string
}

export interface CellEditResponse {
  ok: boolean
  value?: string
  error?: string
}

export interface QuickFilter {
  field_key: string
  operator: string
  value?: string
}

// --- Adaptive Grid Intelligence types ---

export type DisplayTier = 'ultra_wide' | 'spacious' | 'standard' | 'constrained' | 'minimal'

export interface DisplayProfile {
  viewportWidth: number
  viewportHeight: number
  devicePixelRatio: number
  effectiveWidth: number
  effectiveHeight: number
  displayTier: DisplayTier
}

export interface ColumnMetrics {
  fieldKey: string
  maxContentWidth: number
  medianContentWidth: number
  p90ContentWidth: number
  minContentWidth: number
  diversityScore: number
  nullRatio: number
  dominantValue: string | null
  digitCountRange: [number, number] | null
}

export type DemotionTier = 'normal' | 'annotated' | 'collapsed' | 'header_only' | 'hidden'
export type CellAlignment = 'left' | 'center' | 'right'

export interface ComputedColumn {
  fieldKey: string
  computedWidth: number
  alignment: CellAlignment
  demotionTier: DemotionTier
  dominantValue: string | null
  priorityClass: number
}

export interface ComputedLayout {
  displayProfile: DisplayProfile
  columns: ComputedColumn[]
  demotedCount: number
  hiddenCount: number
}

export interface LayoutOverride {
  id: string
  user_id: string
  view_id: string
  display_tier: DisplayTier
  splitter_pct: number | null
  density: 'compact' | 'standard' | 'comfortable' | null
  column_overrides: Record<string, Record<string, unknown>>
  created_at: string
  updated_at: string
}

// --- Create Contact / Company types ---

export interface CreateContactRequest {
  name: string
  email?: string
  source?: string
}

export interface CreateCompanyRequest {
  name: string
  domain?: string
  industry?: string
  website?: string
  headquarters_location?: string
}

// --- Contact Merge types ---

export interface MergePreviewContact {
  id: string
  name: string
  source: string | null
  status: string | null
  identifier_count: number
  affiliation_count: number
  conversation_count: number
  relationship_count: number
  event_count: number
  phone_count: number
  address_count: number
  email_count: number
  social_profile_count: number
  identifiers: { type: string; value: string; is_primary: number }[]
  affiliations: { company_name: string; role_name: string | null; title: string | null }[]
}

export interface MergePreview {
  contacts: MergePreviewContact[]
  conflicts: {
    name: string[]
    source: string[]
  }
  totals: {
    identifiers: number
    combined_identifiers: number
    affiliations: number
    combined_affiliations: number
    conversations: number
    relationships: number
    events: number
    phones: number
    addresses: number
    emails: number
    social_profiles: number
  }
}

export interface MergeRequest {
  surviving_id: string
  absorbed_ids: string[]
  chosen_name?: string
  chosen_source?: string
}

export interface MergeResult {
  merge_ids: string[]
  surviving_id: string
  absorbed_ids: string[]
  identifiers_transferred: number
  affiliations_transferred: number
  affiliations_created: number
  conversations_reassigned: number
  relationships_reassigned: number
  events_reassigned: number
  relationships_deduplicated: number
}

// --- Company Merge types ---

export interface CompanyMergePreviewCompany {
  id: string
  name: string
  domain: string | null
  industry: string | null
  status: string | null
  contact_count: number
  relationship_count: number
  event_count: number
  identifier_count: number
  phone_count: number
  address_count: number
  email_count: number
  social_profile_count: number
}

export interface CompanyMergePreview {
  companies: CompanyMergePreviewCompany[]
  conflicts: {
    name: string[]
    domain: string[]
    industry: string[]
  }
  totals: {
    contacts: number
    relationships: number
    events: number
    identifiers: number
    phones: number
    addresses: number
    emails: number
    social_profiles: number
  }
}

export interface CompanyMergeRequest {
  surviving_id: string
  absorbed_ids: string[]
}

export interface CompanyMergeResult {
  merge_ids: string[]
  surviving_id: string
  absorbed_ids: string[]
  contacts_reassigned: number
  relationships_reassigned: number
  events_reassigned: number
}
