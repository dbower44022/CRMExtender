import { useEffect, useState } from 'react'
import { Copy } from 'lucide-react'
import { toast } from 'sonner'
import { get } from '../../api/client.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'

interface Version {
  version: string
  sha: string | null
  short_sha: string | null
  committed_at: string | null
  message: string | null
  sha_source: string
}

/** Running application version. The version number (from VERSION) is the
 * headline — higher is newer; the commit hash is exact-match detail. */
export function VersionInfo() {
  const [version, setVersion] = useState<Version | null>(null)

  useEffect(() => {
    get<Version>('/version').then(setVersion).catch(() => setVersion(null))
  }, [])

  if (!version) return null

  return (
    <div className="mt-8 border-t border-surface-200 pt-6">
      <h2 className="mb-1 text-base font-semibold text-surface-800">Version</h2>
      <div className="flex items-baseline gap-3">
        <span className="text-2xl font-semibold tabular-nums text-surface-900">
          v{version.version}
        </span>
        {version.committed_at && (
          <span className="text-sm text-surface-500">
            released {formatTimestamp(version.committed_at)}
          </span>
        )}
      </div>
      {version.short_sha && (
        <div className="mt-1 flex items-center gap-2">
          <code className="rounded bg-surface-100 px-1.5 py-0.5 font-mono text-xs text-surface-500">
            {version.short_sha}
          </code>
          <button
            onClick={() => {
              navigator.clipboard?.writeText(version.sha ?? '')
              toast.success('Full commit hash copied')
            }}
            title="Copy full commit hash"
            className="rounded p-0.5 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <Copy size={12} />
          </button>
          {version.message && (
            <span className="truncate text-xs text-surface-400">
              {version.message}
            </span>
          )}
        </div>
      )}
      {version.sha_source !== 'git' && !version.short_sha && (
        <p className="mt-1 text-xs text-surface-400">
          Commit hash unavailable at runtime.
        </p>
      )}
    </div>
  )
}
