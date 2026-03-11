import { Badge } from './ui/badge'

const COLUMNS = [
  { key: 'Signal_Class',  label: 'Signal Class' },
  { key: 'Rule_Type',     label: 'Rule Type' },
  { key: 'Min',           label: 'Min' },
  { key: 'Typ',           label: 'Typ' },
  { key: 'Max',           label: 'Max' },
  { key: 'Unit',          label: 'Unit' },
  { key: 'Source_Page',   label: 'Source' },
  { key: 'Notes',         label: 'Notes' },
]

const RULE_TYPE_COLORS = {
  Impedance:         'bg-blue-500/20 text-blue-400 border-blue-500/30',
  Propagation_Delay: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  Skew:              'bg-amber-500/20 text-amber-400 border-amber-500/30',
  Rise_Time:         'bg-purple-500/20 text-purple-400 border-purple-500/30',
  Fall_Time:         'bg-purple-500/20 text-purple-400 border-purple-500/30',
  Voltage_Level:     'bg-green-500/20 text-green-400 border-green-500/30',
  Spacing:           'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  Max_Length:         'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  Differential_Pair: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  Overshoot:         'bg-red-500/20 text-red-400 border-red-500/30',
  Undershoot:        'bg-red-500/20 text-red-400 border-red-500/30',
  Crosstalk:         'bg-orange-500/20 text-orange-400 border-orange-500/30',
}

export default function ConstraintTable({ constraints }) {
  if (!constraints || constraints.length === 0) {
    return (
      <div className="text-center py-10 text-muted-foreground text-sm">
        No constraints extracted. Upload a datasheet with SI/PI specifications.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {constraints.map((rule, i) => (
            <tr
              key={i}
              className="border-b border-border/50 hover:bg-secondary/30 transition-colors"
            >
              <td className="px-3 py-2.5 font-mono text-xs font-medium text-foreground">
                {rule.Signal_Class}
              </td>
              <td className="px-3 py-2.5">
                <Badge
                  className={
                    RULE_TYPE_COLORS[rule.Rule_Type] ||
                    'bg-secondary text-muted-foreground border-border'
                  }
                >
                  {rule.Rule_Type?.replace(/_/g, ' ')}
                </Badge>
              </td>
              <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">
                {rule.Min || '—'}
              </td>
              <td className="px-3 py-2.5 font-mono text-xs text-foreground font-medium">
                {rule.Typ || '—'}
              </td>
              <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">
                {rule.Max || '—'}
              </td>
              <td className="px-3 py-2.5 text-xs text-muted-foreground">
                {rule.Unit || '—'}
              </td>
              <td className="px-3 py-2.5 text-xs text-muted-foreground">
                {rule.Source_Page ? `p.${rule.Source_Page}` : '—'}
              </td>
              <td className="px-3 py-2.5 text-xs text-muted-foreground max-w-[200px] truncate">
                {rule.Notes || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 text-xs text-muted-foreground">
        {constraints.length} constraint{constraints.length !== 1 ? 's' : ''} extracted
      </div>
    </div>
  )
}
