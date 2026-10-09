import { describe, expect, it } from 'vitest'
import { defaultSignature, isInlineVisible, scheduleOptions, secondsLeft } from './composeUi.ts'
import type { Signature } from '../api/outbound.ts'
import type { Composer } from '../stores/compose.ts'

const sig = (over: Partial<Signature>): Signature => ({
  id: 'x', name: 'n', body_json: '{}', body_html: '<p>s</p>', provider_account_id: null, is_default: 0,
  created_at: '', updated_at: '', ...over,
})

describe('composeUi (MAIL-34/35)', () => {
  it('prefers the account default signature, then the overall default, in server order', () => {
    const all = [sig({ id: 'g', is_default: 1 }), sig({ id: 'a', is_default: 1, provider_account_id: 'acct1' }), sig({ id: 'z' })]
    expect(defaultSignature(all, 'acct1')?.id).toBe('a')
    expect(defaultSignature(all, 'acct2')?.id).toBe('g')
    expect(defaultSignature([sig({ id: 'z' })], 'acct1')).toBeNull()
  })

  it('offers tomorrow and Monday mornings at 8:00, plus a same-day slot in working hours', () => {
    const wed = new Date(2026, 9, 7, 10, 15) // Wed 7 Oct 2026
    const opts = scheduleOptions(wed)
    expect(opts.map((o) => o.label)).toEqual(['In 3 hours', 'Tomorrow morning', 'Monday morning'])
    expect(opts[1].at.getDate()).toBe(8); expect(opts[1].at.getHours()).toBe(8)
    expect(opts[2].at.getDay()).toBe(1); expect(opts[2].at.getDate()).toBe(12)
    const late = new Date(2026, 9, 7, 17, 0)
    expect(scheduleOptions(late).map((o) => o.label)).toEqual(['Tomorrow morning', 'Monday morning'])
  })

  it('shows an inline composer only while its thread is open in mail mode', () => {
    const c: Composer = { id: 'c1', mode: 'reply', context: { threadKey: 'a:t1' }, draftId: null, placement: 'inline', minimized: false, resume: null }
    expect(isInlineVisible(c, true, 't1')).toBe(true)
    expect(isInlineVisible(c, true, 't2')).toBe(false)
    expect(isInlineVisible(c, false, 't1')).toBe(false)
    expect(isInlineVisible({ ...c, placement: 'dock' }, true, 't1')).toBe(false)
  })

  it('counts seconds left without going negative', () => {
    expect(secondsLeft(10_000, 4_100)).toBe(6)
    expect(secondsLeft(1_000, 5_000)).toBe(0)
  })
})
