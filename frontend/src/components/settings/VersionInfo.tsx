import { useEffect, useState } from 'react'
import { Copy } from 'lucide-react'
import { toast } from 'sonner'
import { get } from '../../api/client.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'

interface Version {
  sha: string
  short_sha: string
  committed_at: string | null
  message: string | null
  source: string
}

/** Running application version — the git commit, for verifying you are on
 * the released build. */
export function VersionInfo() {
  const [version, setVersion] = useState<Version | null>(null)

  useEffect(() => {
    get<Version>('/version').then(setVersion).catch(() => setVersion(null))
  }, [])

  if (!version) return null

  return (
    <div className="mt-8 border-t border-surface-200 pt-6">
      <h2 className="mb-1 text-base font-semibold text-surface-800">Version</h2>
      <div className="flex items-center gap-2">
        <code className="rounded bg-surface-100 px-2 py-1 font-mono text-sm text-surface-800">
          {version.short_sha}
        </code>
        {version.committed_at && (
          <span className="text-sm text-surface-500">
            {formatTimestamp(version.committed_at)}
          </span>
        )}
        <button
          onClick={() => {
            navigator.clipboard?.writeText(version.sha)
            toast.success('Full commit hash copied')
          }}
          title="Copy full commit hash"
          className="rounded p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
        >
          <Copy size={13} />
        </button>
      </div>
      {version.message && (
        <p className="mt-1 truncate text-xs text-surface-400">
          {version.message}
        </p>
      )}
      {version.source !== 'git' && (
        <p className="mt-1 text-xs text-amber-600">
          Version read from {version.source} — git unavailable at runtime.
        </p>
      )}
    </div>
  )
}
