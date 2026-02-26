import type { Editor } from '@tiptap/react'
import {
  Bold,
  Italic,
  Underline,
  Strikethrough,
  List,
  ListOrdered,
  Link,
  Quote,
  Code,
  Minus,
  Heading1,
  Heading2,
} from 'lucide-react'

interface EditorToolbarProps {
  editor: Editor | null
}

export function EditorToolbar({ editor }: EditorToolbarProps) {
  if (!editor) return null

  const btn = (
    active: boolean,
    onClick: () => void,
    icon: React.ReactNode,
    title: string,
  ) => (
    <button
      type="button"
      onClick={onClick}
      className={active ? 'is-active' : ''}
      title={title}
    >
      {icon}
    </button>
  )

  const setLink = () => {
    const prev = editor.getAttributes('link').href
    const url = window.prompt('URL', prev)
    if (url === null) return
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
    } else {
      editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
    }
  }

  return (
    <div className="editor-toolbar">
      {btn(
        editor.isActive('bold'),
        () => editor.chain().focus().toggleBold().run(),
        <Bold size={15} />,
        'Bold',
      )}
      {btn(
        editor.isActive('italic'),
        () => editor.chain().focus().toggleItalic().run(),
        <Italic size={15} />,
        'Italic',
      )}
      {btn(
        editor.isActive('underline'),
        () => editor.chain().focus().toggleUnderline().run(),
        <Underline size={15} />,
        'Underline',
      )}
      {btn(
        editor.isActive('strike'),
        () => editor.chain().focus().toggleStrike().run(),
        <Strikethrough size={15} />,
        'Strikethrough',
      )}

      <div className="separator" />

      {btn(
        editor.isActive('heading', { level: 1 }),
        () => editor.chain().focus().toggleHeading({ level: 1 }).run(),
        <Heading1 size={15} />,
        'Heading 1',
      )}
      {btn(
        editor.isActive('heading', { level: 2 }),
        () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
        <Heading2 size={15} />,
        'Heading 2',
      )}

      <div className="separator" />

      {btn(
        editor.isActive('bulletList'),
        () => editor.chain().focus().toggleBulletList().run(),
        <List size={15} />,
        'Bullet List',
      )}
      {btn(
        editor.isActive('orderedList'),
        () => editor.chain().focus().toggleOrderedList().run(),
        <ListOrdered size={15} />,
        'Ordered List',
      )}

      <div className="separator" />

      {btn(
        editor.isActive('blockquote'),
        () => editor.chain().focus().toggleBlockquote().run(),
        <Quote size={15} />,
        'Blockquote',
      )}
      {btn(
        editor.isActive('codeBlock'),
        () => editor.chain().focus().toggleCodeBlock().run(),
        <Code size={15} />,
        'Code Block',
      )}
      {btn(
        editor.isActive('link'),
        setLink,
        <Link size={15} />,
        'Link',
      )}
      {btn(
        false,
        () => editor.chain().focus().setHorizontalRule().run(),
        <Minus size={15} />,
        'Horizontal Rule',
      )}
    </div>
  )
}
