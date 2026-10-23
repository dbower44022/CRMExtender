// Vitest setup (MAIL-40): DOM matchers and a quiet ResizeObserver for virtualized lists.
import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// jsdom has no ResizeObserver; TanStack Virtual and the message frame use it.
Object.defineProperty(globalThis, 'ResizeObserver', { value: RO, writable: true })
// jsdom has no layout: give virtualized scroll containers a height.
Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, get() { return 600 } })
Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, get() { return 600 } })
Element.prototype.scrollTo = Element.prototype.scrollTo || (() => {})
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {})
vi.stubGlobal('scrollTo', () => {})

afterEach(() => cleanup())
