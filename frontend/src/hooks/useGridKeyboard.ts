import { useEffect, useCallback } from 'react'
import type { Row } from '@tanstack/react-table'
import { useNavigationStore } from '../stores/navigation.ts'
import { useLayoutStore } from '../stores/layout.ts'
import { useGridDisplayStore, DENSITY_ROW_HEIGHT } from '../stores/gridDisplay.ts'
import type { FieldDef } from '../types/api.ts'

type RowData = Record<string, unknown>

interface UseGridKeyboardOptions {
  rows: Row<RowData>[]
  allRows: RowData[]
  visibleColumnKeys: string[]
  entityDef: Record<string, FieldDef> | undefined
  entityType: string
  containerRef: React.RefObject<HTMLDivElement | null>
  editingCell: { rowId: string; fieldKey: string } | null
  setEditingCell: (cell: { rowId: string; fieldKey: string; initialChars?: string } | null) => void
}

export function useGridKeyboard({
  rows,
  allRows,
  visibleColumnKeys,
  entityDef,
  entityType,
  containerRef,
  editingCell,
  setEditingCell,
}: UseGridKeyboardOptions) {
  const selectedRowIndex = useNavigationStore((s) => s.selectedRowIndex)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)
  const focusedColumn = useNavigationStore((s) => s.focusedColumn)
  const focusAnchorIndex = useNavigationStore((s) => s.focusAnchorIndex)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)
  const setFocusedColumn = useNavigationStore((s) => s.setFocusedColumn)
  const toggleRowSelection = useNavigationStore((s) => s.toggleRowSelection)
  const selectAllRows = useNavigationStore((s) => s.selectAllRows)
  const selectRange = useNavigationStore((s) => s.selectRange)
  const showDetailPanel = useLayoutStore((s) => s.showDetailPanel)
  const toggleDetailPanel = useLayoutStore((s) => s.toggleDetailPanel)
  const density = useGridDisplayStore((s) => s.density)

  // Check if a field is editable for this entity type
  const isFieldEditable = useCallback(
    (fieldKey: string) => {
      if (!entityDef) return false
      const fd = entityDef[fieldKey]
      return fd?.editable && (entityType === 'contact' || entityType === 'company')
    },
    [entityDef, entityType],
  )

  // Find next/prev editable column from a starting position
  const findNextEditableColumn = useCallback(
    (fromCol: number, direction: 1 | -1): { col: number; row: number } | null => {
      let row = selectedRowIndex
      let col = fromCol + direction

      while (row >= 0 && row < rows.length) {
        while (col >= 0 && col < visibleColumnKeys.length) {
          if (isFieldEditable(visibleColumnKeys[col])) {
            return { col, row }
          }
          col += direction
        }
        // Wrap to next/prev row
        row += direction
        col = direction === 1 ? 0 : visibleColumnKeys.length - 1
      }
      return null
    },
    [selectedRowIndex, rows.length, visibleColumnKeys, isFieldEditable],
  )

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept when editing a cell (InlineEditor handles its own keys)
      if (editingCell) {
        // Tab/Shift+Tab within editor: save and move to next editable cell
        if (e.key === 'Tab') {
          e.preventDefault()
          const currentColIndex = visibleColumnKeys.indexOf(editingCell.fieldKey)
          const next = findNextEditableColumn(currentColIndex, e.shiftKey ? -1 : 1)
          if (next) {
            const nextRow = rows[next.row]
            if (nextRow) {
              setEditingCell(null)
              // Small delay so InlineEditor's onBlur fires first
              setTimeout(() => {
                if (next.row !== selectedRowIndex) {
                  setSelectedRow(String(nextRow.original.id), next.row)
                }
                setFocusedColumn(next.col)
                setEditingCell({
                  rowId: String(nextRow.original.id),
                  fieldKey: visibleColumnKeys[next.col],
                })
              }, 10)
            }
          } else {
            setEditingCell(null)
          }
        }
        return
      }

      // Don't intercept when focus is in an input/textarea/select
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return
      }

      // Ctrl/Cmd+A: select all loaded rows
      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault()
        const allIds = allRows.map((r) => String(r.id))
        selectAllRows(allIds)
        return
      }

      // Arrow Down / j
      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault()
        if (rows.length === 0) return

        if (!selectedRowId) {
          const row = rows[0]
          setSelectedRow(String(row.original.id), 0)
          showDetailPanel()
          return
        }

        const nextIndex = selectedRowIndex + 1
        if (nextIndex < rows.length) {
          const row = rows[nextIndex]
          const id = String(row.original.id)

          if (e.shiftKey) {
            // Shift+Arrow: move focus + toggle checkbox on passed row
            toggleRowSelection(id)
          }

          setSelectedRow(id, nextIndex)
          showDetailPanel()
        }
        return
      }

      // Arrow Up / k
      if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault()
        if (rows.length === 0 || !selectedRowId) return

        const prevIndex = selectedRowIndex - 1
        if (prevIndex >= 0) {
          const row = rows[prevIndex]
          const id = String(row.original.id)

          if (e.shiftKey) {
            toggleRowSelection(id)
          }

          setSelectedRow(id, prevIndex)
          showDetailPanel()
        }
        return
      }

      // Arrow Left / Arrow Right: move focused column
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        if (focusedColumn > 0) {
          setFocusedColumn(focusedColumn - 1)
        }
        return
      }

      if (e.key === 'ArrowRight') {
        e.preventDefault()
        if (focusedColumn < visibleColumnKeys.length - 1) {
          setFocusedColumn(focusedColumn + 1)
        }
        return
      }

      // Enter: activate editor on focused cell
      if (e.key === 'Enter') {
        if (selectedRowId && selectedRowIndex >= 0) {
          const fieldKey = visibleColumnKeys[focusedColumn]
          if (fieldKey && isFieldEditable(fieldKey)) {
            e.preventDefault()
            setEditingCell({ rowId: selectedRowId, fieldKey })
          }
        }
        return
      }

      // Space: toggle Detail Panel
      if (e.key === ' ') {
        e.preventDefault()
        toggleDetailPanel()
        return
      }

      // Delete / Backspace: clear focused editable cell
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedRowId && selectedRowIndex >= 0) {
          const fieldKey = visibleColumnKeys[focusedColumn]
          if (fieldKey && isFieldEditable(fieldKey)) {
            e.preventDefault()
            // Dispatch a custom event for cell clear — DataGrid will handle the mutation
            window.dispatchEvent(
              new CustomEvent('grid:clearCell', {
                detail: { rowId: selectedRowId, fieldKey },
              }),
            )
          }
        }
        return
      }

      // Home / End
      if (e.key === 'Home') {
        e.preventDefault()
        if (e.ctrlKey || e.metaKey) {
          // Ctrl+Home: first row, first column
          if (rows.length > 0) {
            setSelectedRow(String(rows[0].original.id), 0)
            setFocusedColumn(0)
            showDetailPanel()
          }
        } else {
          setFocusedColumn(0)
        }
        return
      }

      if (e.key === 'End') {
        e.preventDefault()
        if (e.ctrlKey || e.metaKey) {
          // Ctrl+End: last loaded row, last column
          if (rows.length > 0) {
            const lastIdx = rows.length - 1
            setSelectedRow(String(rows[lastIdx].original.id), lastIdx)
            setFocusedColumn(visibleColumnKeys.length - 1)
            showDetailPanel()
          }
        } else {
          setFocusedColumn(visibleColumnKeys.length - 1)
        }
        return
      }

      // Page Up / Page Down
      if (e.key === 'PageUp' || e.key === 'PageDown') {
        e.preventDefault()
        if (rows.length === 0 || selectedRowIndex < 0) return
        const container = containerRef.current
        const visibleCount = container ? Math.floor(container.clientHeight / DENSITY_ROW_HEIGHT[density]) : 10
        const delta = e.key === 'PageDown' ? visibleCount : -visibleCount
        const newIndex = Math.max(0, Math.min(rows.length - 1, selectedRowIndex + delta))
        if (newIndex !== selectedRowIndex) {
          setSelectedRow(String(rows[newIndex].original.id), newIndex)
          showDetailPanel()
        }
        return
      }

      // Escape: deselect
      if (e.key === 'Escape') {
        setSelectedRow(null, -1)
        return
      }

      // Type-to-edit: printable character on focused editable cell
      if (
        selectedRowId &&
        selectedRowIndex >= 0 &&
        e.key.length === 1 &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey
      ) {
        const fieldKey = visibleColumnKeys[focusedColumn]
        if (fieldKey && isFieldEditable(fieldKey)) {
          e.preventDefault()
          setEditingCell({ rowId: selectedRowId, fieldKey, initialChars: e.key })
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    rows,
    allRows,
    selectedRowId,
    selectedRowIndex,
    focusedColumn,
    focusAnchorIndex,
    visibleColumnKeys,
    editingCell,
    setSelectedRow,
    setFocusedColumn,
    toggleRowSelection,
    selectAllRows,
    selectRange,
    showDetailPanel,
    toggleDetailPanel,
    isFieldEditable,
    findNextEditableColumn,
    setEditingCell,
    containerRef,
    density,
  ])
}
