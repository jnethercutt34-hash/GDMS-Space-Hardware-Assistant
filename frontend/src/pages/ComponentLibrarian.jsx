import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload, Cpu, CheckCircle, Search, Library, Package,
  FileSpreadsheet, AlertTriangle, FileText,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import UploadZone from '../components/UploadZone'
import DataTable from '../components/DataTable'
import SectionLabel from '../components/SectionLabel'

export default function ComponentLibrarian() {
  const [extractedData, setExtractedData] = useState(null)
  const [isLoading, setIsLoading]         = useState(false)
  const [error, setError]                 = useState(null)

  const [pushResult, setPushResult] = useState(null)
  const [isPushing, setIsPushing]   = useState(false)
  const [pushError, setPushError]   = useState(null)

  const [libraryParts, setLibraryParts]   = useState([])
  const [searchQuery, setSearchQuery]     = useState('')
  const [isSearching, setIsSearching]     = useState(false)

  // BOM import
  const [bomResult, setBomResult]       = useState(null)
  const [isBomLoading, setIsBomLoading] = useState(false)
  const [bomError, setBomError]         = useState(null)
  const [bomDragOver, setBomDragOver]   = useState(false)

  // Load library on mount
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

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => fetchLibrary(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery, fetchLibrary])

  const handleUpload = async (file) => {
    setIsLoading(true)
    setError(null)
    setExtractedData(null)
    setPushResult(null)
    setPushError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/upload-datasheet', { method: 'POST', body: formData })
      if (!res.ok) {
        const text = await res.text()
        let detail = 'Upload failed'
        try { detail = JSON.parse(text).detail || detail } catch { detail = text || detail }
        throw new Error(detail)
      }
      const data = await res.json()
      setExtractedData(data)
      // Refresh library to show newly added parts
      fetchLibrary(searchQuery)
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handlePushToXpedition = async () => {
    if (!extractedData?.rows?.length) return
    setIsPushing(true)
    setPushResult(null)
    setPushError(null)

    try {
      const res = await fetch('/api/push-to-databook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: extractedData.rows }),
      })
      if (!res.ok) {
        const text = await res.text()
        let detail = 'Push failed'
        try { detail = JSON.parse(text).detail || detail } catch { detail = text || detail }
        throw new Error(detail)
      }
      setPushResult(await res.json())
    } catch (e) {
      setPushError(e.message)
    } finally {
      setIsPushing(false)
    }
  }

  // Update a part's program in local state after PATCH succeeds
  const handleProgramChange = (partNumber, program) => {
    setLibraryParts(prev =>
      prev.map(p => p.Part_Number === partNumber ? { ...p, Program: program } : p)
    )
  }

  // BOM import handler
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
      const data = await res.json()
      setBomResult(data)
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

  const hasRows = Boolean(extractedData?.rows?.length)

  return (
    <div>
      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Component Librarian
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Component Datasheet Extractor
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Upload a PDF datasheet for AI parameter extraction, or import an Xpedition BOM CSV to
          bulk-add ICs to the library. Every part is saved to the searchable library below.
        </p>
      </section>

      {/* Step 1 — Upload */}
      <section className="mb-14">
        <SectionLabel icon={<Upload className="h-4 w-4" />} step="1" label="Upload Component Datasheet (PDF)" />
        <Card>
          <CardContent className="pt-6">
            <UploadZone onUpload={handleUpload} isLoading={isLoading} />
            {error && (
              <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">
                  Upload Error
                </p>
                <p className="text-xs text-muted-foreground">{error}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* BOM Import */}
      <section className="mb-14">
        <SectionLabel icon={<FileSpreadsheet className="h-4 w-4" />} step="" label="Import from BOM CSV" />
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground mb-3">
              Upload an Xpedition BOM CSV to bulk-add ICs and active devices to the library.
              Passives (R, C, L, ferrites, test points) are automatically skipped.
              Parts already in the library are left untouched.
            </p>
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
              <input
                id="bom-import-input"
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleBomFileInput}
              />
              <FileSpreadsheet className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-sm text-foreground font-medium">
                {isBomLoading ? 'Importing BOM…' : 'Drop a BOM CSV here or click to browse'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Supports Xpedition, Altium, OrCAD, and generic CSV formats
              </p>
            </div>
            {isBomLoading && (
              <p className="text-xs text-muted-foreground text-center mt-3 animate-pulse">
                Parsing BOM and filtering ICs…
              </p>
            )}
            {bomError && (
              <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">
                  Import Error
                </p>
                <p className="text-xs text-muted-foreground">{bomError}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* BOM Import Results */}
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
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest">Added to Library</p>
                </div>
                <div className="rounded-md bg-secondary/30 px-3 py-2 text-center">
                  <p className="text-lg font-bold text-muted-foreground">{bomResult.already_in_library}</p>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest">Already Existed</p>
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                <span className="text-muted-foreground/60">{bomResult.passives_skipped} passives skipped.</span>
                {bomResult.added_to_library > 0 && (
                  <span className="ml-1">
                    New parts are marked <span className="text-amber-400 font-medium">Needs Datasheet</span> — 
                    click into each part and upload its PDF datasheet to populate engineering parameters.
                  </span>
                )}
              </p>
            </CardContent>
          </Card>
        )}
      </section>

      {/* Step 2 — Extracted Parameters */}
      {extractedData && (
        <section className="mb-14">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel icon={<Cpu className="h-4 w-4" />} step="2" label="Extracted Parameters" />
            <Button
              onClick={handlePushToXpedition}
              disabled={!hasRows || isPushing}
            >
              {isPushing ? 'Pushing…' : 'Push to Xpedition Databook →'}
            </Button>
          </div>
          <Card>
            <CardContent className="pt-6">
              <DataTable data={extractedData} />
            </CardContent>
          </Card>
          {pushError && (
            <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
              <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">
                Push Error
              </p>
              <p className="text-xs text-muted-foreground">{pushError}</p>
            </div>
          )}
        </section>
      )}

      {/* Step 3 — Push Results */}
      {pushResult && (
        <section className="mb-14">
          <SectionLabel icon={<CheckCircle className="h-4 w-4" />} step="3" label="Xpedition Databook Push Results" />
          <Card>
            <CardContent className="pt-6">
              <PushResultPanel results={pushResult.results} />
            </CardContent>
          </Card>
        </section>
      )}

      {/* Part Library */}
      <section className="mb-14">
        <div className="flex items-center justify-between mb-3">
          <SectionLabel icon={<Library className="h-4 w-4" />} step="" label="Part Library" />
          <span className="text-xs text-muted-foreground">
            {libraryParts.length} part{libraryParts.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Search bar */}
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            placeholder="Search by part number, manufacturer, program, package…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-md border border-border bg-secondary/30 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring focus:border-ring transition-colors"
          />
        </div>

        {/* Results */}
        {isSearching ? (
          <p className="text-sm text-muted-foreground">Searching…</p>
        ) : libraryParts.length === 0 ? (
          <div className="rounded-lg border border-border bg-secondary/10 px-6 py-12 text-center">
            <Package className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              {searchQuery.trim()
                ? 'No parts match your search.'
                : 'No parts in the library yet — upload a datasheet to get started.'}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {libraryParts.map((part) => (
              <PartCard key={part.Part_Number} part={part} onProgramChange={handleProgramChange} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function PartCard({ part, onProgramChange }) {
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft]     = useState(part.Program ?? '')
  const [saving, setSaving]   = useState(false)

  const specs = [
    { label: 'Package',   value: part.Package_Type    ?? '—' },
    { label: 'Pins',      value: part.Pin_Count        ?? '—' },
    { label: 'Voltage',   value: part.Voltage_Rating   ?? '—' },
    { label: 'Value',     value: part.Value            ?? '—' },
    { label: 'Tolerance', value: part.Tolerance        ?? '—' },
    { label: 'θja',       value: part.Thermal_Resistance ?? '—' },
  ].filter((s) => s.value !== '—')

  const handleSaveProgram = async () => {
    setSaving(true)
    try {
      const res = await fetch(`/api/library/${encodeURIComponent(part.Part_Number)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ Program: draft.trim() || null }),
      })
      if (res.ok) {
        onProgramChange?.(part.Part_Number, draft.trim() || null)
        setEditing(false)
      }
    } finally {
      setSaving(false)
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
        {part.needs_datasheet && (
          <div className="flex items-center gap-1.5 pt-1.5">
            <AlertTriangle className="h-3 w-3 text-amber-400 shrink-0" />
            <span className="text-[10px] text-amber-400 font-medium uppercase tracking-wider">Needs Datasheet</span>
          </div>
        )}
      </CardHeader>

      {specs.length > 0 && (
        <CardContent className="pt-0 flex-1">
          <div className="grid grid-cols-3 gap-2 text-center">
            {specs.slice(0, 6).map(({ label, value }) => (
              <div key={label} className="rounded-md bg-secondary/30 px-2 py-1.5">
                <p className="text-xs text-muted-foreground uppercase tracking-widest leading-none mb-1">
                  {label}
                </p>
                <p className="text-xs font-semibold text-foreground font-mono truncate">{value}</p>
              </div>
            ))}
          </div>
        </CardContent>
      )}

      {/* Program assignment */}
      <div className="px-6 pb-3 pt-1" onClick={e => e.stopPropagation()}>
        {editing ? (
          <div className="flex gap-1.5 items-center">
            <input
              className="flex-1 rounded-md border border-border bg-secondary px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Program name…"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') handleSaveProgram()
                if (e.key === 'Escape') { setEditing(false); setDraft(part.Program ?? '') }
              }}
              autoFocus
              disabled={saving}
            />
            <Button size="sm" className="h-6 px-2 text-[10px]" onClick={handleSaveProgram} disabled={saving}>
              {saving ? '…' : 'Save'}
            </Button>
            <button
              className="text-xs text-muted-foreground hover:text-foreground"
              onClick={() => { setEditing(false); setDraft(part.Program ?? '') }}
            >
              ✕
            </button>
          </div>
        ) : (
          <button
            className="w-full text-left group"
            onClick={() => setEditing(true)}
          >
            <p className="text-xs text-muted-foreground/60 uppercase tracking-widest leading-none mb-0.5">Program</p>
            <p className="text-xs text-foreground group-hover:text-primary transition-colors">
              {part.Program || <span className="text-muted-foreground/40 italic">Click to assign…</span>}
            </p>
          </button>
        )}
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

function PushResultPanel({ results }) {
  return (
    <div className="space-y-3">
      {results.map((r, i) => {
        const isSuccess = r.status === 'success'
        return (
          <div
            key={i}
            className={[
              'rounded-md border px-4 py-3 flex items-start gap-3',
              isSuccess
                ? 'border-emerald-500/20 bg-emerald-500/5'
                : 'border-amber-500/20 bg-amber-500/5',
            ].join(' ')}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-semibold text-foreground">{r.Part_Number}</span>
                <span
                  className={[
                    'text-xs font-mono px-1.5 py-0.5 rounded border',
                    isSuccess
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/20',
                  ].join(' ')}
                >
                  {r.status}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{r.message}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
