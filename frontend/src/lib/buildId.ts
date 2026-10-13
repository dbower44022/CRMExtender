/** Which page bundle is running, and whether a reload is due (v10.43).
 *
 * The server's version route reports the bundle it currently serves; the
 * page knows the bundle it loaded. After a restart on a newer build they
 * differ, and the page reloads itself instead of waiting for a hard
 * reload by hand.
 */

const BUNDLE = /\/assets\/(index-[A-Za-z0-9_-]+)\.js/

/** The hashed name of the script this page loaded, or null outside a build. */
export function loadedBuildId(doc: Document = document): string | null {
  for (const s of Array.from(doc.scripts)) {
    const m = BUNDLE.exec(s.getAttribute('src') ?? '')
    if (m) return m[1]
  }
  return null
}

/** True when the served bundle is known, differs from the loaded one, and nothing is being composed. */
export function shouldReload(loaded: string | null, served: string | null | undefined, composing: boolean): boolean {
  if (!loaded || !served) return false
  if (loaded === served) return false
  return !composing
}
