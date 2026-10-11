/** The mail keyboard model (Mail Client PRD §5.1 "Keyboard navigation"; MAIL-30).
 *
 * Active only in mail mode and never while typing in a field. Bindings
 * not yet backed by a feature (label, move) are inert until their task
 * lands; the shortcut sheet marks them.
 */

import { useEffect, useRef, useState } from 'react'
import { useHotkeys } from 'react-hotkeys-hook'
import { toast } from 'sonner'

export interface ShortcutHandlers {
  moveFocus: (delta: number) => void
  openFocused: () => void
  toggleSelectFocused: () => void
  escape: () => void
  act: (action: 'archive' | 'trash' | 'spam' | 'star' | 'mark_unread') => void
  reply: (mode: 'reply' | 'reply_all' | 'forward') => void
  compose: () => void
  /** Open the snooze picker for the selection or the focused thread (MAIL-28). */
  snooze: () => void
  goFolder: (folder: 'inbox' | 'starred' | 'snoozed' | 'awaiting' | 'sent' | 'drafts' | 'all') => void
  goAccount: (index: number) => void   // 0 = unified, 1..9 = nth account
  focusSearch: () => void
  toggleSheet: () => void
}

const OPTS = { enableOnFormTags: false, preventDefault: true } as const

export function useMailShortcuts(enabled: boolean, h: ShortcutHandlers) {
  // "g" then a letter, within one second
  const pendingG = useRef<number | null>(null)
  const [, force] = useState(0)
  const armG = () => {
    pendingG.current = window.setTimeout(() => { pendingG.current = null; force((n) => n + 1) }, 1000)
  }
  const takeG = (): boolean => {
    if (pendingG.current === null) return false
    window.clearTimeout(pendingG.current)
    pendingG.current = null
    return true
  }
  useEffect(() => () => { if (pendingG.current !== null) window.clearTimeout(pendingG.current) }, [])

  useHotkeys('j, down', () => h.moveFocus(1), { ...OPTS, enabled }, [h])
  useHotkeys('k, up', () => h.moveFocus(-1), { ...OPTS, enabled }, [h])
  useHotkeys('enter, o', () => h.openFocused(), { ...OPTS, enabled }, [h])
  useHotkeys('x', () => h.toggleSelectFocused(), { ...OPTS, enabled }, [h])
  useHotkeys('escape', () => h.escape(), { ...OPTS, enabled }, [h])
  useHotkeys('e', () => h.act('archive'), { ...OPTS, enabled }, [h])
  useHotkeys('shift+3', () => h.act('trash'), { ...OPTS, enabled }, [h])          // #
  useHotkeys('shift+1', () => h.act('spam'), { ...OPTS, enabled }, [h])           // !
  useHotkeys('u', () => h.act('mark_unread'), { ...OPTS, enabled }, [h])
  useHotkeys('r', () => h.reply('reply'), { ...OPTS, enabled }, [h])
  useHotkeys('a', () => h.reply('reply_all'), { ...OPTS, enabled }, [h])
  useHotkeys('f', () => h.reply('forward'), { ...OPTS, enabled }, [h])
  useHotkeys('c', () => h.compose(), { ...OPTS, enabled }, [h])
  useHotkeys('slash', () => h.focusSearch(), { ...OPTS, enabled }, [h])
  useHotkeys('shift+slash', () => h.toggleSheet(), { ...OPTS, enabled }, [h])   // ?
  useHotkeys('z', () => { if (takeG()) h.goFolder('snoozed'); else h.snooze() }, { ...OPTS, enabled }, [h])
  useHotkeys('l, v', () => toast.info('Label and move pickers arrive with MAIL-29'), { ...OPTS, enabled }, [h])

  // "s" is star unless it follows "g"
  useHotkeys('s', () => { if (takeG()) h.goFolder('starred'); else h.act('star') }, { ...OPTS, enabled }, [h])
  useHotkeys('g', () => { takeG(); armG() }, { ...OPTS, enabled }, [h])
  useHotkeys('i', () => { if (takeG()) h.goFolder('inbox') }, { ...OPTS, enabled }, [h])
  useHotkeys('t', () => { if (takeG()) h.goFolder('sent') }, { ...OPTS, enabled }, [h])
  useHotkeys('w', () => { if (takeG()) h.goFolder('awaiting') }, { ...OPTS, enabled }, [h])
  useHotkeys('d', () => { if (takeG()) h.goFolder('drafts') }, { ...OPTS, enabled }, [h])
  useHotkeys('shift+o', () => { /* handled by the reading pane (expand all) */ }, { enabled: false }, [])

  // Account switch: 0 unified, 1-9 nth account
  useHotkeys('0', () => h.goAccount(0), { ...OPTS, enabled }, [h])
  for (let n = 1; n <= 9; n++) {
    // eslint-disable-next-line react-hooks/rules-of-hooks -- fixed-length loop, same order every render
    useHotkeys(String(n), () => h.goAccount(n), { ...OPTS, enabled }, [h])
  }
  // "g a" = all mail
  useHotkeys('shift+a', () => { if (takeG()) h.goFolder('all') }, { ...OPTS, enabled }, [h])
}

export const SHORTCUT_ROWS: { keys: string; action: string; note?: string }[] = [
  { keys: 'j / k', action: 'Next / previous thread' },
  { keys: 'Enter or o', action: 'Open the focused thread' },
  { keys: 'x', action: 'Select / deselect the focused thread' },
  { keys: 'Shift+click', action: 'Select a range' },
  { keys: 'Ctrl+A', action: 'Select all loaded threads (list focused)' },
  { keys: 'Esc', action: 'Close the thread, then clear the selection' },
  { keys: 'e', action: 'Archive' },
  { keys: '#', action: 'Trash' },
  { keys: '!', action: 'Report spam' },
  { keys: 's', action: 'Star / unstar' },
  { keys: 'u', action: 'Mark unread' },
  { keys: 'r / a / f', action: 'Reply / reply all / forward the open thread' },
  { keys: 'c', action: 'Compose' },
  { keys: 'Shift+O', action: 'Expand every message in the open thread' },
  { keys: 'g then i / s / z / w / t / d / Shift+A', action: 'Go to Inbox / Starred / Snoozed / Awaiting reply / Sent / Drafts / All mail' },
  { keys: '0, 1 … 9', action: 'Unified inbox, or the nth account' },
  { keys: '/', action: 'Search mail (Enter to run, Esc to clear)' },
  { keys: 'z', action: 'Snooze (picker: later today, tomorrow, weekend, next week, custom)' },
  { keys: 'l / v', action: 'Label / move', note: 'MAIL-29' },
  { keys: 'Ctrl+Enter', action: 'Send (in the composer)' },
  { keys: '?', action: 'This sheet' },
]
