import { ChevronDown } from 'lucide-react'
import { useAccounts } from '../../api/settings.ts'

interface SendingAccountSelectorProps {
  value: string
  onChange: (accountId: string) => void
}

export function SendingAccountSelector({ value, onChange }: SendingAccountSelectorProps) {
  const { data: accounts } = useAccounts()
  const activeAccounts = accounts?.filter((a) => a.is_active) ?? []

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none rounded border border-surface-200 bg-white py-1.5 pl-3 pr-8 text-sm text-surface-800 focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
      >
        <option value="">Select sending account...</option>
        {activeAccounts.map((acc) => (
          <option key={acc.id} value={acc.id}>
            {acc.display_name ? `${acc.display_name} <${acc.email_address}>` : acc.email_address}
          </option>
        ))}
      </select>
      <ChevronDown
        size={14}
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-400"
      />
    </div>
  )
}
