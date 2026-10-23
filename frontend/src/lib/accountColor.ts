/** Account label colours (Settings → Accounts): the preset palette and the
 * chip style derived from a colour. */

export const ACCOUNT_COLORS: { name: string; value: string }[] = [
  { name: 'Blue', value: '#2563eb' },
  { name: 'Green', value: '#16a34a' },
  { name: 'Orange', value: '#ea580c' },
  { name: 'Purple', value: '#7c3aed' },
  { name: 'Red', value: '#dc2626' },
  { name: 'Teal', value: '#0d9488' },
  { name: 'Pink', value: '#db2777' },
  { name: 'Brown', value: '#92400e' },
  { name: 'Slate', value: '#475569' },
]

/** Inline style for a chip: a light tint of the colour behind text in the colour. */
export function chipStyle(color: string | null | undefined): React.CSSProperties | undefined {
  if (!color) return undefined
  return { backgroundColor: `${color}1f`, color, boxShadow: `inset 0 0 0 1px ${color}66` }
}
