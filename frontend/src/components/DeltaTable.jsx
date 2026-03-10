const COLUMNS = [
  { key: 'Signal_Name',        label: 'Signal Name' },
  { key: 'Old_Pin',            label: 'Old Pin' },
  { key: 'New_Pin',            label: 'New Pin' },
  { key: 'Old_Bank',           label: 'Old Bank' },
  { key: 'New_Bank',           label: 'New Bank' },
  { key: 'AI_Risk_Assessment', label: 'AI Risk Assessment' },
]

function RiskBadge({ value }) {
  if (!value) {
    return <span className="text-muted-foreground italic text-xs">Pending AI review</span>
  }
  const upper = value.toUpperCase()
  const isHigh   = upper.startsWith('HIGH')
  const isMedium = upper.startsWith('MEDIUM') || upper.startsWith('MED')

  const cls = isHigh
    ? 'bg-destructive/10 text-red-400 border border-destructive/30'
    : isMedium
      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
      : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'

  return (
    <span className={`inline-block text-xs px-2 py-0.5 rounded ${cls}`}>{value}</span>
  )
}

function BankChange({ oldVal, newVal }) {
  const changed = oldVal !== newVal
  return (
    <span className={changed ? 'text-amber-400 font-semibold' : 'text-muted-foreground'}>{newVal}</span>
  )
}

export default function DeltaTable({ data }) {
  const swaps = data?.swapped_pins ?? []
  const total = data?.total_swaps ?? 0

  return (
    <div className="space-y-3">
      {/* Summary stat */}
      <div className="flex flex-wrap gap-8 border-b border-border pb-4 mb-2">
        <div>
          <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">Pin Swaps Detected</p>
          <p className="font-heading text-3xl font-bold text-primary">{total}</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-secondary">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-primary whitespace-nowrap"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {swaps.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-10 text-center text-muted-foreground italic text-sm">
                  No pin swaps detected — the two pinouts are identical.
                </td>
              </tr>
            ) : (
              swaps.map((row, i) => (
                <tr key={i} className="border-t border-border hover:bg-secondary/30 transition-colors">
                  <td className="px-4 py-3 text-foreground font-mono font-semibold text-xs">{row.Signal_Name}</td>
                  <td className="px-4 py-3 text-muted-foreground font-mono text-xs">{row.Old_Pin}</td>
                  <td className="px-4 py-3 text-primary font-mono font-semibold text-xs">{row.New_Pin}</td>
                  <td className="px-4 py-3 text-muted-foreground font-mono text-xs">{row.Old_Bank}</td>
                  <td className="px-4 py-3 font-mono text-xs">
                    <BankChange oldVal={row.Old_Bank} newVal={row.New_Bank} />
                  </td>
                  <td className="px-4 py-3">
                    <RiskBadge value={row.AI_Risk_Assessment} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
