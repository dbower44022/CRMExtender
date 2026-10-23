import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ThreadList } from './ThreadList.tsx'
import type { ThreadSummary } from '../../api/mail.ts'

function thread(n: number, over: Partial<ThreadSummary> = {}): ThreadSummary {
  return {
    account_id: 'a', account_email: 'me@dougbower.com', thread_id: `t${n}`, subject: `Subject ${n}`,
    snippet: `snippet ${n}`, last_at: '2026-10-01T12:00:00+00:00', message_count: 1, unread_count: 0,
    starred: false, has_attachments: false, labels: ['INBOX'],
    participants: [{ address: 'ada@example.com', name: 'Ada Lovelace', is_me: false }],
    latest_message_id: `m${n}`, ...over,
  }
}

function setup(items: ThreadSummary[], focusedKey: string | null = null) {
  const onFocus = vi.fn(); const onOpen = vi.fn(); const onToggleSelect = vi.fn()
  const onRangeSelect = vi.fn(); const onSelectAll = vi.fn(); const onLoadMore = vi.fn()
  render(
    <ThreadList
      items={items} total={items.length} loading={false} loadingMore={false} hasMore={false} error={null}
      unified focusedKey={focusedKey} openKey={null} selectedKeys={new Set()}
      onFocus={onFocus} onOpen={onOpen} onToggleSelect={onToggleSelect} onRangeSelect={onRangeSelect}
      onSelectAll={onSelectAll} onLoadMore={onLoadMore}
    />,
  )
  return { onFocus, onOpen, onToggleSelect, onRangeSelect, onSelectAll }
}

describe('ThreadList (MAIL-23, MAIL-T14)', () => {
  it('renders rows with unread weight, account chip, and marks', () => {
    setup([thread(1, { unread_count: 2, message_count: 3, starred: true, has_attachments: true }), thread(2)])
    expect(screen.getByText('Subject 1')).toHaveClass('font-medium')
    expect(screen.getByText('Subject 2')).not.toHaveClass('font-medium')
    expect(screen.getByText('Ada (3)')).toBeInTheDocument()
    expect(screen.getAllByText('dougbower').length).toBe(2)   // account chip in the unified view
    expect(screen.getByText('2 threads')).toBeInTheDocument()
  })

  it('j / k move focus and Enter opens; x toggles selection', () => {
    const items = [thread(1), thread(2), thread(3)]
    const h = setup(items, 'a:t1')
    const list = screen.getByRole('listbox')
    fireEvent.keyDown(list, { key: 'j' })
    expect(h.onFocus).toHaveBeenLastCalledWith('a:t2')
    fireEvent.keyDown(list, { key: 'k' })
    expect(h.onFocus).toHaveBeenLastCalledWith('a:t1')
    fireEvent.keyDown(list, { key: 'Enter' })
    expect(h.onOpen).toHaveBeenCalledWith(items[0])
    fireEvent.keyDown(list, { key: 'x' })
    expect(h.onToggleSelect).toHaveBeenCalledWith('a:t1')
    fireEvent.keyDown(list, { key: 'a', ctrlKey: true })
    expect(h.onSelectAll).toHaveBeenCalled()
  })

  it('click opens, ctrl-click toggles, shift-click selects a range', () => {
    const items = [thread(1), thread(2), thread(3)]
    const h = setup(items)
    fireEvent.click(screen.getByText('Subject 1'))
    expect(h.onOpen).toHaveBeenCalledWith(items[0])
    fireEvent.click(screen.getByText('Subject 2'), { ctrlKey: true })
    expect(h.onToggleSelect).toHaveBeenCalledWith('a:t2')
    fireEvent.click(screen.getByText('Subject 3'), { shiftKey: true })
    expect(h.onRangeSelect).toHaveBeenCalledWith('a:t2', 'a:t3')
  })

  it('shows the return time instead of the date on a snoozed thread (MAIL-28)', () => {
    const until = new Date(Date.now() + 26 * 60 * 60 * 1000).toISOString()
    setup([thread(1, { snoozed_until: until }), thread(2)])
    expect(screen.getAllByTestId('snooze-chip')).toHaveLength(1)
  })

  it('shows days waiting on an awaiting-reply thread (MAIL-47)', () => {
    setup([thread(1, { awaiting_days: 4, awaiting_since: '2026-10-07T12:00:00+00:00' })])
    expect(screen.getByTestId('awaiting-chip')).toHaveTextContent('4 days')
  })

  it('shows one chip per account on a thread mirrored in two mailboxes (MAIL-44, MAIL-T21)', () => {
    setup([thread(1, { accounts: [{ id: 'a', email: 'me@dougbower.com', color: null }, { id: 'b', email: 'doug.bower@cbmentors.org', color: '#445566' }] })])
    const chips = screen.getAllByTestId('account-chip')
    expect(chips.map((c) => c.textContent)).toEqual(['dougbower', 'cbmentors'])
  })

  it('shows the empty state', () => {
    setup([])
    expect(screen.getByText('Nothing here.')).toBeInTheDocument()
  })

  it('colours the account chip in the unified view with the account colour', async () => {
    setup([thread(1, { account_color: '#dc2626' }), thread(2, { account_email: 'me@case.edu', account_color: null })])
    const chips = await screen.findAllByTestId('account-chip')
    expect(chips[0]).toHaveTextContent('dougbower')
    expect(chips[0].style.color).toBe('rgb(220, 38, 38)')
    expect(chips[1]).toHaveTextContent('case')
    expect(chips[1].style.color).toBe('')
  })
})
