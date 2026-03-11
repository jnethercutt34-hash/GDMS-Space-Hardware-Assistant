import { useState, useCallback } from 'react'
import {
  Upload, FileSpreadsheet, Download, AlertTriangle, CheckCircle,
  XCircle, Shield, ChevronDown, ChevronRight, Search, Filter,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import ModuleGuide from '../components/ModuleGuide'
import SectionLabel from '../components/SectionLabel'
import SummaryCard from '../components/SummaryCard'
import StackBar from '../components/StackBar'
import { downloadBlob } from '../lib/downloadBlob'

const RISK_COLORS = {
  Critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  High:     'bg-amber-500/20 text-amber-400 border-amber-500/30',
  Medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  Low:      'bg-green-500/20 text-green-400 border-green-500/30',
}

const LIFECYCLE_COLORS = {
  Active:   'bg-green-500/20 text-green-400 border-green-500/30',
  NRND:     'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  Obsolete: 'bg-red-500/20 text-red-400 border-red-500/30',
  Unknown:  'bg-secondary text-muted-foreground border-border',
}

const RAD_COLORS = {
  RadHard:     'bg-violet-500/20 text-violet-400 border-violet-500/30',
  RadTolerant: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  MIL:         'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  Commercial:  'bg-secondary text-muted-foreground border-border',
  Unknown:     'bg-secondary text-muted-foreground border-border',
}

export default function BomAnalyzer() {
  const [report, setReport]           = useState(null)
  const [isLoading, setIsLoading]     = useState(false)
  const [error, setError]             = useState(null)
  const [dragOver, setDragOver]       = useState(false)
  const [expanded, setExpanded]       = useState({})
  const [sortField, setSortField]     = useState('risk_level')
  const [sortAsc, setSortAsc]         = useState(false)
  const [filter, setFilter]           = useState('')

  // --- Upload ---
  const uploadFile = useCallback(async (file) => {
    if (!file) return
    setIsLoading(true)
    setError(null)
    setReport(null)
    setExpanded({})

    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch('/api/bom/analyze', { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'BOM analysis failed')
      }
      setReport(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [])

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
      const res = await fetch('/api/bom/export', {
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
      downloadBlob(blob, `bom_${format}.${ext}`)
    } catch (e) {
      setError(e.message)
    }
  }

  // --- Sorting ---
  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc)
    } else {
      setSortField(field)
      setSortAsc(false)
    }
  }

  // --- Derived data ---
  const riskOrder = { Critical: 4, High: 3, Medium: 2, Low: 1 }
  const filteredResults = report
    ? report.results
        .filter((r) => {
          if (!filter) return true
          const q = filter.toLowerCase()
          return (
            r.line_item.part_number.toLowerCase().includes(q) ||
            r.line_item.manufacturer.toLowerCase().includes(q) ||
            r.line_item.description.toLowerCase().includes(q)
          )
        })
        .sort((a, b) => {
          let va, vb
          if (sortField === 'risk_level') {
            va = riskOrder[a.risk_level] ?? 0
            vb = riskOrder[b.risk_level] ?? 0
          } else if (sortField === 'part_number') {
            va = a.line_item.part_number
            vb = b.line_item.part_number
          } else if (sortField === 'lifecycle') {
            va = a.lifecycle_status
            vb = b.lifecycle_status
          } else if (sortField === 'rad') {
            va = a.radiation_grade
            vb = b.radiation_grade
          } else if (sortField === 'qty') {
            va = a.line_item.quantity
            vb = b.line_item.quantity
          } else {
            va = a[sortField] ?? ''
            vb = b[sortField] ?? ''
          }
          if (va < vb) return sortAsc ? -1 : 1
          if (va > vb) return sortAsc ? 1 : -1
          return 0
        })
    : []

  const s = report?.summary

  return (
    <div>
      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Step 7 · BOM Analyzer
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          BOM Risk Analyzer
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Upload a Bill of Materials CSV to assess lifecycle status, radiation tolerance,
          and obsolescence risk for every part — with AI alternate suggestions and annotated export.
        </p>
      </section>

      <ModuleGuide
        title="BOM Analyzer Guide"
        purpose="This module analyzes a Bill of Materials CSV against your part library and AI knowledge to flag lifecycle risks (obsolete/NRND parts), radiation grading gaps, single-source concerns, and ITAR/EAR issues. It suggests alternate parts and exports an annotated BOM for design reviews."
        inputFormat="A CSV BOM file from Xpedition, Altium, OrCAD, or a generic export. Required columns: Part_Number (or part number variant). Optional but useful: Manufacturer, Description, Quantity, RefDes, Package."
        outputFormat="An interactive table with per-part risk levels, lifecycle status, radiation grade, library match score, and AI assessment. Exportable as an annotated CSV (with all analysis columns) or a Markdown risk summary report."
        workflow={[
          { step: 'Upload BOM CSV', description: 'Drop or select your BOM CSV. The parser auto-detects Xpedition, Altium, OrCAD, and generic column formats.' },
          { step: 'Review Dashboard', description: 'Check the summary cards and stack bar to understand your overall BOM health at a glance. High risk_count and low library match % are red flags.' },
          { step: 'Investigate Flagged Parts', description: 'Expand any row to see specific risk flags, AI assessment, and suggested alternate parts. Critical = immediate action needed.' },
          { step: 'Export Report', description: 'Download an annotated CSV to share with procurement, or the Markdown summary for a design review package.' },
        ]}
        tips={[
          'Sort by Risk Level (descending) to immediately see your most critical parts.',
          'Parts not in the library get AI assessment — this is useful but less precise than a library match.',
          'Check the rad_grade column carefully: space programs require RadHard or RadTolerant for radiation-exposed assemblies.',
          'The library match % tells you how complete your component library is. Below 50% = consider a library enrichment session.',
        ]}
        warnings={[
          'Alternate part suggestions do not guarantee form-fit-function equivalence. Always review the alternate\'s datasheet before substituting.',
          'Lifecycle status and radiation grade for unmatched parts are AI estimates based on part number patterns. Verify against DLA QPL/QML for flight hardware.',
          'ITAR/EAR flags are heuristic — consult your export control officer for formal classification.',
        ]}
      />

      {/* Error banner */}
      {error && (
        <div className="mb-6 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 flex items-center justify-between">
          <div>
            <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">Analysis Error</p>
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-muted-foreground hover:text-foreground ml-4 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Step 1 — Upload */}
      <section className="mb-14">
        <SectionLabel icon={<FileSpreadsheet className="h-4 w-4" />} step="1" label="Upload BOM CSV" />
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
              onClick={() => document.getElementById('bom-file-input').click()}
            >
              <input
                id="bom-file-input"
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileInput}
              />
              <FileSpreadsheet className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-sm text-foreground font-medium">
                {isLoading ? 'Analyzing BOM\u2026' : 'Drop a BOM CSV here or click to browse'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Supports Xpedition, Altium, OrCAD, and generic CSV formats
              </p>
            </div>
            {isLoading && (
              <p className="text-xs text-muted-foreground text-center mt-3 animate-pulse">
                Running library match, AI risk assessment\u2026 this may take 20\u201360 seconds for large BOMs.
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Step 2 — Dashboard */}
      {report && (
        <section className="mb-14">
          <SectionLabel icon={<Shield className="h-4 w-4" />} step="2" label="BOM Health Dashboard" />

          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <SummaryCard
              title="Total Parts"
              value={s.total_line_items}
              sub={`${s.total_placements} placements`}
            />
            <SummaryCard
              title="Library Match"
              value={`${s.library_matched_pct.toFixed(0)}%`}
              sub={`${s.library_matched} of ${s.unique_parts} unique`}
              warn={s.library_matched_pct < 50}
            />
            <SummaryCard
              title="High / Critical"
              value={s.risk_high + s.risk_critical}
              sub={`${s.risk_critical} critical`}
              warn={s.risk_critical > 0}
            />
            <SummaryCard
              title="Rad Hard / Tolerant"
              value={s.rad_hard + s.rad_tolerant}
              sub={`${s.rad_commercial} commercial`}
            />
          </div>

          {/* Risk distribution bar */}
          <Card className="mb-4">
            <CardHeader><CardTitle className="text-sm">Risk Distribution</CardTitle></CardHeader>
            <CardContent>
              <StackBar
                total={s.total_line_items}
                items={[
                  { label: 'Critical', count: s.risk_critical, color: 'bg-red-500' },
                  { label: 'High',     count: s.risk_high,     color: 'bg-amber-500' },
                  { label: 'Medium',   count: s.risk_medium,   color: 'bg-yellow-500' },
                  { label: 'Low',      count: s.risk_low,      color: 'bg-green-500' },
                ]}
              />
            </CardContent>
          </Card>

          {/* Lifecycle + Rad grade bars */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <Card>
              <CardHeader><CardTitle className="text-sm">Lifecycle Status</CardTitle></CardHeader>
              <CardContent>
                <StackBar
                  total={s.total_line_items}
                  items={[
                    { label: 'Active',   count: s.lifecycle_active,   color: 'bg-green-500' },
                    { label: 'NRND',     count: s.lifecycle_nrnd,     color: 'bg-yellow-500' },
                    { label: 'Obsolete', count: s.lifecycle_obsolete, color: 'bg-red-500' },
                    { label: 'Unknown',  count: s.lifecycle_unknown,  color: 'bg-secondary' },
                  ]}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-sm">Radiation Grade</CardTitle></CardHeader>
              <CardContent>
                <StackBar
                  total={s.total_line_items}
                  items={[
                    { label: 'Rad Hard',    count: s.rad_hard,       color: 'bg-violet-500' },
                    { label: 'Rad Tolerant',count: s.rad_tolerant,   color: 'bg-blue-500' },
                    { label: 'MIL',         count: s.rad_mil,        color: 'bg-cyan-500' },
                    { label: 'Commercial',  count: s.rad_commercial, color: 'bg-secondary' },
                    { label: 'Unknown',     count: s.rad_unknown,    color: 'bg-muted' },
                  ]}
                />
              </CardContent>
            </Card>
          </div>
        </section>
      )}

      {/* Step 3 — Results Table */}
      {report && (
        <section className="mb-14">
          <SectionLabel icon={<Search className="h-4 w-4" />} step="3" label="Part-by-Part Results" />

          {/* Filter + export */}
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <div className="relative flex-1 min-w-48">
              <Filter className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Filter by part number, manufacturer, description\u2026"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-transparent border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <Button size="sm" onClick={() => handleExport('csv')}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> Annotated CSV
            </Button>
            <Button size="sm" variant="outline" onClick={() => handleExport('summary')}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> Risk Report
            </Button>
          </div>

          <Card>
            <CardContent className="pt-4 px-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground uppercase tracking-widest">
                      <th className="py-2 pl-4 pr-2 text-left w-6"></th>
                      <SortHeader label="Part Number" field="part_number" current={sortField} asc={sortAsc} onSort={handleSort} />
                      <SortHeader label="Manufacturer" field="manufacturer" current={sortField} asc={sortAsc} onSort={handleSort} />
                      <SortHeader label="Qty" field="qty" current={sortField} asc={sortAsc} onSort={handleSort} align="right" />
                      <SortHeader label="Lifecycle" field="lifecycle" current={sortField} asc={sortAsc} onSort={handleSort} />
                      <SortHeader label="Rad Grade" field="rad" current={sortField} asc={sortAsc} onSort={handleSort} />
                      <th className="py-2 pr-2 text-left">Match</th>
                      <SortHeader label="Risk" field="risk_level" current={sortField} asc={sortAsc} onSort={handleSort} />
                    </tr>
                  </thead>
                  <tbody>
                    {filteredResults.map((r, i) => (
                      <ResultRow
                        key={i}
                        r={r}
                        expanded={!!expanded[i]}
                        onToggle={() => setExpanded(prev => ({ ...prev, [i]: !prev[i] }))}
                      />
                    ))}
                    {filteredResults.length === 0 && (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-muted-foreground">
                          No parts match your filter.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
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

function ResultRow({ r, expanded, onToggle }) {
  const li = r.line_item
  const hasFlags = r.risk_flags.length > 0
  const hasAlts  = r.alt_parts.length > 0
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
        {/* Part Number */}
        <td className="py-2 pr-2 font-mono text-foreground">
          {li.part_number}
          {li.dnp && <span className="ml-1 text-muted-foreground">(DNP)</span>}
        </td>
        {/* Manufacturer */}
        <td className="py-2 pr-2 text-muted-foreground">{li.manufacturer}</td>
        {/* Qty */}
        <td className="py-2 pr-2 text-right text-muted-foreground">{li.quantity}</td>
        {/* Lifecycle */}
        <td className="py-2 pr-2">
          <Badge className={`text-xs ${LIFECYCLE_COLORS[r.lifecycle_status] ?? ''}`}>
            {r.lifecycle_status}
          </Badge>
        </td>
        {/* Rad Grade */}
        <td className="py-2 pr-2">
          <Badge className={`text-xs ${RAD_COLORS[r.radiation_grade] ?? ''}`}>
            {r.radiation_grade}
          </Badge>
        </td>
        {/* Library match */}
        <td className="py-2 pr-2">
          {r.library_match
            ? <CheckCircle className="h-3.5 w-3.5 text-green-400" />
            : <XCircle className="h-3.5 w-3.5 text-muted-foreground" />
          }
        </td>
        {/* Risk level */}
        <td className="py-2 pr-4">
          <Badge className={`text-xs ${RISK_COLORS[r.risk_level] ?? ''}`}>
            {r.risk_level}
          </Badge>
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && (
        <tr className="border-b border-border bg-secondary/20">
          <td colSpan={8} className="py-3 px-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Risk flags */}
              {hasFlags && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-amber-400 mb-1">
                    Risk Flags
                  </p>
                  <ul className="space-y-0.5">
                    {r.risk_flags.map((f, i) => (
                      <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                        <AlertTriangle className="h-3 w-3 text-amber-400 shrink-0 mt-0.5" />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* AI Assessment */}
              {r.ai_assessment && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-primary mb-1">
                    AI Assessment
                  </p>
                  <p className="text-xs text-muted-foreground">{r.ai_assessment}</p>
                </div>
              )}

              {/* Alternate parts */}
              {hasAlts && (
                <div className="sm:col-span-2">
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                    Suggested Alternates
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {r.alt_parts.map((alt, i) => (
                      <div key={i} className="rounded border border-border bg-card px-2 py-1">
                        <p className="text-xs font-mono text-foreground">{alt.part_number}</p>
                        <p className="text-xs text-muted-foreground">{alt.manufacturer}</p>
                        {alt.notes && <p className="text-xs text-muted-foreground italic">{alt.notes}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Description */}
              {li.description && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                    Description
                  </p>
                  <p className="text-xs text-muted-foreground">{li.description}</p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
