import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Upload, FileText, AlertTriangle, Cpu, Package,
  Thermometer, Radiation, Zap, Box, Hash, Gauge, Shield, Clipboard,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'

// ---------------------------------------------------------------------------
// Field definitions — grouped by engineering concern
// ---------------------------------------------------------------------------

const IDENTITY_FIELDS = [
  { key: 'Part_Number',    label: 'Part Number',    icon: Hash },
  { key: 'Manufacturer',   label: 'Manufacturer',   icon: Package },
  { key: 'Program',        label: 'Program',        icon: Clipboard },
]

const ELECTRICAL_FIELDS = [
  { key: 'Value',           label: 'Value',           icon: Zap },
  { key: 'Tolerance',       label: 'Tolerance',       icon: Gauge },
  { key: 'Voltage_Rating',  label: 'Voltage Rating',  icon: Zap },
]

const PHYSICAL_FIELDS = [
  { key: 'Package_Type',           label: 'Package',              icon: Box },
  { key: 'Pin_Count',              label: 'Pin Count',            icon: Hash },
  { key: 'Operating_Temperature_Range', label: 'Temp Range',      icon: Thermometer },
  { key: 'Thermal_Resistance',     label: 'Thermal Resistance',   icon: Thermometer },
]

const RADIATION_FIELDS = [
  { key: 'Radiation_TID',           label: 'TID Rating',           icon: Radiation },
  { key: 'Radiation_SEL_Threshold', label: 'SEL Threshold',        icon: Shield },
  { key: 'Radiation_SEU_Rate',      label: 'SEU Rate',             icon: Shield },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hasDatasheet(part) {
  // A part "has datasheet data" if it has more than just identity fields populated
  const dataFields = [
    'Value', 'Tolerance', 'Voltage_Rating', 'Package_Type', 'Pin_Count',
    'Operating_Temperature_Range', 'Thermal_Resistance', 'Summary',
    'Radiation_TID', 'Radiation_SEL_Threshold', 'Radiation_SEU_Rate',
  ]
  return dataFields.some(f => part[f] != null && part[f] !== '')
}

function dataCoverage(part) {
  const allFields = [
    ...ELECTRICAL_FIELDS, ...PHYSICAL_FIELDS, ...RADIATION_FIELDS,
  ]
  const filled = allFields.filter(f => part[f.key] != null && part[f.key] !== '')
  return { filled: filled.length, total: allFields.length }
}

// ---------------------------------------------------------------------------
// Field table section
// ---------------------------------------------------------------------------

function FieldSection({ title, icon: Icon, fields, part }) {
  const hasAny = fields.some(f => part[f.key] != null && part[f.key] !== '')
  return (
    <div>
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest flex items-center gap-2 mb-3">
        <Icon className="h-3.5 w-3.5" /> {title}
      </h3>
      <div className="grid gap-2">
        {fields.map(f => {
          const val = part[f.key]
          const filled = val != null && val !== ''
          return (
            <div
              key={f.key}
              className={`flex items-center justify-between rounded-md px-3 py-2 ${
                filled ? 'bg-secondary/40' : 'bg-secondary/10'
              }`}
            >
              <div className="flex items-center gap-2">
                <f.icon className={`h-3.5 w-3.5 ${filled ? 'text-primary' : 'text-muted-foreground/30'}`} />
                <span className="text-xs text-muted-foreground">{f.label}</span>
              </div>
              <span className={`text-xs font-mono ${filled ? 'text-foreground font-semibold' : 'text-muted-foreground/30 italic'}`}>
                {filled ? val : '—'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PartDetail() {
  const { partNumber } = useParams()
  const navigate = useNavigate()

  const [part, setPart]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState(null)

  // Program editing
  const [editingProgram, setEditingProgram] = useState(false)
  const [programDraft, setProgramDraft]     = useState('')
  const [savingProgram, setSavingProgram]   = useState(false)

  const fetchPart = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/library/${encodeURIComponent(partNumber)}`)
      if (res.status === 404) {
        setError('Part not found in library.')
        setPart(null)
        return
      }
      if (!res.ok) throw new Error('Failed to load part')
      const data = await res.json()
      setPart(data)
      setProgramDraft(data.Program ?? '')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [partNumber])

  useEffect(() => { fetchPart() }, [fetchPart])

  // Upload datasheet for this part
  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadMsg(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch('/api/upload-datasheet', { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }
      const data = await res.json()
      const matchedCount = (data.rows || []).filter(
        r => r.Part_Number?.toUpperCase() === partNumber.toUpperCase()
      ).length
      setUploadMsg(
        matchedCount > 0
          ? `✅ Datasheet processed — ${matchedCount} matching part(s) updated.`
          : `⚠️ Datasheet processed (${data.rows?.length || 0} parts found) but none matched "${partNumber}". The extracted parts were still saved to the library.`
      )
      // Refresh part data
      fetchPart()
    } catch (e) {
      setUploadMsg(`❌ ${e.message}`)
    } finally {
      setUploading(false)
    }
  }

  // Save program
  const handleSaveProgram = async () => {
    setSavingProgram(true)
    try {
      const res = await fetch(`/api/library/${encodeURIComponent(partNumber)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ Program: programDraft.trim() || null }),
      })
      if (res.ok) {
        setPart(prev => ({ ...prev, Program: programDraft.trim() || null }))
        setEditingProgram(false)
      }
    } finally {
      setSavingProgram(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="text-sm text-muted-foreground animate-pulse">Loading part data…</p>
      </div>
    )
  }

  if (error || !part) {
    return (
      <div className="py-20 text-center">
        <Package className="h-12 w-12 mx-auto mb-4 text-muted-foreground/30" />
        <h2 className="text-lg font-semibold text-foreground mb-1">Part Not Found</h2>
        <p className="text-sm text-muted-foreground mb-6">{error || `"${partNumber}" is not in the library.`}</p>
        <Button variant="outline" onClick={() => navigate('/librarian')}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Library
        </Button>
      </div>
    )
  }

  const hasDsData = hasDatasheet(part)
  const coverage = dataCoverage(part)

  return (
    <div>
      {/* Back nav */}
      <button
        onClick={() => navigate('/librarian')}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-6"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to Library
      </button>

      {/* Header */}
      <section className="mb-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              {part.Part_Number}
            </h1>
            <p className="mt-1 text-lg text-muted-foreground">{part.Manufacturer}</p>
            {part.Summary && (
              <p className="mt-3 max-w-2xl text-sm text-muted-foreground leading-relaxed">{part.Summary}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            {part.Program ? (
              <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                {part.Program}
              </Badge>
            ) : (
              <Badge className="bg-secondary text-muted-foreground border-border">
                No program assigned
              </Badge>
            )}
            {hasDsData ? (
              <Badge className="bg-primary/20 text-primary border-primary/30">
                <FileText className="mr-1 h-3 w-3" /> Datasheet on file
              </Badge>
            ) : (
              <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30">
                <AlertTriangle className="mr-1 h-3 w-3" /> No datasheet data
              </Badge>
            )}
          </div>
        </div>
      </section>

      {/* No-datasheet callout */}
      {!hasDsData && (
        <Card className="mb-8 border-amber-500/30 bg-amber-500/5">
          <CardContent className="py-6 flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-amber-400 flex items-center gap-2 mb-1">
                <AlertTriangle className="h-4 w-4" /> Datasheet Required
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                This part has no extracted datasheet parameters. Upload the manufacturer PDF
                datasheet to populate electrical specs, package info, radiation data, and more.
              </p>
            </div>
            <label className="shrink-0">
              <input type="file" accept=".pdf" className="hidden" onChange={handleUpload} disabled={uploading} />
              <Button size="sm" asChild disabled={uploading}>
                <span>
                  <Upload className="mr-1.5 h-3.5 w-3.5" />
                  {uploading ? 'Processing…' : 'Upload Datasheet'}
                </span>
              </Button>
            </label>
          </CardContent>
        </Card>
      )}

      {/* Upload message */}
      {uploadMsg && (
        <div className="mb-6 rounded-md border border-border bg-secondary/30 px-3 py-2 text-xs text-muted-foreground">
          {uploadMsg}
        </div>
      )}

      {/* Data coverage bar */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-muted-foreground">Data coverage</span>
          <span className="text-xs font-mono text-foreground">{coverage.filled}/{coverage.total} fields</span>
        </div>
        <div className="h-2 rounded-full bg-secondary/40 overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${(coverage.filled / coverage.total) * 100}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-14">
        {/* Left column — identity + program */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Cpu className="h-4 w-4 text-primary" /> Identity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {IDENTITY_FIELDS.map(f => {
                const val = part[f.key]
                const isProgram = f.key === 'Program'
                return (
                  <div key={f.key}>
                    <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-0.5">{f.label}</p>
                    {isProgram && editingProgram ? (
                      <div className="flex gap-1.5 items-center">
                        <input
                          className="flex-1 rounded-md border border-border bg-secondary px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                          placeholder="Program name…"
                          value={programDraft}
                          onChange={e => setProgramDraft(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') handleSaveProgram()
                            if (e.key === 'Escape') { setEditingProgram(false); setProgramDraft(part.Program ?? '') }
                          }}
                          autoFocus
                          disabled={savingProgram}
                        />
                        <Button size="sm" className="h-6 px-2 text-[10px]" onClick={handleSaveProgram} disabled={savingProgram}>
                          Save
                        </Button>
                        <button
                          className="text-xs text-muted-foreground hover:text-foreground"
                          onClick={() => { setEditingProgram(false); setProgramDraft(part.Program ?? '') }}
                        >✕</button>
                      </div>
                    ) : isProgram ? (
                      <button className="group text-left" onClick={() => setEditingProgram(true)}>
                        <p className="text-sm text-foreground group-hover:text-primary transition-colors">
                          {val || <span className="text-muted-foreground/40 italic text-xs">Click to assign…</span>}
                        </p>
                      </button>
                    ) : (
                      <p className="text-sm font-semibold text-foreground font-mono">{val || '—'}</p>
                    )}
                  </div>
                )
              })}

              {part.source_file && (
                <div>
                  <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-0.5">Source File</p>
                  <p className="text-xs text-muted-foreground truncate">{part.source_file}</p>
                </div>
              )}
              {part.added_at && (
                <div>
                  <p className="text-[10px] text-muted-foreground/60 uppercase tracking-widest mb-0.5">Added</p>
                  <p className="text-xs text-muted-foreground">{new Date(part.added_at).toLocaleDateString()}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Upload datasheet (always visible) */}
          {hasDsData && (
            <Card>
              <CardContent className="py-4">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input type="file" accept=".pdf" className="hidden" onChange={handleUpload} disabled={uploading} />
                  <Upload className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                  <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                    {uploading ? 'Processing…' : 'Re-upload datasheet to update fields'}
                  </span>
                </label>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right columns — engineering data */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Engineering Parameters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-8">
              <FieldSection title="Electrical" icon={Zap} fields={ELECTRICAL_FIELDS} part={part} />
              <FieldSection title="Physical / Thermal" icon={Box} fields={PHYSICAL_FIELDS} part={part} />
              <FieldSection title="Radiation Hardness" icon={Shield} fields={RADIATION_FIELDS} part={part} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
