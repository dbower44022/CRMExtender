import { useEffect } from 'react'
import type { Row } from '@tanstack/react-table'
import { useNavigationStore } from '../stores/navigation.ts'
import { useLayoutStore } from '../stores/layout.ts'

interface UseArrowNavigationOptions {
  rows: Row<Record<string, unknown>>[]
  onSelect: (row: Row<Record<string, unknown>>, index: number) => void
  containerRef: React.RefObject<HTMLDivElement | null>
}

export function useArrowNavigation({
  rows,
  onSelect,
  containerRef: _containerRef,
}: UseArrowNavigationOptions) {
  const selectedRowIndex = useNavigationStore((s) => s.selectedRowIndex)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)
  const showDetailPanel = useLayoutStore((s) => s.showDetailPanel)
  const page = useNavigationStore((s) => s.page)
  const setPage = useNavigationStore((s) => s.setPage)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return
      }

      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault()
        if (rows.length === 0) return

        if (!selectedRowId) {
          // Select first row
          const row = rows[0]
          setSelectedRow(String(row.original.id), 0)
          showDetailPanel()
          return
        }

        const nextIndex = selectedRowIndex + 1
        if (nextIndex < rows.length) {
          const row = rows[nextIndex]
          onSelect(row, nextIndex)
        } else if (nextIndex >= rows.length) {
          // Auto-paginate forward
          setPage(page + 1)
        }
      }

      if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault()
        if (rows.length === 0 || !selectedRowId) return

        const prevIndex = selectedRowIndex - 1
        if (prevIndex >= 0) {
          const row = rows[prevIndex]
          onSelect(row, prevIndex)
        } else if (page > 1) {
          // Auto-paginate backward
          setPage(page - 1)
        }
      }

      if (e.key === 'Escape') {
        setSelectedRow(null, -1)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    rows,
    selectedRowId,
    selectedRowIndex,
    setSelectedRow,
    showDetailPanel,
    onSelect,
    page,
    setPage,
  ])
}
