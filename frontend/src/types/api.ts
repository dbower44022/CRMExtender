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
