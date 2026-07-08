import { useEffect, useState } from 'react'
import { Plus, Trash2, Wand2 } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { workflows, type TopicRow } from '../../api/workflows.ts'

/** Topics management + auto-assign for a project (UI Migration Phase 4). */
export function ProjectTopicsCard({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const [topics, setTopics] = useState<TopicRow[] | null>(null)
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [confirming, setConfirming] = useState<string | null>(null)
  const [preview, setPreview] = useState<{
    matched: number
    total_candidates: number
    assignments: { conversation_title: string; topic_name: string; score: number }[]
  } | null>(null)

  const load = () =>
    workflows.topics(projectId)
      .then((res) => setTopics(res.topics))
      .catch(() => setTopics([]))

  useEffect(() => {
    load()
    setPreview(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const addTopic = async () => {
    if (!name.trim()) return
    try {
      await workflows.createTopic(projectId, name.trim())
      setName('')
      setAdding(false)
      load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed')
    }
  }

  const removeTopic = async (topicId: string) => {
    if (confirming !== topicId) {
      setConfirming(topicId)
      return
    }
    setConfirming(null)
    try {
      const res = await workflows.deleteTopic(projectId, topicId)
      toast.success(
        `Topic deleted${res.conversations_unassigned ? ` — ${res.conversations_unassigned} conversation(s) unassigned` : ''}`)
      load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  const runPreview = async () => {
    try {
      setPreview(await workflows.autoAssignPreview(projectId))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Preview failed')
    }
  }

  const runApply = async () => {
    try {
      const res = await workflows.autoAssignApply(projectId)
      toast.success(`${res.assigned} conversation(s) assigned`)
      setPreview(null)
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
      load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Apply failed')
    }
  }

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase text-surface-500">
          Topics{topics && topics.length > 0 && ` (${topics.length})`}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={runPreview} title="Auto-assign conversations to topics"
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-surface-500 hover:bg-surface-100">
            <Wand2 size={12} /> Auto-assign
          </button>
          <button onClick={() => setAdding(true)}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50">
            <Plus size={12} /> Add
          </button>
        </div>
      </div>

      {topics === null ? (
        <div className="px-4 py-3 text-sm text-surface-400">Loading…</div>
      ) : topics.length === 0 && !adding ? (
        <div className="px-4 py-3 text-sm italic text-surface-400">No topics yet</div>
      ) : (
        <ul className="divide-y divide-surface-100">
          {topics.map((t) => (
            <li key={t.id} className="flex items-center gap-2 px-4 py-2">
              <span className="min-w-0 flex-1 truncate text-sm text-surface-800">
                {t.name}
              </span>
              {t.conversation_count != null && (
                <span className="shrink-0 text-xs text-surface-400">
                  {t.conversation_count} conv
                </span>
              )}
              {confirming === t.id ? (
                <button onClick={() => removeTopic(t.id)} onBlur={() => setConfirming(null)}
                  className="shrink-0 rounded bg-red-600 px-2 py-0.5 text-xs font-medium text-white">
                  Confirm
                </button>
              ) : (
                <button onClick={() => removeTopic(t.id)} title="Delete topic"
                  className="shrink-0 rounded p-1 text-surface-300 hover:bg-red-50 hover:text-red-600">
                  <Trash2 size={13} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {adding && (
        <div className="flex gap-2 border-t border-surface-100 px-4 py-2">
          <input autoFocus value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') addTopic() }}
            placeholder="Topic name"
            className="flex-1 rounded-md border border-surface-300 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none" />
          <button onClick={addTopic}
            className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700">
            Add
          </button>
          <button onClick={() => setAdding(false)}
            className="rounded-md px-2 py-1 text-xs text-surface-500 hover:bg-surface-100">
            Cancel
          </button>
        </div>
      )}

      {preview && (
        <div className="border-t border-surface-200 px-4 py-3">
          <div className="mb-1 text-xs font-semibold text-surface-600">
            Auto-assign preview: {preview.matched} of {preview.total_candidates}{' '}
            unassigned conversations matched
          </div>
          {preview.assignments.slice(0, 8).map((a, i) => (
            <div key={i} className="truncate text-xs text-surface-500">
              “{a.conversation_title}” → {a.topic_name} (score {a.score})
            </div>
          ))}
          {preview.assignments.length > 8 && (
            <div className="text-xs text-surface-400">
              …and {preview.assignments.length - 8} more
            </div>
          )}
          <div className="mt-2 flex gap-2">
            <button onClick={runApply} disabled={preview.matched === 0}
              className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50">
              Apply {preview.matched} assignment{preview.matched === 1 ? '' : 's'}
            </button>
            <button onClick={() => setPreview(null)}
              className="rounded-md px-3 py-1 text-xs text-surface-500 hover:bg-surface-100">
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
