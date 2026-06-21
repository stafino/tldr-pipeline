/**
 * Shared filter-chip styling. Both FundingFilterChips and FundingDateFilter
 * render small toggle chips with the same active/inactive treatment; this
 * util is the single source for that string. Keep it a util (not a component)
 * because the chips render as <button> in one place and as a <span> wrapping
 * <select>s in another — a wrapper component wouldn't fit both shapes.
 */
export function filterChipClass(active: boolean): string {
  return (
    'px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors ' +
    (active
      ? 'bg-accent-soft text-text border-accent'
      : 'bg-surface text-text-dim border-border hover:bg-surface-hi hover:text-text')
  );
}
