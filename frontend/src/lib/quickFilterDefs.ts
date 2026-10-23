/**
 * Quick filter chips per entity type (Views & Grid PRD §10; conversation
 * chips per Conversation Base PRD §6.4). Kept out of the component file so
 * tests can import the definitions without rendering.
 */

import type { QuickFilter } from '../types/api.ts'

export interface QuickFilterDef {
  label: string
  filter: QuickFilter
}

export const QUICK_FILTERS: Record<string, QuickFilterDef[]> = {
  contact: [
    { label: 'Active', filter: { field_key: 'status', operator: 'equals', value: 'active' } },
    { label: 'Inactive', filter: { field_key: 'status', operator: 'equals', value: 'inactive' } },
  ],
  company: [
    { label: 'Active', filter: { field_key: 'status', operator: 'equals', value: 'active' } },
  ],
  conversation: [
    // `status` is System Status (active | stale | done; Base PRD §6.1). The grid
    // hides done rows unless a filter names status, so Done is the way in.
    { label: 'Active', filter: { field_key: 'status', operator: 'equals', value: 'active' } },
    { label: 'Stale', filter: { field_key: 'status', operator: 'equals', value: 'stale' } },
    { label: 'Done', filter: { field_key: 'status', operator: 'equals', value: 'done' } },
    // ai_status is the summarizer's verdict; prefixed so Done and AI closed differ on sight.
    { label: 'AI open', filter: { field_key: 'ai_status', operator: 'equals', value: 'open' } },
    { label: 'AI closed', filter: { field_key: 'ai_status', operator: 'equals', value: 'closed' } },
    { label: 'AI uncertain', filter: { field_key: 'ai_status', operator: 'equals', value: 'uncertain' } },
  ],
  event: [
    { label: 'Upcoming', filter: { field_key: 'start', operator: 'is_after', value: new Date().toISOString().slice(0, 10) } },
  ],
}
