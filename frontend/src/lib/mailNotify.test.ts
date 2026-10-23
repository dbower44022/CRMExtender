import { describe, expect, it } from 'vitest'
import { describeNotifications, selectNotifications, type NewMailEvent, type NewMailItem } from './mailNotify.ts'

const item = (id: string, known: boolean, subject = `Subj ${id}`): NewMailItem => ({
  communication_id: id, thread_id: `t-${id}`, sender_address: `${id}@x.com`, sender_name: known ? `Name ${id}` : null,
  known_contact: known, subject, snippet: '', timestamp: '2026-10-09T14:00:00Z',
})
const ev = (items: NewMailItem[], count = items.length): NewMailEvent => ({ type: 'mail.new', account_id: 'a', email: 'me@x.com', count, items })

describe('mailNotify (MAIL-39)', () => {
  it('applies the account setting', () => {
    const e = ev([item('1', true), item('2', false)])
    expect(selectNotifications(e, 'none')).toBeNull()
    expect(selectNotifications(e, 'all')?.length).toBe(2)
    expect(selectNotifications(e, 'known_contacts')?.map((i) => i.communication_id)).toEqual(['1'])
    expect(selectNotifications(ev([item('2', false)]), 'known_contacts')).toBeNull()
  })

  it('announces up to three separately, then one summary with the real count', () => {
    const three = describeNotifications([item('1', true), item('2', true), item('3', true)], 3)
    expect(three.map((n) => n.title)).toEqual(['Name 1', 'Name 2', 'Name 3'])
    expect(three[0].item?.thread_id).toBe('t-1')
    const many = describeNotifications([item('1', true), item('2', true), item('3', true), item('4', true)], 12, 'me@x.com')
    expect(many.length).toBe(1)
    expect(many[0].title).toBe('12 new messages for me@x.com')
    expect(many[0].item).toBeUndefined()
  })
})
