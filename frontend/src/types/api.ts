export interface FieldDef {
  label: string
  type: 'text' | 'number' | 'datetime' | 'select' | 'hidden'
  sortable: boolean
  filterable: boolean
  link: string | null
  editable: boolean
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
