/** Thread list in email rows (MAIL-23).
 *
 * Virtualized rows, a selection model (x toggles, Shift+click ranges,
 * Ctrl/Cmd+A selects the loaded rows), j/k/Enter keyboard movement, and
 * offset paging that loads the next page as the user nears the bottom.
 * Unread weight, account chip in the unified view, star and attachment
 * marks. The full keyboard model (actions) lives in MAIL-30.
 */

import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Clock, Hourglass, Paperclip, Star } from 'lucide-react'
import { threadKey, type ThreadSummary } from '../../api/mail.ts'
import { chipStyle } from '../../lib/accountColor.ts'
import { describeReturn } from '../../lib/snoozeTimes.ts'

export interface ThreadListProps {
  items: ThreadSummary[]
  total: number
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  error: string | null
  unified: boolean
  focusedKey: string | null
  openKey: string | null
  selectedKeys: Set<string>
  onFocus: (key: string | null) => void
  onOpen: (t: ThreadSummary) => void
  onToggleSelect: (key: string) => void
  onRangeSelect: (fromKey: string, toKey: string) => void
  onSelectAll: () => void
  onLoadMore: () => void
}

const ROW_HEIGHT = 68

function fmtDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  }
  const sameYear = d.getFullYear() === now.getFullYear()
  return d.toLocaleDateString([], sameYear ? { month: 'short', day: 'numeric' } : { year: '2-digit', month: 'short', day: 'numeric' })
}

function participantsLine(t: ThreadSummary): string {
  const names = t.participants.map((p) => (p.is_me ? 'me' : p.name?.split(' ')[0] || p.address.split('@')[0]))
  const line = names.slice(0, 3).join(', ')
  return t.message_count > 1 ? `${line} (${t.message_count})` : line
}

function accountChip(email: string): string {
  const domain = email.split('@')[1] ?? ''
  return domain.split('.')[0] || email.split('@')[0]
}

export function ThreadList(props: ThreadListProps) {
  const {
    items, total, loading, loadingMore, hasMore, error, unified,
    focusedKey, openKey, selectedKeys,
    onFocus, onOpen, onToggleSelect, onRangeSelect, onSelectAll, onLoadMore,
  } = props
  const scrollRef = useRef<HTMLDivElement>(null)
  const anchorRef = useRef<string | null>(null)

  const keys = useMemo(() => items.map(threadKey), [items])
  const focusedIndex = focusedKey ? keys.indexOf(focusedKey) : -1

  const virtualizer = useVirtualizer({
    count: items.length + (hasMore ? 1 : 0),
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  })

  // Load the next page when the sentinel row scrolls into view
  const virtualItems = virtualizer.getVirtualItems()
  useEffect(() => {
    const last = virtualItems[virtualItems.length - 1]
    if (!last) return
    if (hasMore && !loadingMore && last.index >= items.length - 1) onLoadMore()
  }, [virtualItems, hasMore, loadingMore, items.length, onLoadMore])

  // Keep the focused row visible
  useEffect(() => {
    if (focusedIndex >= 0) virtualizer.scrollToIndex(focusedIndex, { align: 'auto' })
  }, [focusedIndex, virtualizer])

  const move = useCallback((delta: number) => {
    if (items.length === 0) return
    const next = Math.min(items.length - 1, Math.max(0, (focusedIndex < 0 ? (delta > 0 ? -1 : 0) : focusedIndex) + delta))
    onFocus(keys[next])
  }, [items.length, focusedIndex, keys, onFocus])

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      e.preventDefault(); onSelectAll(); return
    }
    if (e.altKey || e.ctrlKey || e.metaKey) return
    switch (e.key) {
      case 'j': case 'ArrowDown': e.preventDefault(); move(1); break
      case 'k': case 'ArrowUp': e.preventDefault(); move(-1); break
      case 'Home': e.preventDefault(); if (keys[0]) onFocus(keys[0]); break
      case 'End': e.preventDefault(); if (keys.length) onFocus(keys[keys.length - 1]); break
      case 'Enter': case 'o':
        if (focusedIndex >= 0) { e.preventDefault(); onOpen(items[focusedIndex]) }
        break
      case 'x':
        if (focusedKey) { e.preventDefault(); onToggleSelect(focusedKey) }
        break
      default:
        break
    }
  }

  if (error) return <div className="p-3 text-sm text-red-700">Could not load threads: {error}</div>
  if (loading && items.length === 0) return <div className="p-3 text-sm text-surface-500">Loading…</div>

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-surface-200 px-3 py-1.5 text-xs text-surface-500">
        <span>
          {total} thread{total === 1 ? '' : 's'}
          {selectedKeys.size > 0 ? ` · ${selectedKeys.size} selected` : ''}
        </span>
        {items.length < total && <span>{items.length} loaded</span>}
      </div>
      {items.length === 0 ? (
        <div className="p-3 text-sm text-surface-500">Nothing here.</div>
      ) : (
        <div
          ref={scrollRef}
          tabIndex={0}
          role="listbox"
          aria-label="Threads"
          onKeyDown={onKeyDown}
          className="min-h-0 flex-1 overflow-y-auto outline-none focus-visible:ring-1 focus-visible:ring-primary-300"
        >
          <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
            {virtualItems.map((row) => {
              if (row.index >= items.length) {
                return (
                  <div
                    key="sentinel"
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: row.size, transform: `translateY(${row.start}px)` }}
                    className="flex items-center justify-center text-xs text-surface-400"
                  >
                    {loadingMore ? 'Loading more…' : ''}
                  </div>
                )
              }
              const t = items[row.index]
              const key = keys[row.index]
              const unread = t.unread_count > 0
              const isOpen = key === openKey
              const isFocused = key === focusedKey
              const isSelected = selectedKeys.has(key)
              return (
                <div
                  key={key}
                  role="option"
                  aria-selected={isSelected}
                  style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: row.size, transform: `translateY(${row.start}px)` }}
                  onClick={(e) => {
                    if (e.shiftKey && anchorRef.current) {
                      onRangeSelect(anchorRef.current, key)
                    } else if (e.ctrlKey || e.metaKey) {
                      anchorRef.current = key
                      onToggleSelect(key)
                    } else {
                      anchorRef.current = key
                      onFocus(key)
                      onOpen(t)
                    }
                  }}
                  className={`flex cursor-pointer gap-2 border-b border-surface-100 px-2 py-1.5 text-left ${
                    isOpen ? 'bg-primary-50' : isSelected ? 'bg-amber-50' : 'hover:bg-surface-50'
                  } ${isFocused ? 'ring-1 ring-inset ring-primary-300' : ''}`}
                >
                  <label className="flex shrink-0 items-start pt-0.5" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => { anchorRef.current = key; onToggleSelect(key) }}
                      className="h-3.5 w-3.5 accent-primary-600"
                      aria-label="Select thread"
                    />
                  </label>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`min-w-0 flex-1 truncate text-sm ${unread ? 'font-semibold text-surface-900' : 'text-surface-700'}`}>
                        {participantsLine(t)}
                      </span>
                      {unified && (
                        <span
                          className={`rounded px-1 text-[10px] uppercase tracking-wide ${t.account_color ? 'font-semibold' : 'bg-surface-100 text-surface-500'}`}
                          style={chipStyle(t.account_color)}
                          title={t.account_email}
                          data-testid="account-chip"
                        >
                          {accountChip(t.account_email)}
                        </span>
                      )}
                      {t.snoozed_until ? (
                        <span className="inline-flex shrink-0 items-center gap-1 rounded bg-amber-50 px-1 text-[11px] text-amber-700" title={`Returns ${describeReturn(t.snoozed_until)}`} data-testid="snooze-chip">
                          <Clock size={11} /> {describeReturn(t.snoozed_until)}
                        </span>
                      ) : typeof t.awaiting_days === 'number' ? (
                        <span className="inline-flex shrink-0 items-center gap-1 rounded bg-surface-100 px-1 text-[11px] text-surface-600" title={`Sent ${fmtDate(t.last_at)}, no reply yet`} data-testid="awaiting-chip">
                          <Hourglass size={11} /> {t.awaiting_days === 0 ? 'today' : `${t.awaiting_days} day${t.awaiting_days === 1 ? '' : 's'}`}
                        </span>
                      ) : (
                        <span className={`shrink-0 text-xs ${unread ? 'font-semibold text-primary-700' : 'text-surface-500'}`}>{fmtDate(t.last_at)}</span>
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5">
                      <span className={`min-w-0 flex-1 truncate text-sm ${unread ? 'font-medium text-surface-900' : 'text-surface-700'}`}>
                        {t.subject}
                      </span>
                      {t.has_attachments && <Paperclip size={12} className="shrink-0 text-surface-400" />}
                      {t.starred && <Star size={12} className="shrink-0 fill-amber-400 text-amber-400" />}
                    </div>
                    <div className="mt-0.5 truncate text-xs text-surface-500">{t.snippet}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
