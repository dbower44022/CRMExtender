import { format, parseISO } from 'date-fns'
import type { FieldDef } from '../../types/api.ts'

interface CellRendererProps {
  value: unknown
  fieldDef: FieldDef
  fieldKey: string
  row: Record<string, unknown>
  entityType: string
}

export function CellRenderer({
  value,
  fieldDef,
  fieldKey,
  row,
}: CellRendererProps) {
  if (value == null || value === '') {
    return <span className="text-surface-300">&mdash;</span>
  }

  // Link cells
  if (fieldDef.link) {
    const href = resolveLink(fieldDef.link, row)
    if (href) {
      return (
        <a
          href={href}
          onClick={(e) => {
            e.stopPropagation()
          }}
          className="text-primary-600 hover:text-primary-700 hover:underline"
        >
          {String(value)}
        </a>
      )
    }
  }

  // Type-specific rendering
  switch (fieldDef.type) {
    case 'datetime':
      return <DateTimeCell value={value} />
    case 'number':
      if (fieldKey === 'score') {
        return <ScoreCell value={value} />
      }
      return <span>{String(value)}</span>
    case 'select':
      return <SelectCell value={value} />
    default:
      return <span>{String(value)}</span>
  }
}

function DateTimeCell({ value }: { value: unknown }) {
  const str = String(value)
  try {
    const date = parseISO(str)
    const formatted = format(date, 'MMM d, yyyy')
    return (
      <span title={str} className="text-surface-600">
        {formatted}
      </span>
    )
  } catch {
    return <span>{str}</span>
  }
}

function ScoreCell({ value }: { value: unknown }) {
  const num = Number(value)
  if (isNaN(num)) return <span>{String(value)}</span>

  const pct = Math.round(num * 100)
  const color =
    pct >= 70
      ? 'bg-green-500'
      : pct >= 40
        ? 'bg-amber-500'
        : 'bg-surface-300'

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-surface-200">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-surface-500">{pct}%</span>
    </div>
  )
}

function SelectCell({ value }: { value: unknown }) {
  const str = String(value)
  const colorMap: Record<string, string> = {
    active: 'bg-green-100 text-green-700',
    inactive: 'bg-surface-100 text-surface-500',
    archived: 'bg-amber-100 text-amber-700',
  }
  const cls = colorMap[str.toLowerCase()] ?? 'bg-surface-100 text-surface-600'
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {str}
    </span>
  )
}

function resolveLink(
  template: string,
  row: Record<string, unknown>,
): string | null {
  let href = template
  const matches = template.match(/\{(\w+)\}/g)
  if (!matches) return template
  for (const m of matches) {
    const key = m.slice(1, -1)
    const val = row[key]
    if (val == null || val === '') return null
    href = href.replace(m, String(val))
  }
  return href
}
