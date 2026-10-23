import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { ContextColumn } from './ContextColumn.tsx'
import { externalParticipants } from '../../lib/mailParticipants.ts'
import { renderWithQuery, stubFetch } from '../../test/utils.tsx'
import type { ThreadDetail } from '../../api/mail.ts'

const thread: ThreadDetail = {
  account_id: 'a', account_email: 'me@x.com', thread_id: 't1', subject: 'Lunch?', labels: [],
  message_count: 2, unread_count: 0,
  conversation: { id: 'cv1', title: 'Lunch with Ada', ai_summary: 'Planning a lunch.', ai_status: 'OPEN' },
  messages: [
    { id: 'm1', timestamp: '2026-10-01T12:00:00+00:00', direction: 'inbound', subject: 'Lunch?', snippet: '',
      sender: { address: 'ada@example.com', name: 'Ada', contact_id: 'ct-ada', contact_name: 'Ada Lovelace', is_me: false },
      participants: [{ address: 'me@x.com', name: null, role: 'to', contact_id: null, contact_name: null },
                     { address: 'grace@hopper.test', name: 'Grace', role: 'cc', contact_id: null, contact_name: null }],
      body_html: '', body_text: '', is_read: true, is_starred: false, is_archived: false, labels: [], attachments: [],
      header_message_id: null, provider_message_id: 'm1' },
    { id: 'm2', timestamp: '2026-10-02T12:00:00+00:00', direction: 'outbound', subject: 'Re: Lunch?', snippet: '',
      sender: { address: 'me@x.com', name: 'Me', contact_id: null, contact_name: null, is_me: true },
      participants: [{ address: 'ada@example.com', name: 'Ada', role: 'to', contact_id: 'ct-ada', contact_name: 'Ada Lovelace' }],
      body_html: '', body_text: '', is_read: true, is_starred: false, is_archived: false, labels: [], attachments: [],
      header_message_id: null, provider_message_id: 'm2' },
  ],
}

describe('ContextColumn (MAIL-32)', () => {
  it('lists external participants, senders first, without me', () => {
    const people = externalParticipants(thread)
    expect(people.map((p) => p.address)).toEqual(['ada@example.com', 'grace@hopper.test'])
  })

  it('shows the conversation summary, the contact card, and a create-contact affordance', async () => {
    stubFetch({
      '/api/v1/contacts/ct-ada': {
        identity: { name: 'Ada Lovelace', subtitle: 'Engineer', company: { id: 'co1', name: 'Analytical' }, score: 72.4, status: 'active' },
        context: { affiliations: [{ company_name: 'Analytical', title: 'Engineer', is_current: true }] },
        timeline: [{ type: 'conversation', id: 'cv0', title: 'Budget', date: '2026-09-01', summary: 'Agreed the budget.' }],
      },
    })
    renderWithQuery(<ContextColumn thread={thread} />)
    expect(screen.getByText('Lunch with Ada')).toBeInTheDocument()
    expect(screen.getByText('Planning a lunch.')).toBeInTheDocument()
    expect(await screen.findByText('Engineer · Analytical')).toBeInTheDocument()
    expect(screen.getByTitle('Relationship score')).toHaveTextContent('72')
    expect(screen.getByText('Budget')).toBeInTheDocument()
    expect(screen.getByText('Open contact')).toBeInTheDocument()
    expect(screen.getByText('Create contact for Grace')).toBeInTheDocument()
  })
})
