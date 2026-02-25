import { useNavigationStore } from '../../stores/navigation.ts'
import type { CommunicationFullParticipant, CommunicationProviderAccount } from '../../types/api.ts'

interface ParticipantsCardProps {
  participants: CommunicationFullParticipant[]
  providerAccount: CommunicationProviderAccount | null
  onClose: () => void
}

const ROLE_LABELS: Record<string, string> = {
  from: 'Sender',
  to: 'To',
  cc: 'CC',
  bcc: 'BCC',
  participant: 'Participant',
}

export function ParticipantsCard({ participants, providerAccount, onClose }: ParticipantsCardProps) {
  if (participants.length === 0) return null

  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="border-b border-surface-200 px-4 py-2.5 text-xs font-semibold uppercase text-surface-500">
        Participants
      </div>
      <div className="divide-y divide-surface-100">
        {participants.map((p, i) => (
          <div key={i} className="px-4 py-2.5">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                {p.contact_id ? (
                  <button
                    className="truncate text-sm font-medium text-primary-600 hover:underline"
                    onClick={() => {
                      setActiveEntityType('contact')
                      setSelectedRow(p.contact_id!, -1)
                      onClose()
                    }}
                  >
                    {p.contact_name || p.name || p.address}
                  </button>
                ) : (
                  <span className="truncate text-sm text-surface-700">
                    {p.name || p.address}
                  </span>
                )}
                {/* Address line — "via" for account owner, plain address for others */}
                {p.is_account_owner && providerAccount ? (
                  <div className="truncate text-xs text-surface-400">
                    via {providerAccount.email_address}
                  </div>
                ) : p.address ? (
                  <div className="truncate text-xs text-surface-400">
                    {p.address}
                  </div>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="rounded bg-surface-100 px-1.5 py-0.5 text-xs text-surface-500">
                  {ROLE_LABELS[p.role] ?? p.role}
                </span>
                {p.is_account_owner && (
                  <span className="rounded bg-primary-50 px-1.5 py-0.5 text-xs font-medium text-primary-600">
                    You
                  </span>
                )}
              </div>
            </div>
            {(p.title || p.company_name) && (
              <div className="mt-0.5 truncate text-xs text-surface-400">
                {[p.title, p.company_name].filter(Boolean).join(' · ')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
