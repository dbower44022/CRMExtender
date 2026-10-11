import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render } from '@testing-library/react'
import { useMailShortcuts, type ShortcutHandlers } from './useMailShortcuts.ts'

function Host({ h, enabled = true }: { h: ShortcutHandlers; enabled?: boolean }) {
  useMailShortcuts(enabled, h)
  return <div><input aria-label="field" /></div>
}

function handlers(): ShortcutHandlers {
  return {
    moveFocus: vi.fn(), openFocused: vi.fn(), toggleSelectFocused: vi.fn(), escape: vi.fn(),
    act: vi.fn(), reply: vi.fn(), compose: vi.fn(), snooze: vi.fn(), goFolder: vi.fn(), goAccount: vi.fn(),
    focusSearch: vi.fn(), toggleSheet: vi.fn(),
  }
}

// react-hotkeys-hook matches on event.code as well as key, so synthesize both.
function codeFor(k: string): string {
  if (/^[a-z]$/i.test(k)) return `Key${k.toUpperCase()}`
  if (/^[0-9]$/.test(k)) return `Digit${k}`
  return { Enter: 'Enter', Escape: 'Escape', '#': 'Digit3', '!': 'Digit1', '?': 'Slash', '/': 'Slash' }[k] ?? k
}
const key = (k: string, extra: KeyboardEventInit = {}) => fireEvent.keyDown(document.body, { key: k, code: codeFor(k), ...extra })

describe('useMailShortcuts (MAIL-30)', () => {
  it('binds movement, actions, reply, compose, and the sheet', () => {
    const h = handlers()
    render(<Host h={h} />)
    key('j'); expect(h.moveFocus).toHaveBeenLastCalledWith(1)
    key('k'); expect(h.moveFocus).toHaveBeenLastCalledWith(-1)
    key('Enter'); expect(h.openFocused).toHaveBeenCalled()
    key('x'); expect(h.toggleSelectFocused).toHaveBeenCalled()
    key('e'); expect(h.act).toHaveBeenLastCalledWith('archive')
    key('#', { shiftKey: true }); expect(h.act).toHaveBeenLastCalledWith('trash')
    key('!', { shiftKey: true }); expect(h.act).toHaveBeenLastCalledWith('spam')
    key('u'); expect(h.act).toHaveBeenLastCalledWith('mark_unread')
    key('s'); expect(h.act).toHaveBeenLastCalledWith('star')
    key('r'); expect(h.reply).toHaveBeenLastCalledWith('reply')
    key('a'); expect(h.reply).toHaveBeenLastCalledWith('reply_all')
    key('f'); expect(h.reply).toHaveBeenLastCalledWith('forward')
    key('c'); expect(h.compose).toHaveBeenCalled()
    key('z'); expect(h.snooze).toHaveBeenCalled()
    key('?', { shiftKey: true }); expect(h.toggleSheet).toHaveBeenCalled()
    key('Escape'); expect(h.escape).toHaveBeenCalled()
    key('0'); expect(h.goAccount).toHaveBeenLastCalledWith(0)
    key('2'); expect(h.goAccount).toHaveBeenLastCalledWith(2)
  })

  it('g then s goes to Starred instead of starring', () => {
    const h = handlers()
    render(<Host h={h} />)
    key('g'); key('s')
    expect(h.goFolder).toHaveBeenLastCalledWith('starred')
    expect(h.act).not.toHaveBeenCalled()
    key('g'); key('i'); expect(h.goFolder).toHaveBeenLastCalledWith('inbox')
    key('g'); key('t'); expect(h.goFolder).toHaveBeenLastCalledWith('sent')
    key('g'); key('z'); expect(h.goFolder).toHaveBeenLastCalledWith('snoozed')
    expect(h.snooze).not.toHaveBeenCalled()
  })

  it('stays silent inside form fields and when disabled', () => {
    const h = handlers()
    const { getByLabelText, unmount } = render(<Host h={h} />)
    fireEvent.keyDown(getByLabelText('field'), { key: 'e', code: 'KeyE' })
    expect(h.act).not.toHaveBeenCalled()
    unmount()
    const h2 = handlers()
    render(<Host h={h2} enabled={false} />)
    key('e')
    expect(h2.act).not.toHaveBeenCalled()
  })
})
