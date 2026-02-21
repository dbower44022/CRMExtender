import { useMemo, useCallback, useRef, useEffect, useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type Row,
  type ColumnResizeMode,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useLayoutStore } from '../../stores/layout.ts'
import { useEntityRegistry } from '../../api/registry.ts'
import { useViewConfig, useInfiniteViewData } from '../../api/views.ts'
import { useArrowNavigation } from '../../hooks/useArrowNavigation.ts'
import { usePrefetch } from '../../hooks/usePrefetch.ts'
import { CellRenderer } from './CellRenderer.tsx'
import { InlineEditor } from './InlineEditor.tsx'
import { useUpdateViewColumns } from '../../api/views.ts'
import { ChevronUp, ChevronDown, Loader2 } from 'lucide-react'
import type { FieldDef, ViewColumn } from '../../types/api.ts'

type RowData = Record<string, unknown>

export function DataGrid() {
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const sort = useNavigationStore((s) => s.sort)
  const sortDirection = useNavigationStore((s) => s.sortDirection)
  const search = useNavigationStore((s) => s.search)
  const quickFilters = useNavigationStore((s) => s.quickFilters)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)
  const setSort = useNavigationStore((s) => s.setSort)
  const showDetailPanel = useLayoutStore((s) => s.showDetailPanel)

  const { data: registry } = useEntityRegistry()
  const { data: viewConfig } = useViewConfig(activeViewId)
  const {
    data,
    isLoading,
    isFetching,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useInfiniteViewData({
    viewId: activeViewId,
    sort: sort ?? viewConfig?.sort_field,
    sortDirection: sortDirection ?? (viewConfig?.sort_direction as 'asc' | 'desc'),
    search,
    quickFilters,
  })

  const rows = useMemo(() => data?.pages.flatMap((p) => p.rows) ?? [], [data])
  const total = data?.pages[0]?.total ?? 0

  const entityDef = registry?.[activeEntityType]
  const viewColumns = viewConfig?.columns ?? []

  const tableContainerRef = useRef<HTMLDivElement>(null)
  const [editingCell, setEditingCell] = useState<{
    rowId: string
    fieldKey: string
  } | null>(null)

  // Force browser to recalculate overflow after data populates.
  // Without this, overflowY:'auto' doesn't engage until a resize event.
  useEffect(() => {
    const el = tableContainerRef.current
    if (!el || !rows.length) return
    requestAnimationFrame(() => {
      el.style.overflowY = 'scroll'
      requestAnimationFrame(() => {
        el.style.overflowY = 'auto'
      })
    })
  }, [rows.length])

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
          minSize: 50,
          maxSize: 600,
          enableResizing: true,
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

  const columnResizeMode: ColumnResizeMode = 'onChange'

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    rowCount: total,
    getRowId: (row) => String(row.id),
    columnResizeMode,
    enableColumnResizing: true,
  })

  // Column resize persistence — debounced save
  const updateColumns = useUpdateViewColumns(activeViewId ?? '')
  const resizeTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const columnSizingState = table.getState().columnSizing

  useEffect(() => {
    // Skip empty or initial sizing
    if (Object.keys(columnSizingState).length === 0 || !activeViewId || !viewColumns.length) return

    if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current)
    resizeTimerRef.current = setTimeout(() => {
      const cols = viewColumns.map((vc: ViewColumn) => ({
        key: vc.field_key,
        label: vc.label_override || undefined,
        width: columnSizingState[vc.field_key]
          ? Math.round(columnSizingState[vc.field_key])
          : vc.width_px || undefined,
      }))
      updateColumns.mutate({ columns: cols })
    }, 1000)

    return () => {
      if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current)
    }
  }, [columnSizingState]) // eslint-disable-line react-hooks/exhaustive-deps

  const { rows: tableRows } = table.getRowModel()

  // Virtual scrolling
  const rowVirtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => 34,
    overscan: 10,
  })

  // Infinite scroll — fetch next page when near bottom
  useEffect(() => {
    const el = tableContainerRef.current
    if (!el) return
    const onScroll = () => {
      if (
        el.scrollHeight - el.scrollTop - el.clientHeight < 300 &&
        hasNextPage &&
        !isFetchingNextPage
      ) {
        fetchNextPage()
      }
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

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
    <div>
      <div
        ref={tableContainerRef}
        style={{ maxHeight: 'calc(100vh - 130px)', overflowY: 'auto' }}
      >
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
                    className="group/header relative shrink-0 text-left text-xs font-semibold text-surface-500"
                    style={{ width: header.column.getSize() }}
                  >
                    <div
                      onClick={() => canSort && handleSort(header.id)}
                      className={`flex items-center gap-1 px-3 py-2 ${
                        canSort
                          ? 'cursor-pointer select-none hover:text-surface-700'
                          : ''
                      }`}
                    >
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
                    {/* Column resize handle */}
                    <div
                      onMouseDown={header.getResizeHandler()}
                      onTouchStart={header.getResizeHandler()}
                      className={`absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none ${
                        header.column.getIsResizing()
                          ? 'bg-primary-500'
                          : 'bg-transparent group-hover/header:bg-surface-300'
                      }`}
                    />
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
                  {row.getVisibleCells().map((cell) => {
                    const fieldKey = cell.column.id
                    const fd = entityDef?.fields[fieldKey]
                    const isEditable =
                      fd?.editable &&
                      (activeEntityType === 'contact' ||
                        activeEntityType === 'company')
                    const isEditing =
                      editingCell?.rowId === String(row.original.id) &&
                      editingCell?.fieldKey === fieldKey

                    return (
                      <div
                        key={cell.id}
                        data-edit-cell={
                          isEditable
                            ? `${row.original.id}-${fieldKey}`
                            : undefined
                        }
                        className={`shrink-0 truncate px-3 text-sm ${
                          isEditable && !isEditing
                            ? 'cell-editable'
                            : ''
                        }`}
                        style={{ width: cell.column.getSize() }}
                        onDoubleClick={
                          isEditable
                            ? (e) => {
                                e.stopPropagation()
                                setEditingCell({
                                  rowId: String(row.original.id),
                                  fieldKey,
                                })
                              }
                            : undefined
                        }
                      >
                        {isEditing && fd ? (
                          <InlineEditor
                            entityType={activeEntityType}
                            entityId={String(row.original.id)}
                            fieldKey={fd.db_column ?? fieldKey}
                            fieldDef={fd}
                            currentValue={String(
                              row.original[fieldKey] ?? '',
                            )}
                            onClose={() => setEditingCell(null)}
                          />
                        ) : (
                          flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between border-t border-surface-200 bg-surface-50 px-4 py-1.5 text-xs text-surface-500">
        <span>
          {total > 0
            ? `${rows.length} of ${total}`
            : 'No records'}
        </span>
        {isFetchingNextPage && (
          <span className="flex items-center gap-1 text-primary-500">
            <Loader2 size={12} className="animate-spin" />
            Loading more...
          </span>
        )}
        {isFetching && !isLoading && !isFetchingNextPage && (
          <span className="text-primary-500">Updating...</span>
        )}
      </div>
    </div>
  )
}
