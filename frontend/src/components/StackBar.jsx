/**
 * StackBar — proportional horizontal bar with legend, used in BOM / DRC summaries.
 *
 * Props:
 *   items – Array of { label: string, count: number, color: string (Tailwind bg class) }
 *   total – total count (sum of all items)
 */
export default function StackBar({ items, total }) {
  if (total === 0) return <p className="text-xs text-muted-foreground">No data</p>
  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden mb-2">
        {items.map((item, i) =>
          item.count > 0 ? (
            <div
              key={i}
              className={item.color}
              style={{ width: `${(item.count / total) * 100}%` }}
              title={`${item.label}: ${item.count}`}
            />
          ) : null
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <div className={`w-2 h-2 rounded-full ${item.color}`} />
            {item.label}: {item.count}
          </div>
        ))}
      </div>
    </div>
  )
}
