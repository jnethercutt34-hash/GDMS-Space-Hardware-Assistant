import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload, Cpu, CheckCircle, Search, Library, Package,
  FileSpreadsheet, AlertTriangle, Plus, X, Check, Loader2, FileText,
  ChevronDown,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import UploadZone from '../components/UploadZone'
import SectionLabel from '../components/SectionLabel'

// ─── Queue status constants ──────────────────────────────────────────────────
const Q_PENDING  = 'pending'
const Q_RUNNING  = 'running'
const Q_DONE     = 'done'
const Q_ERROR    = 'error'

// ─── Dropdown option lists ────────────────────────────────────────────────────
const PROGRAM_OPTIONS = [
  'Program A',
  'Program B',
  'Program C',
  'Program D',
  'Program E',
  'Program F',
]

const PART_TYPE_OPTIONS = [
  'Power',
  'FPGA',
  'Processor',
  'DDR4',
  'DDR5',
  'ADC',
  'DAC',
  'SerDes',
  'Transceiver',
  'Oscillator / Clock',
  'Voltage Regulator',
  'Op-Amp',
  'MOSFET',
  'Diode',
  'Connector',
  'Memory (Flash)',
  'Memory (SRAM)',
  'Memory (EEPROM)',
  'Gate Driver',
  'Interface (LVDS)',
  'Interface (SpaceWire)',
  'Interface (RS-422)',
  'Multiplexer',
  'Sensor',
  'Filter',
  'Transformer',
  'Other',
]

export default function ComponentLibrarian() {
  // ── Library state ────────────────────────────────────────────────────────
  const [libraryParts, setLibraryParts]   = useState([])
  const [searchQuery, setSearchQuery]     = useState('')
  const [isSearching, setIsSearching]     = useState(false)

  // ── Upload queue ─────────────────────────────────────────────────────────
  // Each item: { id, file, status, result, error }
  const [queue, setQueue] = useState([])
  const processingRef = useRef(false)

  // ── Staging area (extracted but not yet accepted) ────────────────────────
  // Each item: { id, filename, storedFilename, consolidated, rows, warnings, accepted }
  // Persisted to localStorage so pending reviews survive browser refresh.
  const STAGING_KEY = 'gdms_staged_parts'
  const [staged, setStaged] = useState(() => {
    try {
      const saved = localStorage.getItem(STAGING_KEY)
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })

  useEffect(() => {
    try { localStorage.setItem(STAGING_KEY, JSON.stringify(staged)) }
    catch { /* quota exceeded — ignore */ }
  }, [staged])

  // ── BOM import ───────────────────────────────────────────────────────────
  const [bomResult, setBomResult]       = useState(null)
  const [isBomLoading, setIsBomLoading] = useState(false)
  const [bomError, setBomError]         = useState(null)
  const [bomDragOver, setBomDragOver]   = useState(false)

  // ── Library fetching ─────────────────────────────────────────────────────
  const fetchLibrary = useCallback(async (query = '') => {
    setIsSearching(true)
    try {
      const url = query.trim()
        ? `/api/library/search?q=${encodeURIComponent(query.trim())}`
        : '/api/library'
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setLibraryParts(data.parts ?? [])
      }
    } finally {
      setIsSearching(false)
    }
  }, [])

  useEffect(() => { fetchLibrary() }, [fetchLibrary])

  useEffect(() => {
    const timer = setTimeout(() => fetchLibrary(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery, fetchLibrary])

  // ── Queue processing ─────────────────────────────────────────────────────
  const processQueue = useCallback(async (items) => {
    if (processingRef.current) return
    processingRef.current = true

    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.status !== Q_PENDING) continue

      // Mark running
      setQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: Q_RUNNING } : q))

      try {
        const formData = new FormData()
        formData.append('file', item.file)
        const res = await fetch('/api/upload-datasheet', { method: 'POST', body: formData })
        if (!res.ok) {
          const text = await res.text()
          let detail = 'Upload failed'
          try { detail = JSON.parse(text).detail || detail } catch { detail = text || detail }
          throw new Error(detail)
        }
        const data = await res.json()

        // Mark done
        setQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: Q_DONE, result: data } : q))

        // Add to staging if parts were found
        if (data.consolidated || data.rows?.length) {
          setStaged(prev => [...prev, {
            id: item.id,
            filename: data.filename,
            storedFilename: data.stored_filename,
            consolidated: data.consolidated,
            rows: data.rows,
            warnings: data.warnings,
            accepted: null, // null = pending review
          }])
        }
      } catch (e) {
        setQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: Q_ERROR, error: e.message } : q))
      }
    }

    processingRef.current = false
  }, [])

  const handleMultiUpload = useCallback((files) => {
    const newItems = files.map((file, i) => ({
      id: `${Date.now()}-${i}`,
      file,
      status: Q_PENDING,
      result: null,
      error: null,
    }))
    setQueue(prev => {
      const updated = [...prev, ...newItems]
      // Kick off processing after state update
      setTimeout(() => processQueue(updated), 0)
      return updated
    })
  }, [processQueue])

  // ── Accept / Reject ──────────────────────────────────────────────────────
  const handleAccept = async (stagedItem) => {
    const parts = stagedItem.consolidated
      ? [stagedItem.consolidated]
      : stagedItem.rows

    try {
      const res = await fetch('/api/library/accept-parts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          parts: stagedItem.rows,
          source_file: stagedItem.filename,
          datasheet_file: stagedItem.storedFilename,
        }),
      })
      if (!res.ok) throw new Error('Failed to accept parts')

      setStaged(prev => prev.map(s => s.id === stagedItem.id ? { ...s, accepted: true } : s))
      fetchLibrary(searchQuery)
    } catch (e) {
      console.error('Accept failed:', e)
    }
  }

  const handleReject = (stagedItem) => {
    setStaged(prev => prev.map(s => s.id === stagedItem.id ? { ...s, accepted: false } : s))
  }

  const clearCompleted = () => {
    setQueue(prev => prev.filter(q => q.status === Q_PENDING || q.status === Q_RUNNING))
    setStaged(prev => prev.filter(s => s.accepted === null))
  }

  // ── Filter state ──────────────────────────────────────────────────────────
  const [filterProgram, setFilterProgram]   = useState('')
  const [filterPartType, setFilterPartType] = useState('')

  // ── Field change (inline on card) ──────────────────────────────────────
  const handleFieldChange = (partNumber, field, value) => {
    setLibraryParts(prev =>
      prev.map(p => p.Part_Number === partNumber ? { ...p, [field]: value } : p)
    )
  }
  // Back-compat alias
  const handleProgramChange = (partNumber, program) => handleFieldChange(partNumber, 'Program', program)

  // ── BOM import ───────────────────────────────────────────────────────────
  const handleBomImport = async (file) => {
    if (!file) return
    setIsBomLoading(true)
    setBomError(null)
    setBomResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch('/api/library/import-bom', { method: 'POST', body: formData })
      if (!res.ok) {
        const text = await res.text()
        let detail = 'BOM import failed'
        try { detail = JSON.parse(text).detail || detail } catch { detail = text || detail }
        throw new Error(detail)
      }
      setBomResult(await res.json())
      fetchLibrary(searchQuery)
    } catch (e) {
      setBomError(e.message)
    } finally {
      setIsBomLoading(false)
    }
  }

  const handleBomFileInput = (e) => handleBomImport(e.target.files?.[0])
  const handleBomDrop = (e) => {
    e.preventDefault()
    setBomDragOver(false)
    handleBomImport(e.dataTransfer.files?.[0])
  }

  // ── Derived state ────────────────────────────────────────────────────────
  const isProcessing = queue.some(q => q.status === Q_RUNNING)
  const pendingReview = staged.filter(s => s.accepted === null)
  const hasCompletedItems = staged.some(s => s.accepted !== null) || queue.some(q => q.status === Q_ERROR)

  return (
    <div>
      {/* ================================================================
          HERO
          ================================================================ */}
      <section className="mb-10">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Component Librarian
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Component Library
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Browse and search the local parts library. Use the import tools below to add new
          components from PDF datasheets or Xpedition BOM exports.
        </p>
      </section>

      {/* ================================================================
          PART LIBRARY
          ================================================================ */}
      <section className="mb-14">
        <div className="flex items-center justify-between mb-3">
          <SectionLabel icon={<Library className="h-4 w-4" />} step="" label="Part Library" />
          <span className="text-xs text-muted-foreground">
            {libraryParts.length} part{libraryParts.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="flex flex-col gap-3 mb-6">
          {/* Search bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <input
              type="text"
              placeholder="Search by part number, manufacturer, program, package…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 rounded-md border border-border bg-secondary/30 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring focus:border-ring transition-colors"
            />
          </div>

          {/* Filter dropdowns */}
          <div className="flex gap-3">
            <div className="relative">
              <select
                value={filterProgram}
                onChange={(e) => setFilterProgram(e.target.value)}
                className="appearance-none rounded-md border border-border bg-secondary/30 pl-3 pr-8 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring focus:border-ring transition-colors cursor-pointer"
              >
                <option value="">All Programs</option>
                {PROGRAM_OPTIONS.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            </div>

            <div className="relative">
              <select
                value={filterPartType}
                onChange={(e) => setFilterPartType(e.target.value)}
                className="appearance-none rounded-md border border-border bg-secondary/30 pl-3 pr-8 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring focus:border-ring transition-colors cursor-pointer"
              >
                <option value="">All Part Types</option>
                {PART_TYPE_OPTIONS.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            </div>

            {(filterProgram || filterPartType) && (
              <button
                onClick={() => { setFilterProgram(''); setFilterPartType('') }}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2"
              >
                Clear filters
              </button>
            )}
          </div>
        </div>

        {(() => {
          const filtered = libraryParts.filter(p => {
            if (filterProgram && p.Program !== filterProgram) return false
            if (filterPartType && p.Part_Type !== filterPartType) return false
            return true
          })
          if (isSearching) return <p className="text-sm text-muted-foreground">Searching…</p>
          if (filtered.length === 0) return (
            <div className="rounded-lg border border-border bg-secondary/10 px-6 py-12 text-center">
              <Package className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {(searchQuery.trim() || filterProgram || filterPartType)
                  ? 'No parts match your search / filters.'
                  : 'No parts in the library yet — use the import tools below to add components.'}
              </p>
            </div>
          )
          return (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((part) => (
                <PartCard key={part.Part_Number} part={part} onFieldChange={handleFieldChange} />
              ))}
            </div>
          )
        })()}
      </section>

      {/* ================================================================
          REVIEW STAGING — pending accept/reject
          ================================================================ */}
      {(pendingReview.length > 0 || hasCompletedItems) && (
        <section className="mb-14">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel icon={<Cpu className="h-4 w-4" />} step="" label="Review Extracted Parts" />
            {hasCompletedItems && (
              <button
                onClick={clearCompleted}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Clear completed
              </button>
            )}
          </div>

          <div className="space-y-4">
            {staged.map((item) => (
              <StagedPartCard
                key={item.id}
                item={item}
                onAccept={() => handleAccept(item)}
                onReject={() => handleReject(item)}
              />
            ))}
          </div>
        </section>
      )}

      {/* ================================================================
          ADD PARTS — upload + BOM side by side
          ================================================================ */}
      <section className="mb-14">
        <SectionLabel icon={<Plus className="h-4 w-4" />} step="" label="Add Parts to Library" />

        <div className="grid gap-6 md:grid-cols-2">
          {/* PDF Upload */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Upload className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm font-heading">Upload PDF Datasheets</CardTitle>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed pt-1">
                Drop one or more PDF datasheets. Each is processed by AI to extract component
                parameters. You'll review and accept parts before they're added to the library.
              </p>
            </CardHeader>
            <CardContent>
              <UploadZone onUpload={handleMultiUpload} isLoading={isProcessing} multiple />

              {/* Queue progress */}
              {queue.length > 0 && (
                <div className="mt-4 space-y-2">
                  {queue.map((item) => (
                    <div key={item.id} className="flex items-center gap-3 rounded-md bg-secondary/20 px-3 py-2">
                      {item.status === Q_PENDING && (
                        <div className="h-3 w-3 rounded-full bg-muted-foreground/30 shrink-0" />
                      )}
                      {item.status === Q_RUNNING && (
                        <Loader2 className="h-3 w-3 text-primary animate-spin shrink-0" />
                      )}
                      {item.status === Q_DONE && (
                        <CheckCircle className="h-3 w-3 text-emerald-400 shrink-0" />
                      )}
                      {item.status === Q_ERROR && (
                        <X className="h-3 w-3 text-destructive shrink-0" />
                      )}
                      <span className="text-xs text-foreground truncate flex-1">{item.file.name}</span>
                      {item.status === Q_RUNNING && (
                        <span className="text-[10px] text-primary animate-pulse">Processing…</span>
                      )}
                      {item.status === Q_DONE && item.result && (
                        <span className="text-[10px] text-emerald-400">
                          {item.result.rows?.length || 0} part{(item.result.rows?.length || 0) !== 1 ? 's' : ''}
                        </span>
                      )}
                      {item.status === Q_ERROR && (
                        <span className="text-[10px] text-destructive truncate max-w-[200px]">{item.error}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* BOM Import */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm font-heading">Import from BOM CSV</CardTitle>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed pt-1">
                Bulk-add ICs and active devices from an Xpedition BOM export.
                Passives are automatically skipped.
              </p>
            </CardHeader>
            <CardContent>
              <div
                onDragOver={(e) => { e.preventDefault(); setBomDragOver(true) }}
                onDragLeave={() => setBomDragOver(false)}
                onDrop={handleBomDrop}
                className={[
                  'border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer',
                  bomDragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50',
                ].join(' ')}
                onClick={() => document.getElementById('bom-import-input').click()}
              >
                <input id="bom-import-input" type="file" accept=".csv" className="hidden" onChange={handleBomFileInput} />
                <FileSpreadsheet className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-foreground font-medium">
                  {isBomLoading ? 'Importing BOM…' : 'Drop a BOM CSV here or click to browse'}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Supports Xpedition, Altium, OrCAD, and generic CSV formats
                </p>
              </div>
              {isBomLoading && (
                <p className="text-xs text-muted-foreground text-center mt-3 animate-pulse">Parsing BOM and filtering ICs…</p>
              )}
              {bomError && (
                <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                  <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">Import Error</p>
                  <p className="text-xs text-muted-foreground">{bomError}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* BOM Results */}
        {bomResult && (
          <Card className="mt-4">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3 mb-4">
                <CheckCircle className="h-5 w-5 text-green-400 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-foreground">BOM Import Complete</p>
                  <p className="text-xs text-muted-foreground">{bomResult.filename}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div className="rounded-md bg-secondary/30 px-3 py-2 text-center">
                  <p className="text-lg font-bold text-foreground">{bomResult.total_bom_lines}</p>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest">BOM Lines</p>
                </div>
                <div className="rounded-md bg-secondary/30 px-3 py-2 text-center">
                  <p className="text-lg font-bold text-foreground">{bomResult.ic_candidates}</p>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest">ICs Found</p>
                </div>
                <div className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-center">
                  <p className="text-lg font-bold text-emerald-400">{bomResult.added_to_library}</p>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest">Added</p>
                </div>
                <div className="rounded-md bg-secondary/30 px-3 py-2 text-center">
                  <p className="text-lg font-bold text-muted-foreground">{bomResult.already_in_library}</p>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest">Existed</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                <span className="text-muted-foreground/60">{bomResult.passives_skipped} passives skipped.</span>
                {bomResult.added_to_library > 0 && (
                  <span className="ml-1">
                    New parts marked <span className="text-amber-400 font-medium">Needs Datasheet</span>.
                  </span>
                )}
              </p>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// Staged Part Card — accept / reject before committing to library
// ─────────────────────────────────────────────────────────────────────────────

function StagedPartCard({ item, onAccept, onReject }) {
  const c = item.consolidated
  const primaryPN = c?.Part_Number || item.rows?.[0]?.Part_Number || 'Unknown'
  const manufacturer = c?.Manufacturer || item.rows?.[0]?.Manufacturer || '—'
  const summary = c?.Summary || item.rows?.[0]?.Summary || null
  const variants = c?.variants || []
  const warnings = item.warnings || []

  if (item.accepted === true) {
    return (
      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardContent className="py-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-semibold text-foreground font-mono">{primaryPN}</span>
            <span className="text-xs text-muted-foreground ml-2">— accepted, added to library</span>
          </div>
          <span className="text-xs text-muted-foreground">{item.filename}</span>
        </CardContent>
      </Card>
    )
  }

  if (item.accepted === false) {
    return (
      <Card className="border-border/50 bg-secondary/10 opacity-50">
        <CardContent className="py-4 flex items-center gap-3">
          <X className="h-5 w-5 text-muted-foreground shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-semibold text-foreground font-mono">{primaryPN}</span>
            <span className="text-xs text-muted-foreground ml-2">— rejected</span>
          </div>
          <span className="text-xs text-muted-foreground">{item.filename}</span>
        </CardContent>
      </Card>
    )
  }

  // Pending review
  return (
    <Card className="border-amber-500/30 bg-amber-500/5">
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-bold text-foreground font-mono">{primaryPN}</span>
              <span className="text-xs text-muted-foreground">{manufacturer}</span>
              {variants.length > 0 && (
                <span className="text-[10px] text-muted-foreground bg-secondary/50 rounded px-1.5 py-0.5">
                  +{variants.length} variant{variants.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            {summary && (
              <p className="text-xs text-muted-foreground leading-relaxed">{summary}</p>
            )}
            <p className="text-[10px] text-muted-foreground/60 mt-1">
              Source: {item.filename}
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button size="sm" className="h-7 px-3 text-xs bg-emerald-600 hover:bg-emerald-700" onClick={onAccept}>
              <Check className="h-3 w-3 mr-1" /> Accept
            </Button>
            <Button size="sm" variant="outline" className="h-7 px-3 text-xs" onClick={onReject}>
              <X className="h-3 w-3 mr-1" /> Reject
            </Button>
          </div>
        </div>

        {/* Quick specs preview */}
        {c && (
          <div className="flex flex-wrap gap-2 mb-2">
            {c.Package_Type && (
              <span className="text-[10px] rounded bg-secondary/40 px-1.5 py-0.5 text-muted-foreground">
                {c.Package_Type}
              </span>
            )}
            {c.Pin_Count && (
              <span className="text-[10px] rounded bg-secondary/40 px-1.5 py-0.5 text-muted-foreground">
                {c.Pin_Count}-pin
              </span>
            )}
            {c.Voltage_Rating && (
              <span className="text-[10px] rounded bg-secondary/40 px-1.5 py-0.5 text-muted-foreground">
                {c.Voltage_Rating}
              </span>
            )}
            {c.Radiation_TID && (
              <span className="text-[10px] rounded bg-secondary/40 px-1.5 py-0.5 text-muted-foreground">
                TID: {c.Radiation_TID}
              </span>
            )}
            {c.Operating_Temperature_Range && (
              <span className="text-[10px] rounded bg-secondary/40 px-1.5 py-0.5 text-muted-foreground">
                {c.Operating_Temperature_Range}
              </span>
            )}
          </div>
        )}

        {/* Variant list */}
        {variants.length > 0 && (
          <div className="mt-2 pt-2 border-t border-amber-500/10">
            <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-1">Variants</p>
            <div className="flex flex-wrap gap-1.5">
              {variants.map(v => (
                <span key={v.Part_Number} className="text-[10px] font-mono text-muted-foreground bg-secondary/30 rounded px-1.5 py-0.5">
                  {v.Part_Number}
                  {v.Package_Type && <span className="text-muted-foreground/60"> · {v.Package_Type}</span>}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="mt-2 pt-2 border-t border-amber-500/10">
            {warnings.map((w, i) => (
              <p key={i} className="text-[10px] text-amber-400/80 flex items-start gap-1.5">
                <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" /> {w}
              </p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// Part Card (library grid)
// ─────────────────────────────────────────────────────────────────────────────

function PartCard({ part, onFieldChange }) {
  const navigate = useNavigate()
  const [savingField, setSavingField] = useState(null) // 'Program' | 'Part_Type' | null

  const specs = [
    { label: 'Package',   value: part.Package_Type    ?? '—' },
    { label: 'Pins',      value: part.Pin_Count        ?? '—' },
    { label: 'Voltage',   value: part.Voltage_Rating   ?? '—' },
    { label: 'Value',     value: part.Value            ?? '—' },
    { label: 'Tolerance', value: part.Tolerance        ?? '—' },
    { label: 'θja',       value: part.Thermal_Resistance ?? '—' },
  ].filter((s) => s.value !== '—')

  const handleDropdownChange = async (field, value) => {
    const newValue = value || null
    setSavingField(field)
    try {
      const res = await fetch(`/api/library/${encodeURIComponent(part.Part_Number)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: newValue }),
      })
      if (res.ok) {
        onFieldChange?.(part.Part_Number, field, newValue)
      }
    } finally {
      setSavingField(null)
    }
  }

  return (
    <Card
      className="flex flex-col cursor-pointer hover:border-primary/40 transition-colors"
      onClick={() => navigate(`/part/${encodeURIComponent(part.Part_Number)}`)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="font-heading text-sm leading-snug">{part.Part_Number}</CardTitle>
          <span className="inline-block rounded border border-border bg-secondary/50 px-1.5 py-0.5 text-xs text-muted-foreground whitespace-nowrap shrink-0">
            {part.Manufacturer}
          </span>
        </div>
        {part.Summary && (
          <p className="text-xs text-muted-foreground leading-relaxed pt-1">{part.Summary}</p>
        )}
        {part.variants?.length > 0 && (
          <div className="flex items-center gap-1.5 pt-1.5">
            <Package className="h-3 w-3 text-primary shrink-0" />
            <span className="text-[10px] text-muted-foreground font-medium">
              +{part.variants.length} variant{part.variants.length !== 1 ? 's' : ''}
            </span>
          </div>
        )}
        {part.needs_datasheet && (
          <div className="flex items-center gap-1.5 pt-1.5">
            <AlertTriangle className="h-3 w-3 text-amber-400 shrink-0" />
            <span className="text-[10px] text-amber-400 font-medium uppercase tracking-wider">Needs Datasheet</span>
          </div>
        )}
        {part.datasheet_file && (
          <div className="flex items-center gap-1.5 pt-1.5">
            <FileText className="h-3 w-3 text-emerald-400 shrink-0" />
            <span className="text-[10px] text-emerald-400 font-medium">PDF on file</span>
          </div>
        )}
      </CardHeader>

      {specs.length > 0 && (
        <CardContent className="pt-0 flex-1">
          <div className="grid grid-cols-3 gap-2 text-center">
            {specs.slice(0, 6).map(({ label, value }) => (
              <div key={label} className="rounded-md bg-secondary/30 px-2 py-1.5">
                <p className="text-xs text-muted-foreground uppercase tracking-widest leading-none mb-1">{label}</p>
                <p className="text-xs font-semibold text-foreground font-mono truncate">{value}</p>
              </div>
            ))}
          </div>
        </CardContent>
      )}

      {/* Program & Part Type dropdowns */}
      <div className="px-6 pb-3 pt-1 space-y-2" onClick={e => e.stopPropagation()}>
        {/* Program dropdown */}
        <div>
          <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest leading-none mb-1">Program</p>
          <div className="relative">
            <select
              value={part.Program || ''}
              onChange={(e) => handleDropdownChange('Program', e.target.value)}
              disabled={savingField === 'Program'}
              className="w-full appearance-none rounded-md border border-border bg-secondary/30 pl-2.5 pr-7 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring focus:border-ring transition-colors cursor-pointer disabled:opacity-50"
            >
              <option value="">— Select program —</option>
              {PROGRAM_OPTIONS.map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
          </div>
        </div>

        {/* Part Type dropdown */}
        <div>
          <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest leading-none mb-1">Part Type</p>
          <div className="relative">
            <select
              value={part.Part_Type || ''}
              onChange={(e) => handleDropdownChange('Part_Type', e.target.value)}
              disabled={savingField === 'Part_Type'}
              className="w-full appearance-none rounded-md border border-border bg-secondary/30 pl-2.5 pr-7 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring focus:border-ring transition-colors cursor-pointer disabled:opacity-50"
            >
              <option value="">— Select part type —</option>
              {PART_TYPE_OPTIONS.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
          </div>
        </div>
      </div>

      {part.source_file && (
        <div className="px-6 pb-4 pt-0">
          <p className="text-xs text-muted-foreground truncate">
            <span className="text-muted-foreground/60">Source:</span> {part.source_file}
          </p>
        </div>
      )}
    </Card>
  )
}
