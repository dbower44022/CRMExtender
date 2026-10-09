import { useState } from 'react'
import { toast } from 'sonner'
import {
  useSystemSettings,
  useUpdateSystemSettings,
  useReferenceData,
  type SystemSettings as SystemSettingsData,
} from '../../api/settings.ts'
import { DuplicateThresholds } from './DuplicateThresholds.tsx'
import { VersionInfo } from './VersionInfo.tsx'

export function SystemSettings() {
  const { data: settings, isLoading } = useSystemSettings()

  if (isLoading || !settings) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  return <SystemSettingsForm settings={settings} />
}

function SystemSettingsForm({ settings }: { settings: SystemSettingsData }) {
  const { data: refData } = useReferenceData()
  const updateSettings = useUpdateSystemSettings()

  const [companyName, setCompanyName] = useState(settings.company_name)
  const [defaultTz, setDefaultTz] = useState(settings.default_timezone)
  const [defaultPhoneCountry, setDefaultPhoneCountry] = useState(settings.default_phone_country)
  const [emailHistoryWindow, setEmailHistoryWindow] = useState(settings.email_history_window)
  const [settleMinutes, setSettleMinutes] = useState(settings.summarize_settle_minutes ?? '15')
  const [maxPerSync, setMaxPerSync] = useState(settings.summarize_max_per_sync ?? '500')
  const [syncInterval, setSyncInterval] = useState(settings.mail_sync_interval_seconds ?? '120')
  const [syncEnabled, setSyncEnabled] = useState(settings.sync_enabled === 'true')
  const [allowSelfReg, setAllowSelfReg] = useState(settings.allow_self_registration === 'true')

  const handleSave = () => {
    updateSettings.mutate(
      {
        company_name: companyName,
        default_timezone: defaultTz,
        default_phone_country: defaultPhoneCountry,
        email_history_window: emailHistoryWindow,
        summarize_settle_minutes: settleMinutes,
        summarize_max_per_sync: maxPerSync,
        mail_sync_interval_seconds: syncInterval,
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

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">
              Summarize after quiet (minutes)
            </label>
            <input
              type="number"
              min={0}
              step={1}
              value={settleMinutes}
              onChange={(e) => setSettleMinutes(e.target.value)}
              className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
            />
            <p className="mt-1 text-xs text-surface-500">
              A thread is summarized once it has had no new mail for this long, not on every message.
            </p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">
              Max summaries per sync
            </label>
            <input
              type="number"
              min={0}
              step={1}
              value={maxPerSync}
              onChange={(e) => setMaxPerSync(e.target.value)}
              className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
            />
            <p className="mt-1 text-xs text-surface-500">
              Newest threads first; the rest wait for the next sync. 0 means no limit.
            </p>
          </div>
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

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Sync every (seconds)
          </label>
          <input
            type="number"
            min={60}
            step={30}
            value={syncInterval}
            onChange={(e) => setSyncInterval(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          />
          <p className="mt-1 text-xs text-surface-500">
            Each account syncs on its own timer in the background; minimum 60 seconds. Turning Sync enabled off stops the timers but Sync Now still works.
          </p>
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

        <DuplicateThresholds />
        <VersionInfo />
      </div>
    </div>
  )
}
