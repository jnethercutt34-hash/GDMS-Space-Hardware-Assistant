// Columns required by the Xpedition Databook schema (Phase 1 spec)
const COLUMNS = [
  { key: 'Part_Number',        label: 'Part Number' },
  { key: 'Manufacturer',       label: 'Manufacturer' },
  { key: 'Value',              label: 'Value' },
  { key: 'Tolerance',          label: 'Tolerance' },
  { key: 'Voltage_Rating',     label: 'Voltage Rating' },
  { key: 'Package_Type',       label: 'Package Type' },
  { key: 'Pin_Count',          label: 'Pin Count' },
  { key: 'Thermal_Resistance', label: 'Thermal Resistance' },
]

export default function DataTable({ data }) {
  const rows = data?.rows ?? []

  return (
    <div className="space-y-6">
      {/* Xpedition parameter table */}
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
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLUMNS.length}
                  className="px-4 py-10 text-center text-muted-foreground italic text-sm"
                >
                  No components were extracted. Verify the PDF has selectable text and try again.
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr
                  key={i}
                  className="border-t border-border hover:bg-secondary/30 transition-colors"
                >
                  {COLUMNS.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-foreground whitespace-nowrap font-mono text-xs">
                      {row[col.key] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Raw extracted text preview */}
      {data?.extracted_text && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
            Raw Extracted Text — {data.page_count} page{data.page_count !== 1 ? 's' : ''}
          </p>
          <pre className="bg-secondary/30 border border-border rounded-lg p-4 text-xs text-muted-foreground max-h-64 overflow-y-auto whitespace-pre-wrap break-words font-mono">
            {data.extracted_text.slice(0, 3000)}
            {data.extracted_text.length > 3000 && '\n\n… (truncated — full text sent to AI layer)'}
          </pre>
        </div>
      )}
    </div>
  )
}
