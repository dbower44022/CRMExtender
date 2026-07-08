import { useEffect, useState } from 'react'
import { FolderOpen, X } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import type { ConversationTopic } from '../../types/api.ts'
import { workflows, type TopicRow } from '../../api/workflows.ts'

interface ConversationProjectCardProps {
  topic: ConversationTopic | null
  conversationId: string
}

export function ConversationProjectCard({
  topic,
  conversationId,
}: ConversationProjectCardProps) {
  const queryClient = useQueryClient()
  const [assigning, setAssigning] = useState(false)
  const [topics, setTopics] = useState<TopicRow[] | null>(null)

  useEffect(() => {
    if (assigning && topics === null) {
      workflows.topics()
        .then((res) => setTopics(res.topics))
        .catch(() => setTopics([]))
    }
  }, [assigning, topics])

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['conversation-full'] })
    queryClient.invalidateQueries({ queryKey: ['view-data'] })
  }

  const assign = async (topicId: string) => {
    try {
      await workflows.assignTopic(conversationId, topicId)
      toast.success('Topic assigned')
      setAssigning(false)
      refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Assign failed')
    }
  }

  const unassign = async () => {
    try {
      await workflows.unassignTopic(conversationId)
      toast.success('Topic removed')
      refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Unassign failed')
    }
  }

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-2.5">
        <FolderOpen size={14} className="text-surface-400" />
        <span className="text-xs font-semibold uppercase text-surface-500">
          Topic / Project
        </span>
      </div>
      <div className="px-4 py-3">
        {topic ? (
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-medium text-surface-800">{topic.name}</div>
              {topic.project_name && (
                <div className="mt-0.5 text-xs text-surface-400">
                  Project: {topic.project_name}
                </div>
              )}
            </div>
            <button
              onClick={unassign}
              title="Remove topic assignment"
              className="shrink-0 rounded p-1 text-surface-300 hover:bg-surface-100 hover:text-surface-600"
            >
              <X size={13} />
            </button>
          </div>
        ) : assigning ? (
          topics === null ? (
            <div className="text-sm text-surface-400">Loading topics…</div>
          ) : topics.length === 0 ? (
            <div className="text-sm text-surface-400">
              No topics exist yet — create one on a project first.
            </div>
          ) : (
            <ul className="max-h-48 divide-y divide-surface-100 overflow-y-auto rounded-md border border-surface-200">
              {topics.map((t) => (
                <li key={t.id}>
                  <button
                    onClick={() => assign(t.id)}
                    className="w-full px-3 py-1.5 text-left text-sm hover:bg-surface-50"
                  >
                    {t.name}
                    <span className="ml-2 text-xs text-surface-400">
                      {t.project_name}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-sm text-surface-400">Not assigned to a topic</span>
            <button
              onClick={() => setAssigning(true)}
              className="rounded bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-600 hover:bg-primary-100"
            >
              Assign
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
