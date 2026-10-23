import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { renderWithQuery, stubFetch } from '../../test/utils.tsx'
import { MergeContactsModal } from './MergeContactsModal.tsx'

const contact = (id: string, name: string, email: string) => ({
  id, name, source: 'google_contacts', identifier_count: 1, affiliation_count: 0, conversation_count: 0,
  relationship_count: 0, event_count: 0, phone_count: 0, address_count: 0, email_count: 0, social_profile_count: 0,
  identifiers: [{ type: 'email', value: email }], affiliations: [],
})
const preview = {
  contacts: [contact('c1', 'Mo Yahyaei', 'mohammadyahyaei@case.edu'), contact('c2', 'Mohammad Yahyaei', 'mxy593@case.edu'), contact('c3', 'Mo Yahyaei', 'm.y@case.edu')],
  conflicts: { name: ['Mo Yahyaei', 'Mohammad Yahyaei'], source: ['google_contacts'] },
  totals: { identifiers: 3, combined_identifiers: 3, affiliations: 0, combined_affiliations: 0, conversations: 0, relationships: 0, events: 0, phones: 0, addresses: 0, emails: 0, social_profiles: 0 },
}

describe('MergeContactsModal', () => {
  it('names the merged contact after the chosen survivor, and lets a name be picked or typed', async () => {
    const calls = stubFetch({
      '/api/v1/contacts/merge-preview': preview,
      '/api/v1/contacts/merge': { surviving_id: 'c2', absorbed_ids: ['c1', 'c3'], identifiers_transferred: 2, conversations_reassigned: 0 },
    })
    renderWithQuery(<MergeContactsModal contactIds={['c1', 'c2', 'c3']} onClose={vi.fn()} />)
    const nameField = await screen.findByLabelText('Name after merge')
    expect(nameField).toHaveValue('Mo Yahyaei')                       // first contact survives by default
    // choosing the second card as survivor changes the default name to its own
    const survivorRadios = Array.from(document.querySelectorAll<HTMLInputElement>('input[name="surviving"]'))
    expect(survivorRadios.length).toBe(3)
    fireEvent.click(survivorRadios[1])
    expect(nameField).toHaveValue('Mohammad Yahyaei')
    // a typed name wins
    fireEvent.change(nameField, { target: { value: 'Mohammad Yahyaei Ferizhendi' } })
    fireEvent.click(screen.getByText('Confirm Merge'))
    await waitFor(() => {
      const post = calls.find((c) => c.url.endsWith('/contacts/merge') && c.init?.method === 'POST')
      expect(post).toBeTruthy()
      expect(JSON.parse(String(post!.init?.body))).toMatchObject({ surviving_id: 'c2', absorbed_ids: ['c1', 'c3'], chosen_name: 'Mohammad Yahyaei Ferizhendi' })
    })
  })
})
