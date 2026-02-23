import { useState } from 'react'
import { toast } from 'sonner'
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useToggleUserActive,
  useSetUserPassword,
} from '../../api/settings.ts'
import { Plus, X } from 'lucide-react'

export function UsersSettings() {
  const { data: users, isLoading } = useUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const toggleActive = useToggleUserActive()
  const setPassword = useSetUserPassword()

  const [showCreate, setShowCreate] = useState(false)
  const [createEmail, setCreateEmail] = useState('')
  const [createName, setCreateName] = useState('')
  const [createRole, setCreateRole] = useState('user')
  const [createPw, setCreatePw] = useState('')

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editRole, setEditRole] = useState('user')

  const [pwUserId, setPwUserId] = useState<string | null>(null)
  const [newPw, setNewPw] = useState('')

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  const handleCreate = () => {
    if (!createEmail.trim()) {
      toast.error('Email is required')
      return
    }
    createUser.mutate(
      {
        email: createEmail.trim(),
        name: createName.trim(),
        role: createRole,
        password: createPw || undefined,
      },
      {
        onSuccess: () => {
          toast.success('User created')
          setShowCreate(false)
          setCreateEmail('')
          setCreateName('')
          setCreateRole('user')
          setCreatePw('')
        },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const startEdit = (user: { id: string; name: string; role: string }) => {
    setEditingId(user.id)
    setEditName(user.name)
    setEditRole(user.role)
  }

  const saveEdit = () => {
    if (!editingId) return
    updateUser.mutate(
      { userId: editingId, name: editName, role: editRole },
      {
        onSuccess: () => {
          toast.success('User updated')
          setEditingId(null)
        },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const handleSetPassword = () => {
    if (!pwUserId) return
    setPassword.mutate(
      { userId: pwUserId, new_password: newPw },
      {
        onSuccess: () => {
          toast.success('Password set')
          setPwUserId(null)
          setNewPw('')
        },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  return (
    <div className="w-full">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-surface-800">Users</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1 rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          <Plus size={14} />
          Create User
        </button>
      </div>

      {showCreate && (
        <div className="mb-4 rounded-lg border border-surface-200 bg-surface-50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-surface-700">New User</h3>
            <button
              onClick={() => setShowCreate(false)}
              className="text-surface-400 hover:text-surface-600"
            >
              <X size={16} />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="email"
              placeholder="Email"
              value={createEmail}
              onChange={(e) => setCreateEmail(e.target.value)}
              className="rounded-md border border-surface-300 bg-surface-0 px-3 py-1.5 text-sm focus:border-primary-400 focus:outline-none"
            />
            <input
              type="text"
              placeholder="Name"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              className="rounded-md border border-surface-300 bg-surface-0 px-3 py-1.5 text-sm focus:border-primary-400 focus:outline-none"
            />
            <select
              value={createRole}
              onChange={(e) => setCreateRole(e.target.value)}
              className="rounded-md border border-surface-300 bg-surface-0 px-3 py-1.5 text-sm focus:border-primary-400 focus:outline-none"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <input
              type="password"
              placeholder="Password (optional)"
              value={createPw}
              onChange={(e) => setCreatePw(e.target.value)}
              className="rounded-md border border-surface-300 bg-surface-0 px-3 py-1.5 text-sm focus:border-primary-400 focus:outline-none"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={createUser.isPending}
            className="mt-3 rounded-md bg-primary-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          >
            {createUser.isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-surface-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-200 bg-surface-50">
              <th className="px-4 py-2 text-left font-medium text-surface-600">
                Name
              </th>
              <th className="px-4 py-2 text-left font-medium text-surface-600">
                Email
              </th>
              <th className="px-4 py-2 text-left font-medium text-surface-600">
                Role
              </th>
              <th className="px-4 py-2 text-left font-medium text-surface-600">
                Status
              </th>
              <th className="px-4 py-2 text-right font-medium text-surface-600">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {users?.map((user) => (
              <tr
                key={user.id}
                className="border-b border-surface-100 last:border-b-0"
              >
                <td className="px-4 py-2 text-surface-800">
                  {editingId === user.id ? (
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full rounded border border-surface-300 px-2 py-0.5 text-sm"
                    />
                  ) : (
                    user.name || '-'
                  )}
                </td>
                <td className="px-4 py-2 text-surface-600">{user.email}</td>
                <td className="px-4 py-2">
                  {editingId === user.id ? (
                    <select
                      value={editRole}
                      onChange={(e) => setEditRole(e.target.value)}
                      className="rounded border border-surface-300 px-2 py-0.5 text-sm"
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  ) : (
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        user.role === 'admin'
                          ? 'bg-primary-100 text-primary-700'
                          : 'bg-surface-100 text-surface-600'
                      }`}
                    >
                      {user.role}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      user.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {editingId === user.id ? (
                      <>
                        <button
                          onClick={saveEdit}
                          className="rounded px-2 py-0.5 text-xs text-primary-600 hover:bg-primary-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="rounded px-2 py-0.5 text-xs text-surface-500 hover:bg-surface-100"
                        >
                          Cancel
                        </button>
                      </>
                    ) : pwUserId === user.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="password"
                          value={newPw}
                          onChange={(e) => setNewPw(e.target.value)}
                          placeholder="New password"
                          className="w-32 rounded border border-surface-300 px-2 py-0.5 text-xs"
                        />
                        <button
                          onClick={handleSetPassword}
                          className="rounded px-2 py-0.5 text-xs text-primary-600 hover:bg-primary-50"
                        >
                          Set
                        </button>
                        <button
                          onClick={() => {
                            setPwUserId(null)
                            setNewPw('')
                          }}
                          className="rounded px-2 py-0.5 text-xs text-surface-500 hover:bg-surface-100"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          onClick={() => startEdit(user)}
                          className="rounded px-2 py-0.5 text-xs text-surface-600 hover:bg-surface-100"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => setPwUserId(user.id)}
                          className="rounded px-2 py-0.5 text-xs text-surface-600 hover:bg-surface-100"
                        >
                          Password
                        </button>
                        <button
                          onClick={() =>
                            toggleActive.mutate(user.id, {
                              onError: (err) => toast.error(err.message),
                            })
                          }
                          className={`rounded px-2 py-0.5 text-xs ${
                            user.is_active
                              ? 'text-red-600 hover:bg-red-50'
                              : 'text-green-600 hover:bg-green-50'
                          }`}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
