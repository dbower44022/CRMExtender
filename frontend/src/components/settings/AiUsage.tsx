import { useAiUsage, type AiUsageTotals } from '../../api/settings.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'

const fmtInt = (n: number) => n.toLocaleString()
const fmtUsd = (n: number) => `$${n.toFixed(n >= 10 ? 2 : 4)}`

function TotalsRow({ label, t }: { label: string; t: AiUsageTotals }) {
  return (
    <tr className="border-t border-surface-100">
      <td className="py-1.5 pr-3 text-surface-700">{label}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(t.calls)}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(t.input_tokens)}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(t.output_tokens)}</td>
      <td className="py-1.5 text-right tabular-nums">
        {fmtUsd(t.cost_usd)}
        {t.unpriced_calls > 0 && (
          <span className="ml-1 text-xs text-surface-400" title={`${t.unpriced_calls} call(s) on a model with no price in the table`}>
            +{t.unpriced_calls}?
          </span>
        )}
      </td>
    </tr>
  )
}

/** Token accounting for Anthropic calls (Mail Client MAIL-49): what the
 * summariser spent today, over 30 days and all time, by model and mode,
 * and the batches still open. Costs are estimates from a dated price table. */
export function AiUsage() {
  const { data, isLoading, error } = useAiUsage()

  return (
    <div className="mt-8 border-t border-surface-200 pt-6">
      <h2 className="mb-1 text-base font-semibold text-surface-800">AI usage</h2>
      {isLoading && <p className="text-sm text-surface-500">Loading...</p>}
      {error && <p className="text-sm text-red-600">Could not load AI usage.</p>}
      {data && (
        <>
          <p className="mb-3 text-xs text-surface-500">
            Summaries run on <code className="rounded bg-surface-100 px-1 font-mono">{data.model}</code>.
            Cost is an estimate from list prices dated {data.price_table_date}; batches are counted at half price.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-surface-500">
                  <th className="pb-1 text-left font-medium">Period</th>
                  <th className="pb-1 text-right font-medium">Calls</th>
                  <th className="pb-1 text-right font-medium">Input tokens</th>
                  <th className="pb-1 text-right font-medium">Output tokens</th>
                  <th className="pb-1 text-right font-medium">Est. cost</th>
                </tr>
              </thead>
              <tbody>
                <TotalsRow label="Today" t={data.periods.today} />
                <TotalsRow label="Last 30 days" t={data.periods.last_30_days} />
                <TotalsRow label="All time" t={data.periods.all_time} />
              </tbody>
            </table>
          </div>

          {data.by_model_30_days.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <h3 className="mb-1 text-sm font-medium text-surface-700">Last 30 days by model</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-surface-500">
                    <th className="pb-1 text-left font-medium">Model</th>
                    <th className="pb-1 text-left font-medium">Mode</th>
                    <th className="pb-1 text-right font-medium">Calls</th>
                    <th className="pb-1 text-right font-medium">Input</th>
                    <th className="pb-1 text-right font-medium">Output</th>
                    <th className="pb-1 text-right font-medium">Est. cost</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_model_30_days.map((m) => (
                    <tr key={`${m.model}-${m.mode}`} className="border-t border-surface-100">
                      <td className="py-1.5 pr-3 font-mono text-xs text-surface-700">{m.model}</td>
                      <td className="py-1.5 pr-3 text-surface-600">{m.mode}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(m.calls)}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(m.input_tokens)}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(m.output_tokens)}</td>
                      <td className="py-1.5 text-right tabular-nums">{fmtUsd(m.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4">
            <h3 className="mb-1 text-sm font-medium text-surface-700">Summary batches</h3>
            {data.batches.length === 0 ? (
              <p className="text-xs text-surface-500">
                No batch has been submitted in the last 30 days. Batches are used when more settled conversations than the threshold above are waiting.
              </p>
            ) : (
              <ul className="space-y-1 text-sm">
                {data.batches.map((b) => {
                  const open = !b.processed_at && b.status !== 'failed'
                  return (
                    <li key={b.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs ${open ? 'bg-amber-50 text-amber-800' : b.status === 'failed' ? 'bg-red-50 text-red-700' : 'bg-surface-100 text-surface-600'}`}
                      >
                        {open ? (b.status === 'ended' ? 'applying' : 'in progress') : b.status}
                      </span>
                      <span className="tabular-nums text-surface-700">
                        {fmtInt(b.submitted_count)} sent, {fmtInt(b.succeeded)} ok, {fmtInt(b.errored + b.expired + b.canceled)} failed
                      </span>
                      <span className="text-xs text-surface-500">submitted {formatTimestamp(b.created_at)}</span>
                      {b.error && <span className="text-xs text-red-600">{b.error}</span>}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  )
}
