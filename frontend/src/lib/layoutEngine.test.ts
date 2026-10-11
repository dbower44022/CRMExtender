import { describe, expect, it } from 'vitest'
import { computeLayout } from './layoutEngine.ts'
import type { EntityDef, FieldDef, ViewColumn } from '../types/api.ts'

// Content analysis measures text with a canvas, which jsdom does not draw.
HTMLCanvasElement.prototype.getContext = (() =>
  ({ font: '', measureText: (t: string) => ({ width: t.length * 7 }) })) as unknown as typeof HTMLCanvasElement.prototype.getContext

const field = (label: string, extra: Partial<FieldDef> = {}): FieldDef => ({
  label,
  type: 'text',
  sortable: true,
  filterable: true,
  link: null,
  editable: false,
  db_column: null,
  select_options: null,
  ...extra,
})

const entityDef: EntityDef = {
  label: 'Conversations',
  detail_url: '/conversations/{id}',
  fields: {
    title: field('Subject'),
    account_name: field('Account', { demotable: false }),
    status: field('Status'),
  },
  default_columns: ['title', 'account_name', 'status'],
  default_sort: ['title', 'asc'],
  search_fields: [],
} as unknown as EntityDef

const col = (field_key: string, position: number): ViewColumn =>
  ({ id: field_key, view_id: 'v', field_key, position, label_override: null, width_px: null }) as ViewColumn

// 50 rows: unique subjects, one mailbox on every row, one status on every row.
const rows = Array.from({ length: 50 }, (_, i) => ({
  title: `Subject ${i}`,
  account_name: 'doug.bower@cbmentors.org',
  status: 'active',
}))

describe('computeLayout demotion exemption (Adaptive Grid PRD §12.4)', () => {
  it('never demotes a column the registry marks demotable: false', () => {
    const layout = computeLayout({
      rows,
      viewColumns: [col('title', 0), col('account_name', 1), col('status', 2)],
      entityDef,
    })
    const tier = (k: string) => layout.columns.find((c) => c.fieldKey === k)?.demotionTier
    expect(tier('account_name')).toBe('normal')
    expect(tier('status')).not.toBe('normal') // uniform column still demoted
  })
})
