import { useEntityDetail } from '../../api/detail.ts'
import { IdentityZone } from './IdentityZone.tsx'
import { ContextZone } from './ContextZone.tsx'
import { TimelineZone } from './TimelineZone.tsx'

interface RecordDetailProps {
  entityType: string
  entityId: string
}

export function RecordDetail({ entityType, entityId }: RecordDetailProps) {
  const { data, isLoading, error } = useEntityDetail(entityType, entityId)

  if (isLoading) {
    return <DetailSkeleton />
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-red-500">
        Failed to load record details.
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex h-full flex-col">
      <IdentityZone
        data={data.identity}
        entityType={entityType}
        entityId={entityId}
      />
      <ContextZone data={data.context} />
      <TimelineZone entries={data.timeline} />
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <div className="space-y-2">
        <div className="h-6 w-48 animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-32 animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-64 animate-pulse rounded bg-surface-200" />
      </div>
      <div className="h-px bg-surface-200" />
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-surface-200" />
      </div>
    </div>
  )
}
