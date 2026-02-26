import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { EditorToolbar } from './EditorToolbar.tsx'
import './editor.css'

interface RichTextEditorProps {
  content?: string | null
  onChange?: (json: string, html: string, text: string) => void
  placeholder?: string
  editable?: boolean
  className?: string
  autoFocus?: boolean
}

export function RichTextEditor({
  content,
  onChange,
  placeholder = 'Write your message...',
  editable = true,
  className = '',
  autoFocus = false,
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        link: {
          openOnClick: false,
          HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' },
        },
      }),
      Placeholder.configure({ placeholder }),
    ],
    content: content || '',
    editable,
    autofocus: autoFocus ? 'end' : false,
    onUpdate: ({ editor }) => {
      if (onChange) {
        onChange(
          JSON.stringify(editor.getJSON()),
          editor.getHTML(),
          editor.getText(),
        )
      }
    },
  })

  return (
    <div className={`rounded-lg border border-surface-200 bg-white ${className}`}>
      {editable && <EditorToolbar editor={editor} />}
      <div className="px-3 py-2">
        <EditorContent editor={editor} className="tiptap-editor" />
      </div>
    </div>
  )
}
