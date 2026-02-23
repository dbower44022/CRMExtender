import { useReferenceData } from '../../api/settings.ts'

export function RolesSettings() {
  const { data: refData, isLoading } = useReferenceData()

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  const roles = refData?.roles ?? []

  return (
    <div className="mx-auto w-full max-w-xl">
      <h1 className="mb-2 text-lg font-semibold text-surface-800">Roles</h1>
      <p className="mb-6 text-sm text-surface-500">
        System-defined contact-company roles. These are used when associating
        contacts with companies.
      </p>

      <div className="overflow-hidden rounded-lg border border-surface-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-200 bg-surface-50">
              <th className="px-4 py-2 text-left font-medium text-surface-600">
                Role Name
              </th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <tr
                key={role.id}
                className="border-b border-surface-100 last:border-b-0"
              >
                <td className="px-4 py-2 text-surface-800">{role.name}</td>
              </tr>
            ))}
            {roles.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-center text-surface-500">
                  No roles defined.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
