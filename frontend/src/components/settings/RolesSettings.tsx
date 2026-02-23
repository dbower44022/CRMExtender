import { useState } from 'react'
import { toast } from 'sonner'
import {
  useRoles,
  useCreateRole,
  useUpdateRole,
  useDeleteRole,
  type Role,
} from '../../api/settings.ts'
import { Plus, Pencil, Trash2, Check, X } from 'lucide-react'

export function RolesSettings() {
  const { data: roles, isLoading } = useRoles()
  const createRole = useCreateRole()
  const updateRole = useUpdateRole()
  const deleteRole = useDeleteRole()

  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newSortOrder, setNewSortOrder] = useState(0)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editSortOrder, setEditSortOrder] = useState(0)

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  const handleCreate = () => {
    const name = newName.trim()
    if (!name) return
    createRole.mutate(
      { name, sort_order: newSortOrder },
      {
        onSuccess: () => {
          toast.success('Role created')
          setNewName('')
          setNewSortOrder(0)
          setShowAdd(false)
        },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const startEdit = (role: Role) => {
    setEditingId(role.id)
    setEditName(role.name)
    setEditSortOrder(role.sort_order)
  }

  const cancelEdit = () => setEditingId(null)

  const handleUpdate = () => {
    if (!editingId) return
    const name = editName.trim()
    if (!name) return
    updateRole.mutate(
      { roleId: editingId, name, sort_order: editSortOrder },
      {
        onSuccess: () => {
          toast.success('Role updated')
          setEditingId(null)
        },
        onError: (err) => toast.error(err.message),
      },
    )
  }

  const handleDelete = (role: Role) => {
    if (!confirm(`Delete role "${role.name}"?`)) return
    deleteRole.mutate(role.id, {
      onSuccess: () => toast.success('Role deleted'),
      onError: (err) => toast.error(err.message),
    })
  }

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleUpdate()
    else if (e.key === 'Escape') cancelEdit()
  }

  const handleAddKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleCreate()
    else if (e.key === 'Escape') setShowAdd(false)
  }

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-surface-800">Roles</h1>
          <p className="mt-1 text-sm text-surface-500">
            Contact-company affiliation roles. System roles cannot be modified.
          </p>
        </div>
        {!showAdd && (
          <button
            onClick={() => setShowAdd(true)}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Plus size={14} />
            Add Role
          </button>
        )}
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="mb-4 rounded-lg border border-primary-200 bg-primary-50 p-4">
          <h2 className="mb-3 text-sm font-medium text-surface-700">
            New Role
          </h2>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-surface-600">
                Name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={handleAddKeyDown}
                placeholder="e.g. Consultant"
                autoFocus
                className="w-full rounded border border-surface-300 bg-surface-0 px-2.5 py-1.5 text-sm focus:border-primary-400 focus:outline-none"
              />
            </div>
            <div className="w-24">
              <label className="mb-1 block text-xs font-medium text-surface-600">
                Sort Order
              </label>
              <input
                type="number"
                value={newSortOrder}
                onChange={(e) => setNewSortOrder(Number(e.target.value))}
                onKeyDown={handleAddKeyDown}
                className="w-full rounded border border-surface-300 bg-surface-0 px-2.5 py-1.5 text-sm focus:border-primary-400 focus:outline-none"
              />
            </div>
            <button
              onClick={handleCreate}
              disabled={!newName.trim() || createRole.isPending}
              className="rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {createRole.isPending ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="rounded-md border border-surface-300 bg-surface-0 px-3 py-1.5 text-sm font-medium text-surface-600 hover:bg-surface-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Roles table */}
      {roles && roles.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-surface-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 bg-surface-50 text-left text-xs font-medium uppercase tracking-wider text-surface-500">
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2 w-24">Order</th>
                <th className="px-4 py-2 w-24">Type</th>
                <th className="px-4 py-2 w-28">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {roles.map((role) => (
                <tr key={role.id} className="hover:bg-surface-50">
                  {editingId === role.id ? (
                    <>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={handleEditKeyDown}
                          autoFocus
                          className="w-full rounded border border-surface-300 bg-surface-0 px-1.5 py-0.5 text-sm focus:border-primary-400 focus:outline-none"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          value={editSortOrder}
                          onChange={(e) =>
                            setEditSortOrder(Number(e.target.value))
                          }
                          onKeyDown={handleEditKeyDown}
                          className="w-16 rounded border border-surface-300 bg-surface-0 px-1.5 py-0.5 text-sm focus:border-primary-400 focus:outline-none"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <span className="inline-block rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-500">
                          Custom
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={handleUpdate}
                            disabled={
                              !editName.trim() || updateRole.isPending
                            }
                            className="rounded p-1 text-green-600 hover:bg-green-50 disabled:opacity-50"
                            title="Save"
                          >
                            <Check size={14} />
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="rounded p-1 text-surface-500 hover:bg-surface-100"
                            title="Cancel"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-2 font-medium text-surface-800">
                        {role.name}
                      </td>
                      <td className="px-4 py-2 text-surface-600">
                        {role.sort_order}
                      </td>
                      <td className="px-4 py-2">
                        {role.is_system ? (
                          <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                            System
                          </span>
                        ) : (
                          <span className="inline-block rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-500">
                            Custom
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        {!role.is_system && (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => startEdit(role)}
                              className="rounded p-1 text-surface-500 hover:bg-surface-100"
                              title="Edit"
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => handleDelete(role)}
                              disabled={deleteRole.isPending}
                              className="rounded p-1 text-red-600 hover:bg-red-50 disabled:opacity-50"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-surface-500">No roles defined.</p>
      )}
    </div>
  )
}
