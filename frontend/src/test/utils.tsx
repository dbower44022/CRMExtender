/** Test helpers (MAIL-40): render inside a fresh QueryClient; stub fetch per route. */
import type { ReactElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { vi } from 'vitest'

export function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchInterval: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

/** fetch stub: map a path prefix to a JSON body (or a function of the URL). */
export function stubFetch(routes: Record<string, unknown | ((url: string, init?: RequestInit) => unknown)>) {
  const calls: { url: string; init?: RequestInit }[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push({ url, init })
    for (const [prefix, body] of Object.entries(routes)) {
      if (url.includes(prefix)) {
        const data = typeof body === 'function' ? (body as (u: string, i?: RequestInit) => unknown)(url, init) : body
        return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
    }
    return new Response('not found', { status: 404 })
  }))
  return calls
}
