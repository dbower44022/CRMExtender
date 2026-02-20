import { useMemo, useCallback, useRef, useEffect } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type Row,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useLayoutStore } from '../../stores/layout.ts'
import { useEntityRegistry } from '../../api/registry.ts'
import { useViewConfig, useViewData } from '../../api/views.ts'
import { useArrowNavigation } from '../../hooks/useArrowNavigation.ts'
import { usePrefetch } from '../../hooks/usePrefetch.ts'
import { CellRenderer } from './CellRenderer.tsx'
import {
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import type { FieldDef, ViewColumn } from '../../types/api.ts'

type RowData = Record<string, unknown>

export function DataGrid() {
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const page = useNavigationStore((s) => s.page)
  const sort = useNavigationStore((s) => s.sort)
  const sortDirection = useNavigationStore((s) => s.sortDirection)
  const search = useNavigationStore((s) => s.search)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)
  const setSort = useNavigationStore((s) => s.setSort)
  const setPage = useNavigationStore((s) => s.setPage)
  const showDetailPanel = useLayoutStore((s) => s.showDetailPanel)

  const { data: registry } = useEntityRegistry()
  const { data: viewConfig } = useViewConfig(activeViewId)
  const {
    data: viewData,
    isLoading,
    isFetching,
  } = useViewData({
    viewId: activeViewId,
    page,
    sort: sort ?? viewConfig?.sort_field,
    sortDirection: sortDirection ?? (viewConfig?.sort_direction as 'asc' | 'desc'),
    search,
  })

  const rows = viewData?.rows ?? []
  const total = viewData?.total ?? 0
  const perPage = viewConfig?.per_page ?? 50
  const totalPages = Math.ceil(total / perPage)

  const entityDef = registry?.[activeEntityType]
  const viewColumns = viewConfig?.columns ?? []

  const tableContainerRef = useRef<HTMLDivElement>(null)

  // Build TanStack columns from view config + entity registry
  const columns = useMemo<ColumnDef<RowData>[]>(() => {
    if (!entityDef) return []
    return viewColumns
      .filter((vc: ViewColumn) => {
        const fd = entityDef.fields[vc.field_key]
        return fd && fd.type !== 'hidden'
      })
      .map((vc: ViewColumn) => {
        const fd = entityDef.fields[vc.field_key] as FieldDef
        return {
          id: vc.field_key,
          accessorKey: vc.field_key,
          header: vc.label_override || fd.label,
          size: vc.width_px ?? 150,
          enableSorting: fd.sortable,
          cell: ({ getValue, row }) => (
            <CellRenderer
              value={getValue()}
              fieldDef={fd}
              fieldKey={vc.field_key}
              row={row.original}
              entityType={activeEntityType}
            />
          ),
        } satisfies ColumnDef<RowData>
      })
  }, [entityDef, viewColumns, activeEntityType])

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    rowCount: total,
    getRowId: (row) => String(row.id),
  })

  const { rows: tableRows } = table.getRowModel()

  // Virtual scrolling
  const rowVirtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => 34,
    overscan: 10,
  })

  // Row selection
  const handleRowClick = useCallback(
    (row: Row<RowData>, index: number) => {
      const id = String(row.original.id)
      if (id === selectedRowId) {
        setSelectedRow(null, -1)
      } else {
        setSelectedRow(id, index)
        showDetailPanel()
      }
    },
    [selectedRowId, setSelectedRow, showDetailPanel],
  )

  // Arrow key navigation
  useArrowNavigation({
    rows: tableRows,
    onSelect: handleRowClick,
    containerRef: tableContainerRef,
  })

  // Prefetch adjacent records
  usePrefetch({
    rows,
    selectedRowId,
    entityType: activeEntityType,
  })

  // Column sort handler
  const handleSort = (fieldKey: string) => {
    const fd = entityDef?.fields[fieldKey]
    if (!fd?.sortable) return
    const newDir =
      sort === fieldKey && sortDirection === 'asc' ? 'desc' : 'asc'
    setSort(fieldKey, newDir)
  }

  // Scroll selected row into view
  useEffect(() => {
    const idx = tableRows.findIndex(
      (r) => String(r.original.id) === selectedRowId,
    )
    if (idx >= 0) {
      rowVirtualizer.scrollToIndex(idx, { align: 'auto' })
    }
  }, [selectedRowId, tableRows, rowVirtualizer])

  if (!activeViewId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-400">
        Select a view to get started
      </div>
    )
  }

  // Compute total width so header + body share the same sizing basis
  const totalWidth = table
    .getAllColumns()
    .reduce((sum, col) => sum + col.getSize(), 0)

  return (
    <div className="flex h-full flex-col">
      {/* Scrollable area with sticky header */}
      <div ref={tableContainerRef} className="flex-1 overflow-auto">
        {/* Header — sticky inside the scroll container so scrollbar affects both */}
        <div className="sticky top-0 z-10 border-b border-surface-200 bg-surface-50">
          <div className="flex" style={{ width: totalWidth }}>
            {table.getHeaderGroups().map((headerGroup) =>
              headerGroup.headers.map((header) => {
                const canSort =
                  entityDef?.fields[header.id]?.sortable ?? false
                const isSorted = sort === header.id
                return (
                  <div
                    key={header.id}
                    onClick={() => canSort && handleSort(header.id)}
                    className={`shrink-0 px-3 py-2 text-left text-xs font-semibold text-surface-500 ${
                      canSort
                        ? 'cursor-pointer select-none hover:text-surface-700'
                        : ''
                    }`}
                    style={{ width: header.column.getSize() }}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      {isSorted &&
                        (sortDirection === 'asc' ? (
                          <ChevronUp size={12} />
                        ) : (
                          <ChevronDown size={12} />
                        ))}
                    </div>
                  </div>
                )
              }),
            )}
          </div>
        </div>

        {/* Body */}
        {isLoading &&
          Array.from({ length: 10 }).map((_, i) => (
            <div key={`skeleton-${i}`} className="flex border-b border-surface-100" style={{ width: totalWidth }}>
              {columns.map((col, j) => (
                <div
                  key={j}
                  className="shrink-0 px-3 py-2"
                  style={{ width: col.size ?? 150 }}
                >
                  <div className="h-4 animate-pulse rounded bg-surface-200" />
                </div>
              ))}
            </div>
          ))}

        {!isLoading && tableRows.length === 0 && (
          <div className="px-4 py-12 text-center text-sm text-surface-400">
            No records match your criteria
          </div>
        )}

        {!isLoading && tableRows.length > 0 && (
          <div
            style={{ height: rowVirtualizer.getTotalSize(), width: totalWidth, position: 'relative' }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const row = tableRows[virtualRow.index]
              if (!row) return null
              const isSelected =
                String(row.original.id) === selectedRowId
              return (
                <div
                  key={row.id}
                  data-index={virtualRow.index}
                  ref={rowVirtualizer.measureElement}
                  onClick={() =>
                    handleRowClick(row, virtualRow.index)
                  }
                  className={`absolute left-0 flex cursor-pointer items-center border-b border-surface-100 transition-colors ${
                    isSelected
                      ? 'bg-primary-50'
                      : 'hover:bg-surface-50'
                  }`}
                  style={{
                    width: totalWidth,
                    height: 34,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <div
                      key={cell.id}
                      className="shrink-0 truncate px-3 text-sm"
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-surface-200 bg-surface-50 px-4 py-1.5 text-xs text-surface-500">
        <span>
          {total > 0
            ? `${(page - 1) * perPage + 1}\u2013${Math.min(
                page * perPage,
                total,
              )} of ${total}`
            : 'No records'}
        </span>
        {isFetching && !isLoading && (
          <span className="text-primary-500">Updating...</span>
        )}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="flex h-6 w-6 items-center justify-center rounded text-surface-500 transition-colors hover:bg-surface-200 disabled:opacity-30"
          >
            <ChevronLeft size={14} />
          </button>
          <span>
            {page} / {totalPages || 1}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
            className="flex h-6 w-6 items-center justify-center rounded text-surface-500 transition-colors hover:bg-surface-200 disabled:opacity-30"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
