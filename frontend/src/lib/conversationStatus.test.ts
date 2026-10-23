import { describe, expect, it } from 'vitest'
import {
  conversationStatusClass,
  conversationStatusLabel,
  isConversationDone,
  reopenReasonLabel,
} from './conversationStatus.ts'

describe('conversation status display (CONV-DNT-12)', () => {
  it('renders done as Done in the grey style', () => {
    expect(conversationStatusLabel('done')).toBe('Done')
    expect(conversationStatusClass('done')).toBe('bg-surface-100 text-surface-500')
    expect(isConversationDone('done')).toBe(true)
  })

  it('renders active as Active in the green style', () => {
    expect(conversationStatusLabel('active')).toBe('Active')
    expect(conversationStatusClass('active')).toBe('bg-green-50 text-green-700')
    expect(isConversationDone('active')).toBe(false)
  })

  it('falls back for unknown and empty values', () => {
    expect(conversationStatusLabel(null)).toBe('')
    expect(conversationStatusLabel('odd')).toBe('Odd')
    expect(conversationStatusClass(undefined)).toBe('bg-surface-100 text-surface-500')
    expect(isConversationDone(null)).toBe(false)
  })

  it('names the reopen reasons', () => {
    expect(reopenReasonLabel('inbound')).toBe('New inbound message')
    expect(reopenReasonLabel('user')).toBe('Reopened by user')
    expect(reopenReasonLabel(null)).toBe('')
  })
})
