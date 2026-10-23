import { describe, expect, it } from 'vitest'
import { QUICK_FILTERS } from './quickFilterDefs.ts'

describe('conversation quick filters (CONV-DNT-11)', () => {
  const defs = QUICK_FILTERS.conversation

  it('offers Active and Done chips on System Status', () => {
    const byLabel = Object.fromEntries(defs.map((d) => [d.label, d.filter]))
    expect(byLabel.Active).toEqual({ field_key: 'status', operator: 'equals', value: 'active' })
    expect(byLabel.Stale).toEqual({ field_key: 'status', operator: 'equals', value: 'stale' })
    expect(byLabel.Done).toEqual({ field_key: 'status', operator: 'equals', value: 'done' })
  })

  it('prefixes the AI Status chips so Done and AI closed cannot be misread', () => {
    const aiChips = defs.filter((d) => d.filter.field_key === 'ai_status')
    expect(aiChips.map((d) => d.label)).toEqual(['AI open', 'AI closed', 'AI uncertain'])
    expect(aiChips.map((d) => d.filter.value)).toEqual(['open', 'closed', 'uncertain'])
  })

  it('lists the status chips before the AI chips (CONV-DNT-18)', () => {
    expect(defs.map((d) => d.label).slice(0, 3)).toEqual(['Active', 'Stale', 'Done'])
  })
})
