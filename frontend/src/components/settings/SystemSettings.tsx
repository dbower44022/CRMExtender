import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import {
  useSystemSettings,
  useUpdateSystemSettings,
  useReferenceData,
} from '../../api/settings.ts'

export function SystemSettings() {
  const { data: settings, isLoading } = useSystemSettings()
  const { data: refData } = useReferenceData()
  const updateSettings = useUpdateSystemSettings()

  const [companyName, setCompanyName] = useState('')
  const [defaultTz, setDefaultTz] = useState('UTC')
  const [defaultPhoneCountry, setDefaultPhoneCountry] = useState('US')
  const [emailHistoryWindow, setEmailHistoryWindow] = useState('90d')
  const [syncEnabled, setSyncEnabled] = useState(true)
  const [allowSelfReg, setAllowSelfReg] = useState(false)

  useEffect(() => {
    if (settings) {
      setCompanyName(settings.company_name)
      setDefaultTz(settings.default_timezone)
      setDefaultPhoneCountry(settings.default_phone_country)
      setEmailHistoryWindow(settings.email_history_window)
      setSyncEnabled(settings.sync_enabled === 'true')
      setAllowSelfReg(settings.allow_self_registration === 'true')
    }
  }, [settings])

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  const handleSave = () => {
    updateSettings.mutate(
      {
        company_name: companyName,
        default_timezone: defaultTz,
        default_phone_country: defaultPhoneCountry,
        email_history_window: emailHistoryWindow,
        sync_enabled: syncEnabled ? 'true' : 'false',
        allow_self_registration: allowSelfReg ? 'true' : 'false',
      },
      {
        onSuccess: () => toast.success('System settings updated'),
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const timezones = refData?.timezones ?? []
  const countries = refData?.countries ?? []
  const historyOptions = refData?.email_history_options ?? []

  return (
    <div className="mx-auto w-full max-w-xl">
      <h1 className="mb-6 text-lg font-semibold text-surface-800">
        System Settings
      </h1>

      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Company name
          </label>
          <input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Default timezone
          </label>
          <select
            value={defaultTz}
            onChange={(e) => setDefaultTz(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          >
            {timezones.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Default phone country
          </label>
          <select
            value={defaultPhoneCountry}
            onChange={(e) => setDefaultPhoneCountry(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          >
            {countries.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Email history window
          </label>
          <select
            value={emailHistoryWindow}
            onChange={(e) => setEmailHistoryWindow(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          >
            {historyOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              checked={syncEnabled}
              onChange={(e) => setSyncEnabled(e.target.checked)}
              className="peer sr-only"
            />
            <div className="peer h-5 w-9 rounded-full bg-surface-300 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all after:content-[''] peer-checked:bg-primary-600 peer-checked:after:translate-x-full" />
          </label>
          <span className="text-sm text-surface-700">Sync enabled</span>
        </div>

        <div className="flex items-center gap-3">
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              checked={allowSelfReg}
              onChange={(e) => setAllowSelfReg(e.target.checked)}
              className="peer sr-only"
            />
            <div className="peer h-5 w-9 rounded-full bg-surface-300 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all after:content-[''] peer-checked:bg-primary-600 peer-checked:after:translate-x-full" />
          </label>
          <span className="text-sm text-surface-700">
            Allow self-registration
          </span>
        </div>

        <button
          onClick={handleSave}
          disabled={updateSettings.isPending}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
        >
          {updateSettings.isPending ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  )
}
