import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigationStore } from '../../stores/navigation.ts'
import {
  useViews,
  useCreateView,
  useUpdateView,
  useDeleteView,
  useDuplicateView,
} from '../../api/views.ts'
import { ViewContextMenu } from './ViewContextMenu.tsx'
import { List, ChevronRight, Plus, MoreHorizontal } from 'lucide-react'

export function ActionPanel() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const setActiveViewId = useNavigationStore((s) => s.setActiveViewId)
  const { data: views, isLoading } = useViews(activeEntityType)

  const [isCreating, setIsCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const createView = useCreateView()

  const handleCreate = () => {
    const name = newName.trim()
    if (!name) {
      setIsCreating(false)
      return
    }
    createView.mutate(
      { entity_type: activeEntityType, name },
      {
        onSuccess: (view) => {
          setActiveViewId(view.id)
          setIsCreating(false)
          setNewName('')
        },
      },
    )
  }

  const personalViews = views?.filter((v) => v.visibility === 'personal') ?? []
  const sharedViews = views?.filter((v) => v.visibility === 'shared') ?? []

  return (
    <div className="flex h-full flex-col overflow-hidden border-r border-surface-200 bg-surface-50">
      <div className="flex items-center justify-between border-b border-surface-200 px-3 py-2.5">
        <h2 className="text-xs font-semibold tracking-wide text-surface-500 uppercase">
          Views
        </h2>
        <button
          onClick={() => {
            setIsCreating(true)
            setNewName('')
          }}
          className="flex h-5 w-5 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-200 hover:text-surface-600"
          title="Create new view"
        >
          <Plus size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-1">
        {isLoading && (
          <div className="space-y-2 p-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-7 animate-pulse rounded bg-surface-200"
              />
            ))}
          </div>
        )}

        {isCreating && (
          <div className="px-2 py-1.5">
            <input
              autoFocus
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate()
                if (e.key === 'Escape') {
                  setIsCreating(false)
                  setNewName('')
                }
              }}
              onBlur={handleCreate}
              placeholder="View name..."
              className="w-full rounded border border-primary-300 bg-surface-0 px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-primary-200"
            />
          </div>
        )}

        {personalViews.length > 0 && (
          <ViewGroup
            label="My Views"
            views={personalViews}
            activeViewId={activeViewId}
            onSelect={setActiveViewId}
            entityType={activeEntityType}
          />
        )}

        {sharedViews.length > 0 && (
          <ViewGroup
            label="Shared"
            views={sharedViews}
            activeViewId={activeViewId}
            onSelect={setActiveViewId}
            entityType={activeEntityType}
          />
        )}
      </div>
    </div>
  )
}

interface ViewGroupProps {
  label: string
  views: Array<{
    id: string
    name: string
    is_default: number
  }>
  activeViewId: string | null
  onSelect: (id: string) => void
  entityType: string
}

function ViewGroup({ label, views, activeViewId, onSelect }: ViewGroupProps) {
  const [menuViewId, setMenuViewId] = useState<string | null>(null)
  const [menuPos, setMenuPos] = useState({ x: 0, y: 0 })
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const setActiveViewId = useNavigationStore((s) => s.setActiveViewId)
  const deleteView = useDeleteView()
  const duplicateView = useDuplicateView()

  const handleContextMenu = (viewId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setMenuViewId(viewId)
    setMenuPos({ x: e.clientX, y: e.clientY })
  }

  const closeMenu = useCallback(() => setMenuViewId(null), [])

  const startRename = (view: { id: string; name: string }) => {
    setMenuViewId(null)
    setRenamingId(view.id)
    setRenameValue(view.name)
  }

  const handleDuplicate = (viewId: string) => {
    setMenuViewId(null)
    duplicateView.mutate(
      { viewId },
      {
        onSuccess: (newView) => setActiveViewId(newView.id),
      },
    )
  }

  const handleDelete = (viewId: string) => {
    setMenuViewId(null)
    setConfirmDeleteId(viewId)
  }

  const confirmDelete = (viewId: string) => {
    deleteView.mutate(viewId, {
      onSuccess: () => {
        if (viewId === activeViewId) {
          // Switch to another view
          const other = views.find((v) => v.id !== viewId)
          if (other) setActiveViewId(other.id)
        }
      },
    })
    setConfirmDeleteId(null)
  }

  return (
    <div className="mb-2">
      <div className="px-2 py-1.5 text-[10px] font-semibold tracking-wider text-surface-400 uppercase">
        {label}
      </div>
      {views.map((v) => {
        const isActive = v.id === activeViewId

        if (renamingId === v.id) {
          return (
            <RenameInput
              key={v.id}
              viewId={v.id}
              initialValue={renameValue}
              onDone={() => setRenamingId(null)}
            />
          )
        }

        if (confirmDeleteId === v.id) {
          return (
            <div key={v.id} className="flex items-center gap-1 px-2 py-1.5 text-xs">
              <span className="text-surface-500">Delete?</span>
              <button
                onClick={() => confirmDelete(v.id)}
                className="rounded bg-red-500 px-2 py-0.5 text-white hover:bg-red-600"
              >
                Yes
              </button>
              <button
                onClick={() => setConfirmDeleteId(null)}
                className="rounded bg-surface-200 px-2 py-0.5 text-surface-600 hover:bg-surface-300"
              >
                No
              </button>
            </div>
          )
        }

        return (
          <div key={v.id} className="group relative">
            <button
              onClick={() => onSelect(v.id)}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                isActive
                  ? 'bg-primary-50 font-medium text-primary-700'
                  : 'text-surface-600 hover:bg-surface-100'
              }`}
            >
              <List size={14} className="shrink-0" />
              <span className="truncate">{v.name}</span>
              {isActive && (
                <ChevronRight size={12} className="ml-auto shrink-0" />
              )}
            </button>
            <button
              onClick={(e) => handleContextMenu(v.id, e)}
              className="absolute right-1.5 top-1/2 hidden h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-surface-400 hover:bg-surface-200 hover:text-surface-600 group-hover:flex"
            >
              <MoreHorizontal size={13} />
            </button>
          </div>
        )
      })}

      {menuViewId && (
        <ViewContextMenu
          x={menuPos.x}
          y={menuPos.y}
          isDefault={!!views.find((v) => v.id === menuViewId)?.is_default}
          onRename={() => startRename(views.find((v) => v.id === menuViewId)!)}
          onDuplicate={() => handleDuplicate(menuViewId)}
          onDelete={() => handleDelete(menuViewId)}
          onClose={closeMenu}
        />
      )}
    </div>
  )
}

function RenameInput({
  viewId,
  initialValue,
  onDone,
}: {
  viewId: string
  initialValue: string
  onDone: () => void
}) {
  const [value, setValue] = useState(initialValue)
  const inputRef = useRef<HTMLInputElement>(null)
  const updateView = useUpdateView(viewId)

  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  const save = () => {
    const name = value.trim()
    if (name && name !== initialValue) {
      updateView.mutate({ name })
    }
    onDone()
  }

  return (
    <div className="px-2 py-1.5">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') save()
          if (e.key === 'Escape') onDone()
        }}
        onBlur={save}
        className="w-full rounded border border-primary-300 bg-surface-0 px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-primary-200"
      />
    </div>
  )
}
