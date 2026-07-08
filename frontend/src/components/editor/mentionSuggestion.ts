/** @-mention autocomplete for the note editor (UI Migration Phase 3).
 *
 * Plain-DOM dropdown (no tippy dependency) driven by Tiptap's suggestion
 * plugin, backed by GET /api/v1/notes/mentions. Selected nodes carry a
 * mentionType attr so the backend records them in note_mentions.
 */

import Mention from '@tiptap/extension-mention'
import type { SuggestionOptions, SuggestionProps } from '@tiptap/suggestion'
import { notesApi, type MentionHit } from '../../api/notes.ts'

class MentionDropdown {
  private el: HTMLDivElement
  private items: MentionHit[] = []
  private selected = 0
  private command: SuggestionProps<MentionHit>['command'] | null = null

  constructor() {
    this.el = document.createElement('div')
    this.el.className =
      'fixed z-[200] max-h-48 w-64 overflow-y-auto rounded-md border ' +
      'border-surface-200 bg-white shadow-lg text-sm'
    this.el.style.display = 'none'
    document.body.appendChild(this.el)
  }

  update(props: SuggestionProps<MentionHit>) {
    this.items = props.items
    this.command = props.command
    this.selected = 0
    if (!props.items.length || !props.clientRect) {
      this.hide()
      return
    }
    const rect = props.clientRect()
    if (!rect) {
      this.hide()
      return
    }
    this.el.style.left = `${rect.left}px`
    this.el.style.top = `${rect.bottom + 4}px`
    this.el.style.display = 'block'
    this.render()
  }

  render() {
    this.el.innerHTML = ''
    this.items.forEach((item, i) => {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className =
        'block w-full px-3 py-1.5 text-left hover:bg-surface-50 ' +
        (i === this.selected ? 'bg-surface-100' : '')
      const name = document.createElement('span')
      name.textContent = item.name
      btn.appendChild(name)
      if (item.detail) {
        const detail = document.createElement('span')
        detail.className = 'ml-2 text-xs text-surface-400'
        detail.textContent = item.detail
        btn.appendChild(detail)
      }
      btn.addEventListener('mousedown', (e) => {
        e.preventDefault()
        this.select(i)
      })
      this.el.appendChild(btn)
    })
  }

  select(index: number) {
    const item = this.items[index]
    if (item && this.command) {
      this.command({ id: item.id, label: item.name } as unknown as MentionHit)
    }
    this.hide()
  }

  onKeyDown(event: KeyboardEvent): boolean {
    if (this.el.style.display === 'none') return false
    if (event.key === 'ArrowDown') {
      this.selected = (this.selected + 1) % this.items.length
      this.render()
      return true
    }
    if (event.key === 'ArrowUp') {
      this.selected = (this.selected - 1 + this.items.length) % this.items.length
      this.render()
      return true
    }
    if (event.key === 'Enter') {
      this.select(this.selected)
      return true
    }
    if (event.key === 'Escape') {
      this.hide()
      return true
    }
    return false
  }

  hide() {
    this.el.style.display = 'none'
  }

  destroy() {
    this.el.remove()
  }
}

const suggestion: Omit<SuggestionOptions<MentionHit>, 'editor'> = {
  items: async ({ query }) => {
    if (query.length < 1) return []
    try {
      return await notesApi.mentions(query, 'user')
    } catch {
      return []
    }
  },
  render: () => {
    let dropdown: MentionDropdown
    return {
      onStart: (props) => {
        dropdown = new MentionDropdown()
        dropdown.update(props)
      },
      onUpdate: (props) => dropdown.update(props),
      onKeyDown: (props) => dropdown.onKeyDown(props.event),
      onExit: () => dropdown.destroy(),
    }
  },
}

export const NoteMention = Mention.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      // Recorded server-side into note_mentions — without it the legacy
      // editor's mentions were silently dropped
      mentionType: {
        default: 'user',
        parseHTML: (el) => el.getAttribute('data-mention-type') || 'user',
        renderHTML: (attrs) => ({ 'data-mention-type': attrs.mentionType }),
      },
    }
  },
}).configure({
  HTMLAttributes: { class: 'mention' },
  suggestion,
})
