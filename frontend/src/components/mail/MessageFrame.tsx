/** A mail body in a sandboxed frame (MAIL-25). See lib/mailRender.ts. */

import { useEffect, useId, useMemo, useState } from 'react'
import { ImageOff } from 'lucide-react'
import { FRAME_MESSAGE_TYPE, allowSender, allowedSenders, buildFrameDocument, sanitizeMailHtml } from '../../lib/mailRender.ts'

interface Props {
  html: string
  senderAddress: string | null
  /** Base URL for cid: images, e.g. `/api/v1/mail/attachments/cid/<messageId>/` (MAIL-26). */
  cidBase?: string
  className?: string
}

export function MessageFrame({ html, senderAddress, cidBase, className }: Props) {
  const frameId = useId()
  const sender = (senderAddress || '').toLowerCase()
  const [senderAllowed, setSenderAllowed] = useState(() => (sender ? allowedSenders().has(sender) : false))
  const [loadOnce, setLoadOnce] = useState(false)
  const allowRemote = senderAllowed || loadOnce
  const [height, setHeight] = useState(80)

  const rendered = useMemo(() => sanitizeMailHtml(html, allowRemote), [html, allowRemote])
  const srcDoc = useMemo(() => buildFrameDocument(rendered.html, frameId, { cidBase }), [rendered.html, frameId, cidBase])

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      const d = e.data
      if (!d || d.type !== FRAME_MESSAGE_TYPE || d.id !== frameId) return
      if (d.kind === 'height' && typeof d.height === 'number') {
        setHeight(Math.min(Math.max(24, d.height + 4), 20000))
      } else if (d.kind === 'link' && typeof d.href === 'string') {
        const href: string = d.href
        if (/^(https?:|mailto:|tel:)/i.test(href)) {
          window.open(href, '_blank', 'noopener,noreferrer')
        }
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [frameId])

  return (
    <div className={className}>
      {rendered.blockedImages > 0 && (
        <div className="mb-2 flex flex-wrap items-center gap-2 rounded border border-surface-200 bg-surface-50 px-2 py-1 text-xs text-surface-600">
          <ImageOff size={12} />
          <span>
            {rendered.blockedImages} remote image{rendered.blockedImages === 1 ? '' : 's'} blocked
          </span>
          <button type="button" onClick={() => setLoadOnce(true)} className="text-primary-700 hover:underline">
            Load images
          </button>
          {sender && (
            <button
              type="button"
              onClick={() => { allowSender(sender); setSenderAllowed(true) }}
              className="text-primary-700 hover:underline"
              title={`Always load images from ${sender} in this browser`}
            >
              Always from this sender
            </button>
          )}
        </div>
      )}
      <iframe
        title="Message"
        sandbox="allow-scripts"
        referrerPolicy="no-referrer"
        srcDoc={srcDoc}
        style={{ width: '100%', height, border: 0, display: 'block', colorScheme: 'light' }}
      />
    </div>
  )
}
