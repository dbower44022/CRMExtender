import { DataGrid } from '../grid/DataGrid.tsx'
import { GridToolbar } from '../grid/GridToolbar.tsx'

export function ContentArea() {
  return (
    <div className="flex h-full flex-col overflow-hidden bg-surface-0">
      <GridToolbar />
      <div className="flex-1 overflow-hidden">
        <DataGrid />
      </div>
    </div>
  )
}
