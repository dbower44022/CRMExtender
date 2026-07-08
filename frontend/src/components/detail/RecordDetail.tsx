import { useState } from 'react'
import { useEntityDetail } from '../../api/detail.ts'
import { ManageRecordModal } from './ManageRecordModal.tsx'
import { EntityNotesCard } from '../notes/EntityNotesCard.tsx'
import { ProjectTopicsCard } from '../workflows/ProjectTopicsCard.tsx'
import { IdentityZone } from './IdentityZone.tsx'
import { ContextZone } from './ContextZone.tsx'
import { TimelineZone } from './TimelineZone.tsx'

interface RecordDetailProps {
  entityType: string
  entityId: string
}

export function RecordDetail({ entityType, entityId }: RecordDetailProps) {
  const { data, isLoading, error } = useEntityDetail(entityType, entityId)
  const [managing, setManaging] = useState(false)

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

  const editable = entityType === 'contact' || entityType === 'company'

  return (
    <div className="flex h-full flex-col">
      <IdentityZone
        data={data.identity}
        entityType={entityType}
        entityId={entityId}
        onManage={editable ? () => setManaging(true) : undefined}
      />
      <ContextZone data={data.context} />
      {entityType === 'project' && (
        <div className="border-b border-surface-200 p-3">
          <ProjectTopicsCard projectId={entityId} />
        </div>
      )}
      {['contact', 'company', 'event', 'project'].includes(entityType) && (
        <div className="border-b border-surface-200 p-3">
          <EntityNotesCard entityType={entityType} entityId={entityId} />
        </div>
      )}
      <TimelineZone entries={data.timeline} />
      {managing && editable && (
        <ManageRecordModal
          entityType={entityType as 'contact' | 'company'}
          entityId={entityId}
          entityName={String(data.identity.name ?? data.identity.title ?? '')}
          onClose={() => setManaging(false)}
        />
      )}
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
