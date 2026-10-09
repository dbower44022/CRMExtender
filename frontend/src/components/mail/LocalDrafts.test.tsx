import { beforeEach, describe, expect, it } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import { renderWithQuery, stubFetch } from '../../test/utils.tsx'
import { useComposeStore } from '../../stores/compose.ts'
import { LocalDrafts } from './LocalDrafts.tsx'

describe('LocalDrafts (MAIL-35)', () => {
  beforeEach(() => useComposeStore.setState({ composers: [], pendingSends: [] }))

  it('lists drafts written here and resumes one in a docked composer', async () => {
    stubFetch({
      '/api/v1/outbound-emails/drafts': [
        { id: 'd1', from_account_id: 'a', to_addresses: [{ email: 'bob@test.com', name: 'Bob' }], cc_addresses: [], bcc_addresses: [],
          subject: 'Hello Bob', body_json: '{}', body_html: '', body_text: '', source_type: 'manual', status: 'draft', signature_id: null,
          reply_to_communication_id: null, forward_of_communication_id: null, conversation_id: null, created_at: '', updated_at: '2026-10-09T10:00:00Z' },
      ],
    })
    renderWithQuery(<LocalDrafts />)
    await screen.findByText('Hello Bob')
    expect(screen.getByText('Bob')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Hello Bob'))
    const c = useComposeStore.getState().composers
    expect(c.length).toBe(1)
    expect(c[0]).toMatchObject({ draftId: 'd1', placement: 'dock', mode: 'new' })
    expect(c[0].resume?.subject).toBe('Hello Bob')
  })
})
