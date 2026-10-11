import { describe, expect, it } from 'vitest'
import { describeReturn, fromLocalInputValue, snoozeOptions } from './snoozeTimes.ts'

const local = (y: number, m: number, d: number, h = 0) => new Date(y, m - 1, d, h, 0, 0, 0)

describe('snoozeOptions (MAIL-28)', () => {
  it('offers later today only while 6 pm is at least an hour away', () => {
    const wed = local(2026, 10, 14, 10)   // Wednesday 10:00
    const keys = snoozeOptions(wed).map((o) => o.key)
    expect(keys).toEqual(['later_today', 'tomorrow', 'weekend', 'next_week'])
    const lateAfternoon = new Date(2026, 9, 14, 17, 30)
    expect(snoozeOptions(lateAfternoon).map((o) => o.key)).toEqual(['tomorrow', 'weekend', 'next_week'])
  })

  it('lands on tomorrow 8 am, Saturday 8 am, Monday 8 am in local time', () => {
    const wed = local(2026, 10, 14, 10)
    const by = Object.fromEntries(snoozeOptions(wed).map((o) => [o.key, new Date(o.at)]))
    expect(by.later_today.getTime()).toBe(local(2026, 10, 14, 18).getTime())
    expect(by.tomorrow.getTime()).toBe(local(2026, 10, 15, 8).getTime())
    expect(by.weekend.getTime()).toBe(local(2026, 10, 17, 8).getTime())   // Saturday
    expect(by.next_week.getTime()).toBe(local(2026, 10, 19, 8).getTime()) // Monday
  })

  it('from Saturday the weekend means the next Saturday and next week the coming Monday', () => {
    const sat = local(2026, 10, 17, 10)
    const by = Object.fromEntries(snoozeOptions(sat).map((o) => [o.key, new Date(o.at)]))
    expect(by.weekend.getTime()).toBe(local(2026, 10, 24, 8).getTime())
    expect(by.next_week.getTime()).toBe(local(2026, 10, 19, 8).getTime())
  })

  it('custom times must be in the future', () => {
    const now = local(2026, 10, 14, 10)
    expect(fromLocalInputValue('2026-10-14T09:00', now)).toBeNull()
    expect(fromLocalInputValue('', now)).toBeNull()
    expect(fromLocalInputValue('2026-10-14T11:30', now)).toBe(new Date(2026, 9, 14, 11, 30).toISOString())
  })

  it('describes a return time relative to today', () => {
    const now = local(2026, 10, 14, 10)
    expect(describeReturn(local(2026, 10, 14, 18).toISOString(), now)).toMatch(/^Today /)
    expect(describeReturn(local(2026, 10, 15, 8).toISOString(), now)).toMatch(/^Tomorrow /)
    expect(describeReturn(local(2026, 10, 17, 8).toISOString(), now)).toMatch(/^Sat /)
    expect(describeReturn(local(2026, 11, 2, 8).toISOString(), now)).toMatch(/^Nov 2, /)
  })
})
