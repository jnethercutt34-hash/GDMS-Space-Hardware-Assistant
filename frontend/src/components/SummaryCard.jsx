import { Card, CardContent } from './ui/card'

/**
 * SummaryCard — metric card used in BOM Analyzer and Schematic DRC dashboards.
 *
 * Props:
 *   title – small all-caps label above the value
 *   value – large primary number/text
 *   sub   – small caption below the value
 *   warn  – if true, renders value in amber (warning colour)
 */
export default function SummaryCard({ title, value, sub, warn }) {
  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">{title}</p>
        <p className={`text-2xl font-bold font-heading ${warn ? 'text-amber-400' : 'text-foreground'}`}>
          {value}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>
      </CardContent>
    </Card>
  )
}
