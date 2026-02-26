import { useNavigationStore } from '../../stores/navigation.ts'
import { DataGrid } from '../grid/DataGrid.tsx'
import { GridToolbar } from '../grid/GridToolbar.tsx'
import { ProfileSettings } from '../settings/ProfileSettings.tsx'
import { SystemSettings } from '../settings/SystemSettings.tsx'
import { UsersSettings } from '../settings/UsersSettings.tsx'
import { AccountsSettings } from '../settings/AccountsSettings.tsx'
import { CalendarsSettings } from '../settings/CalendarsSettings.tsx'
import { RolesSettings } from '../settings/RolesSettings.tsx'
import { SignatureSettings } from '../settings/SignatureSettings.tsx'

const SETTINGS_COMPONENTS: Record<string, React.FC> = {
  profile: ProfileSettings,
  system: SystemSettings,
  users: UsersSettings,
  accounts: AccountsSettings,
  calendars: CalendarsSettings,
  roles: RolesSettings,
  signatures: SignatureSettings,
}

export function ContentArea() {
  const settingsMode = useNavigationStore((s) => s.settingsMode)
  const settingsTab = useNavigationStore((s) => s.settingsTab)

  if (settingsMode) {
    const Component = SETTINGS_COMPONENTS[settingsTab] ?? ProfileSettings
    return (
      <div className="flex h-full flex-col overflow-auto bg-surface-0 p-6">
        <Component />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-surface-0">
      <GridToolbar />
      <DataGrid />
    </div>
  )
}
