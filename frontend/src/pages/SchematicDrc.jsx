import { useState } from 'react'
import {
  Upload, FileText, Download, AlertTriangle, CheckCircle, XCircle,
  Info, Shield, ChevronDown, ChevronRight, Search, Filter, Cpu, Zap,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import ModuleGuide from '../components/ModuleGuide'
import SectionLabel from '../components/SectionLabel'
import SummaryCard from '../components/SummaryCard'
import StackBar from '../components/StackBar'
import { downloadBlob } from '../lib/downloadBlob'

const SEVERITY_STYLE = {
  Error:   { color: 'bg-red-500/20 text-red-400 border-red-500/30',     icon: <XCircle className="h-3.5 w-3.5" /> },
  Warning: { color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  Info:    { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',   icon: <Info className="h-3.5 w-3.5" /> },
}

const CATEGORY_STYLE = {
  Power:        'bg-amber-500/20 text-amber-400 border-amber-500/30',
  Decoupling:   'bg-blue-500/20 text-blue-400 border-blue-500/30',
  Termination:  'bg-violet-500/20 text-violet-400 border-violet-500/30',
  Interface:    'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  Connectivity: 'bg-secondary text-muted-foreground border-border',
  Naming:       'bg-secondary text-muted-foreground border-border',
}

export default function SchematicDrc() {
  const [report, setReport]       = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError]         = useState(null)
  const [dragOver, setDragOver]   = useState(false)
  const [expanded, setExpanded]   = useState({})
  const [sortField, setSortField] = useState('severity')
  const [sortAsc, setSortAsc]     = useState(true)
  const [filter, setFilter]       = useState('')

  // --- Upload & analyze ---
  const uploadFile = async (file) => {
    if (!file) return
    setIsLoading(true)
    setError(null)
    setReport(null)
    setExpanded({})

    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch('/api/drc/analyze', { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'DRC analysis failed')
      }
      setReport(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileInput = (e) => uploadFile(e.target.files?.[0])

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    uploadFile(e.dataTransfer.files?.[0])
  }

  // --- Export ---
  const handleExport = async (format) => {
    if (!report) return
    try {
      const res = await fetch('/api/drc/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report, format }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Export failed')
      }
      const blob = await res.blob()
      const ext = format === 'csv' ? 'csv' : 'md'
      downloadBlob(blob, `drc_report.${ext}`)
    } catch (e) {
      setError(e.message)
    }
  }

  // --- Sorting ---
  const handleSort = (field) => {
    if (sortField === field) setSortAsc(!sortAsc)
    else { setSortField(field); setSortAsc(true) }
  }

  // --- Derived data ---
  const sevOrder = { Error: 3, Warning: 2, Info: 1 }
  const filteredViolations = report
    ? report.violations
        .filter((v) => {
          if (!filter) return true
          const q = filter.toLowerCase()
          return (
            v.rule_id.toLowerCase().includes(q) ||
            v.message.toLowerCase().includes(q) ||
            v.category.toLowerCase().includes(q) ||
            v.affected_components.some(c => c.toLowerCase().includes(q)) ||
            v.affected_nets.some(n => n.toLowerCase().includes(q))
          )
        })
        .sort((a, b) => {
          let va, vb
          if (sortField === 'severity') {
            va = sevOrder[a.severity] ?? 0
            vb = sevOrder[b.severity] ?? 0
          } else if (sortField === 'rule_id') {
            va = a.rule_id; vb = b.rule_id
          } else if (sortField === 'category') {
            va = a.category; vb = b.category
          } else {
            va = a[sortField] ?? ''; vb = b[sortField] ?? ''
          }
          if (va < vb) return sortAsc ? 1 : -1
          if (va > vb) return sortAsc ? -1 : 1
          return 0
        })
    : []

  const ns = report?.netlist_summary
  const overallStyle = !report ? null :
    report.overall_status === 'PASS'    ? 'text-green-400' :
    report.overall_status === 'WARNING' ? 'text-amber-400' :
    'text-red-400'

  return (
    <div>
      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Step 5 · Schematic DRC
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Schematic Design Rule Check
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Upload an Xpedition or OrCAD netlist to run deterministic design rules and AI-powered
          heuristic checks — catching power, decoupling, termination, and interface issues before layout.
        </p>
      </section>

      <ModuleGuide
        title="Schematic DRC Guide"
        purpose="This module runs two layers of checks on a parsed schematic netlist: (1) deterministic rules — power net fan-out, decoupling capacitor presence, termination on high-speed nets, short circuit detection, and 5 more; (2) AI heuristic checks — interface protocol validation (I2C pull-ups, SPI CS lines, JTAG chain), power sequencing, and cross-domain signal detection."
        inputFormat="A netlist export from Xpedition (.asc format), Altium (.csv netlist), or OrCAD (.net). The parser handles all three formats automatically."
        outputFormat="A violation table with severity (Error/Warning/Info), category, rule ID, affected nets and components, and recommended action. Exportable as a CSV or Markdown report for design reviews."
        workflow={[
          { step: 'Export Netlist', description: 'From Xpedition: File > Export > Netlist (ASC format). From Altium: Project > Export Netlist. From OrCAD: Tools > Export > Netlist.' },
          { step: 'Upload & Analyze', description: 'Drop the netlist file. Both deterministic and AI checks run automatically. AI checks take 10-30 seconds depending on netlist size.' },
          { step: 'Review Violations', description: 'Filter by severity and expand rows for details. Errors must be resolved before layout. Warnings should be reviewed. AI violations are tagged.' },
          { step: 'Export Report', description: 'Download a CSV for tracking in your design review tool, or a Markdown report for the design review document.' },
        ]}
        tips={[
          'Run DRC at schematic completion, not just before layout — earlier is cheaper to fix.',
          'The AI checks are heuristic. Confirm AI-flagged violations against your actual schematic before acting on them.',
          'I2C pull-up detection looks for resistors on SDA/SCL nets. Name your nets descriptively (I2C_SDA, I2C_SCL) for accurate detection.',
          'Power sequencing checks look for EN/PGOOD connections between regulators. Standard enable/disable paths are usually fine.',
        ]}
        warnings={[
          'The deterministic rules are conservative — some warnings may be intentional design choices. Use your engineering judgment.',
          'The parser does not support schematic-level hierarchical blocks or encrypted netlists.',
          'AI checks are best-effort and may miss issues in very large designs (> 5,000 nets). Always supplement with manual review.',
        ]}
      />

      {/* Error banner */}
      {error && (
        <div className="mb-6 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 flex items-center justify-between">
          <div>
            <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">DRC Error</p>
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-muted-foreground hover:text-foreground ml-4 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Step 1 — Upload */}
      <section className="mb-14">
        <SectionLabel icon={<Upload className="h-4 w-4" />} step="1" label="Upload Netlist" />
        <Card>
          <CardContent className="pt-6">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={[
                'border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer',
                dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50',
              ].join(' ')}
              onClick={() => document.getElementById('drc-file-input').click()}
            >
              <input
                id="drc-file-input"
                type="file"
                accept=".asc,.csv,.net,.txt"
                className="hidden"
                onChange={handleFileInput}
              />
              <FileText className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-sm text-foreground font-medium">
                {isLoading ? 'Running DRC\u2026' : 'Drop a netlist file here or click to browse'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Supports Xpedition (.asc), Altium (.csv), OrCAD (.net) netlist formats
              </p>
            </div>
            {isLoading && (
              <p className="text-xs text-muted-foreground text-center mt-3 animate-pulse">
                Running deterministic rules + AI heuristic checks\u2026 10\u201330 seconds.
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Step 2 — Dashboard */}
      {report && (
        <section className="mb-14">
          <SectionLabel icon={<Shield className="h-4 w-4" />} step="2" label="DRC Summary" />

          {/* Overall status banner */}
          <div className={`mb-4 rounded-lg border px-4 py-3 flex items-center gap-3 ${
            report.overall_status === 'PASS'    ? 'border-green-500/30 bg-green-500/10' :
            report.overall_status === 'WARNING' ? 'border-amber-500/30 bg-amber-500/10' :
            'border-red-500/30 bg-red-500/10'
          }`}>
            {report.overall_status === 'PASS'
              ? <CheckCircle className="h-5 w-5 text-green-400 shrink-0" />
              : report.overall_status === 'WARNING'
              ? <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0" />
              : <XCircle className="h-5 w-5 text-red-400 shrink-0" />
            }
            <span className={`font-bold font-heading text-lg ${overallStyle}`}>
              {report.overall_status}
            </span>
            <span className="text-sm text-muted-foreground">
              &mdash; {report.error_count} error{report.error_count !== 1 ? 's' : ''},
              &nbsp;{report.warning_count} warning{report.warning_count !== 1 ? 's' : ''},
              &nbsp;{report.info_count} info
            </span>
          </div>

          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <SummaryCard title="Components" value={ns.component_count} sub="reference designators" />
            <SummaryCard title="Nets" value={ns.net_count} sub={`${ns.power_net_count} power, ${ns.ground_net_count} ground`} />
            <SummaryCard title="Errors" value={report.error_count} sub="must fix before layout" warn={report.error_count > 0} />
            <SummaryCard title="Warnings" value={report.warning_count} sub={`${report.pass_count} rules passed`} />
          </div>

          {/* Severity distribution */}
          <Card className="mb-4">
            <CardHeader><CardTitle className="text-sm">Violation Severity Distribution</CardTitle></CardHeader>
            <CardContent>
              <StackBar
                total={report.violations.length || 1}
                items={[
                  { label: 'Error',   count: report.error_count,   color: 'bg-red-500' },
                  { label: 'Warning', count: report.warning_count, color: 'bg-amber-500' },
                  { label: 'Info',    count: report.info_count,    color: 'bg-blue-500' },
                ]}
              />
            </CardContent>
          </Card>
        </section>
      )}

      {/* Step 3 — Violations Table */}
      {report && (
        <section className="mb-14">
          <SectionLabel icon={<Search className="h-4 w-4" />} step="3" label="Violations" />

          {/* Filter + export */}
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <div className="relative flex-1 min-w-48">
              <Filter className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Filter by rule ID, message, net, component\u2026"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-transparent border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <Button size="sm" onClick={() => handleExport('csv')}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> CSV Report
            </Button>
            <Button size="sm" variant="outline" onClick={() => handleExport('markdown')}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> Markdown Report
            </Button>
          </div>

          {report.violations.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center">
                <CheckCircle className="mx-auto h-8 w-8 text-green-400 mb-2" />
                <p className="text-sm font-medium text-foreground">No violations found</p>
                <p className="text-xs text-muted-foreground mt-1">
                  All {report.pass_count} deterministic rules passed and no AI issues detected.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-4 px-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground uppercase tracking-widest">
                        <th className="py-2 pl-4 pr-2 text-left w-6"></th>
                        <SortHeader label="Rule ID" field="rule_id" current={sortField} asc={sortAsc} onSort={handleSort} />
                        <SortHeader label="Severity" field="severity" current={sortField} asc={sortAsc} onSort={handleSort} />
                        <SortHeader label="Category" field="category" current={sortField} asc={sortAsc} onSort={handleSort} />
                        <th className="py-2 pr-4 text-left">Message</th>
                        <th className="py-2 pr-2 text-left">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredViolations.map((v, i) => (
                        <ViolationRow
                          key={i}
                          v={v}
                          expanded={!!expanded[i]}
                          onToggle={() => setExpanded(prev => ({ ...prev, [i]: !prev[i] }))}
                        />
                      ))}
                      {filteredViolations.length === 0 && (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-muted-foreground">
                            No violations match your filter.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </section>
      )}
    </div>
  )
}

// ── Table helpers ──────────────────────────────────────────────────────────

function SortHeader({ label, field, current, asc, onSort, align = 'left' }) {
  const active = current === field
  return (
    <th
      className={`py-2 pr-2 cursor-pointer select-none hover:text-foreground transition-colors ${align === 'right' ? 'text-right' : 'text-left'}`}
      onClick={() => onSort(field)}
    >
      {label}
      {active ? (asc ? ' \u2191' : ' \u2193') : ' \u2195'}
    </th>
  )
}

function ViolationRow({ v, expanded, onToggle }) {
  const sty = SEVERITY_STYLE[v.severity] ?? SEVERITY_STYLE.Info
  const catColor = CATEGORY_STYLE[v.category] ?? CATEGORY_STYLE.Connectivity
  return (
    <>
      <tr
        className="border-b border-border/50 hover:bg-secondary/30 cursor-pointer"
        onClick={onToggle}
      >
        {/* expand chevron */}
        <td className="py-2 pl-4 pr-2 text-muted-foreground">
          {expanded
            ? <ChevronDown className="h-3.5 w-3.5" />
            : <ChevronRight className="h-3.5 w-3.5" />
          }
        </td>
        {/* Rule ID */}
        <td className="py-2 pr-2 font-mono text-foreground">{v.rule_id}</td>
        {/* Severity */}
        <td className="py-2 pr-2">
          <Badge className={`text-xs flex items-center gap-1 w-fit ${sty.color}`}>
            {sty.icon}
            {v.severity}
          </Badge>
        </td>
        {/* Category */}
        <td className="py-2 pr-2">
          <Badge className={`text-xs ${catColor}`}>{v.category}</Badge>
        </td>
        {/* Message (truncated) */}
        <td className="py-2 pr-4 max-w-xs">
          <span className="line-clamp-1 text-muted-foreground">{v.message}</span>
        </td>
        {/* AI / Deterministic */}
        <td className="py-2 pr-2">
          {v.ai_generated
            ? <Badge className="text-xs bg-violet-500/20 text-violet-400 border-violet-500/30">AI</Badge>
            : <Badge className="text-xs bg-secondary text-muted-foreground border-border">Rule</Badge>
          }
        </td>
      </tr>

      {/* Expanded detail */}
      {expanded && (
        <tr className="border-b border-border bg-secondary/20">
          <td colSpan={6} className="py-3 px-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                  Full Message
                </p>
                <p className="text-xs text-foreground">{v.message}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                  Recommendation
                </p>
                <p className="text-xs text-foreground">{v.recommendation}</p>
              </div>
              {v.affected_nets.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                    Affected Nets
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {v.affected_nets.map((n, i) => (
                      <code key={i} className="text-xs bg-card border border-border rounded px-1 py-0.5 text-foreground">{n}</code>
                    ))}
                  </div>
                </div>
              )}
              {v.affected_components.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                    Affected Components
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {v.affected_components.map((c, i) => (
                      <code key={i} className="text-xs bg-card border border-border rounded px-1 py-0.5 text-foreground">{c}</code>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
