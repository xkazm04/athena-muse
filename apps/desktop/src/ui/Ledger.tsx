import type { HTMLAttributes, ReactNode } from "react";

export interface LedgerColumn<R> {
  key: string;
  head: ReactNode;
  cell: (row: R) => ReactNode;
  /** A class on this column's head and every cell (a number column's alignment, a skin's hook). */
  className?: string;
  /** A class on the cells only, after `className`. */
  cellClassName?: string;
}

type RowAttrs = HTMLAttributes<HTMLTableRowElement> & { [data: `data-${string}`]: string | undefined };

export interface LedgerProps<R> {
  columns: readonly LedgerColumn<R>[];
  rows: readonly R[];
  rowKey: (row: R) => string | number;
  /** The table's own class: the skin. */
  className?: string;
  /** Wraps the table in a box with this class (a horizontal scroll box). */
  wrapClassName?: string;
  /** The table's accessible name. */
  label?: string;
  headClassName?: string;
  rowClassName?: string;
  /** Per-row attributes: a row that opens something, its state for the skin. */
  rowProps?: (row: R) => RowAttrs;
  /** One full-width row instead of the rows, when there are none (or they could not be read). */
  empty?: ReactNode;
  emptyClassName?: string;
  /** The totals line as the foot's cells, under the rows. */
  totals?: readonly ReactNode[];
  totalsClassName?: string;
  /** Classes on the totals cells, by position. */
  totalsCellClassNames?: readonly (string | undefined)[];
}

/**
 * The app's row table: a head, one row per item with badges in its cells, and a totals line. The
 * Athena page's costs and the twins page both draw it; each skins it through its classes.
 */
export function Ledger<R>({
  columns,
  rows,
  rowKey,
  className,
  wrapClassName,
  label,
  headClassName,
  rowClassName,
  rowProps,
  empty,
  emptyClassName,
  totals,
  totalsClassName,
  totalsCellClassNames = [],
}: LedgerProps<R>) {
  const table = (
    <table className={className} aria-label={label}>
      <thead>
        <tr className={headClassName}>
          {columns.map((c) => (
            <th key={c.key} scope="col" className={c.className}>
              {c.head}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && empty !== undefined ? (
          <tr className={[rowClassName, emptyClassName].filter(Boolean).join(" ") || undefined}>
            <td colSpan={columns.length}>{empty}</td>
          </tr>
        ) : (
          rows.map((r) => (
            <tr key={rowKey(r)} className={rowClassName} {...rowProps?.(r)}>
              {columns.map((c) => (
                <td key={c.key} className={[c.className, c.cellClassName].filter(Boolean).join(" ") || undefined}>
                  {c.cell(r)}
                </td>
              ))}
            </tr>
          ))
        )}
      </tbody>
      {totals && (
        <tfoot>
          <tr className={totalsClassName}>
            {totals.map((cell, i) => (
              <td key={i} className={totalsCellClassNames[i]}>
                {cell}
              </td>
            ))}
          </tr>
        </tfoot>
      )}
    </table>
  );
  return wrapClassName ? <div className={wrapClassName}>{table}</div> : table;
}
