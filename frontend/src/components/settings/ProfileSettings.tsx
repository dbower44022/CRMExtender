import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import {
  useProfile,
  useUpdateProfile,
  useChangePassword,
  useReferenceData,
} from '../../api/settings.ts'
import { ChevronDown, ChevronRight } from 'lucide-react'

export function ProfileSettings() {
  const { data: profile, isLoading } = useProfile()
  const { data: refData } = useReferenceData()
  const updateProfile = useUpdateProfile()
  const changePassword = useChangePassword()

  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [startOfWeek, setStartOfWeek] = useState('monday')
  const [dateFormat, setDateFormat] = useState('ISO')

  const [showPwSection, setShowPwSection] = useState(false)
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')

  useEffect(() => {
    if (profile) {
      setName(profile.name)
      setTimezone(profile.timezone)
      setStartOfWeek(profile.start_of_week)
      setDateFormat(profile.date_format)
    }
  }, [profile])

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  const handleSave = () => {
    updateProfile.mutate(
      { name, timezone, start_of_week: startOfWeek, date_format: dateFormat },
      {
        onSuccess: () => toast.success('Profile updated'),
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const handlePasswordChange = () => {
    if (newPw !== confirmPw) {
      toast.error('Passwords do not match')
      return
    }
    changePassword.mutate(
      {
        current_password: currentPw,
        new_password: newPw,
        confirm_password: confirmPw,
      },
      {
        onSuccess: () => {
          toast.success('Password changed')
          setCurrentPw('')
          setNewPw('')
          setConfirmPw('')
          setShowPwSection(false)
        },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const timezones = refData?.timezones ?? []

  return (
    <div className="mx-auto w-full max-w-xl">
      <h1 className="mb-6 text-lg font-semibold text-surface-800">Profile</h1>

      <div className="space-y-4">
        <div className="text-sm text-surface-500">
          {profile?.email}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Timezone
          </label>
          <select
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
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
            Start of week
          </label>
          <select
            value={startOfWeek}
            onChange={(e) => setStartOfWeek(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          >
            <option value="monday">Monday</option>
            <option value="sunday">Sunday</option>
            <option value="saturday">Saturday</option>
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">
            Date format
          </label>
          <select
            value={dateFormat}
            onChange={(e) => setDateFormat(e.target.value)}
            className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
          >
            <option value="ISO">ISO (2026-02-23)</option>
            <option value="US">US (02/23/2026)</option>
            <option value="EU">EU (23/02/2026)</option>
          </select>
        </div>

        <button
          onClick={handleSave}
          disabled={updateProfile.isPending}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
        >
          {updateProfile.isPending ? 'Saving...' : 'Save'}
        </button>
      </div>

      <div className="mt-8 border-t border-surface-200 pt-6">
        <button
          onClick={() => setShowPwSection(!showPwSection)}
          className="flex items-center gap-1 text-sm font-medium text-surface-700"
        >
          {showPwSection ? (
            <ChevronDown size={16} />
          ) : (
            <ChevronRight size={16} />
          )}
          Change Password
        </button>

        {showPwSection && (
          <div className="mt-4 space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                Current password
              </label>
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                New password
              </label>
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                Confirm new password
              </label>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                className="w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200"
              />
            </div>
            <button
              onClick={handlePasswordChange}
              disabled={changePassword.isPending || !newPw}
              className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
            >
              {changePassword.isPending ? 'Changing...' : 'Change Password'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
