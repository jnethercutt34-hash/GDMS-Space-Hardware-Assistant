import { useState, useEffect } from 'react'
import {
  Layers, Cpu, Download, ChevronRight, Save,
  CheckCircle2, AlertTriangle, Info, Plus, Trash2,
  Calculator, Zap, RefreshCw, Loader2,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import SectionLabel from '../components/SectionLabel'

const API = ''

// ─── Colors ────────────────────────────────────────────────────────────
const TYPE_COLORS = {
  Signal:                 'bg-cyan-500/30 border-cyan-500/40 text-cyan-200',
  Ground:                 'bg-emerald-500/30 border-emerald-500/40 text-emerald-200',
  Power:                  'bg-amber-500/30 border-amber-500/40 text-amber-200',
  'Mixed (Signal + Power)': 'bg-violet-500/30 border-violet-500/40 text-violet-200',
}

const SEV_ICON = {
  Requirement:    <AlertTriangle className="h-3.5 w-3.5 text-red-400 shrink-0" />,
  Recommendation: <CheckCircle2 className="h-3.5 w-3.5 text-amber-400 shrink-0" />,
  Info:           <Info className="h-3.5 w-3.5 text-blue-400 shrink-0" />,
}

const LAYER_TYPES = ['Signal', 'Ground', 'Power', 'Mixed (Signal + Power)']
const CU_WEIGHTS  = ['0.5 oz', '1 oz', '2 oz']
const MATERIALS   = [
  'FR-4 Standard (Dk≈4.2, Df≈0.02)',
  'FR-4 Mid-Loss (Dk≈3.8, Df≈0.012)',
  'Megtron-6 (Dk≈3.4, Df≈0.004)',
  'I-Tera MT40 (Dk≈3.45, Df≈0.005)',
  'Nelco N4000-13SI (Dk≈3.5, Df≈0.008)',
  'Rogers 4350B (Dk≈3.48, Df≈0.004)',
  'Polyimide (Dk≈3.5, Df≈0.008)',
  'Custom',
]

// ═══════════════════════════════════════════════════════════════════════
// Layer visual strip
// ═══════════════════════════════════════════════════════════════════════
function LayerStrip({ layer, onChange, onDelete, idx, total }) {
  const colors = TYPE_COLORS[layer.layer_type] || TYPE_COLORS.Signal

  return (
    <div className="group flex items-stretch gap-0 rounded-md overflow-hidden border border-border hover:border-muted-foreground/30 transition-colors">
      {/* Color bar */}
      <div className={`w-2 shrink-0 ${colors.split(' ')[0]}`} />

      {/* Content */}
      <div className="flex-1 px-3 py-2 bg-card flex items-center gap-3 flex-wrap">
        {/* Order */}
        <span className="text-[10px] text-muted-foreground font-mono w-5 shrink-0">L{layer.order}</span>

        {/* Name */}
        <input
          value={layer.name}
          onChange={e => onChange({ ...layer, name: e.target.value })}
          className="bg-transparent border-none text-xs text-foreground font-medium w-40 focus:outline-none focus:ring-0"
        />

        {/* Type */}
        <select
          value={layer.layer_type}
          onChange={e => onChange({ ...layer, layer_type: e.target.value })}
          className="bg-secondary/50 border border-border rounded px-1.5 py-0.5 text-[10px] text-foreground"
        >
          {LAYER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        {/* Copper weight */}
        <select
          value={layer.copper_weight}
          onChange={e => onChange({ ...layer, copper_weight: e.target.value })}
          className="bg-secondary/50 border border-border rounded px-1.5 py-0.5 text-[10px] text-foreground"
        >
          {CU_WEIGHTS.map(w => <option key={w} value={w}>{w}</option>)}
        </select>

        {/* Dielectric thickness */}
        <div className="flex items-center gap-1">
          <input
            type="number"
            value={layer.dielectric_thickness_mil}
            onChange={e => onChange({ ...layer, dielectric_thickness_mil: +e.target.value })}
            className="bg-secondary/50 border border-border rounded px-1.5 py-0.5 text-[10px] text-foreground w-14"
            min={0.5} max={40} step={0.5}
          />
          <span className="text-[10px] text-muted-foreground">mil</span>
        </div>

        {/* Notes */}
        <input
          value={layer.notes || ''}
          onChange={e => onChange({ ...layer, notes: e.target.value })}
          placeholder="Notes"
          className="flex-1 bg-transparent border-none text-[10px] text-muted-foreground focus:outline-none focus:ring-0 min-w-[100px]"
        />

        {/* Delete */}
        <button
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-red-400 p-1"
          title="Remove layer"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════
// Cross-section visual
// ═══════════════════════════════════════════════════════════════════════
function StackupCrossSection({ layers }) {
  if (!layers?.length) return null
  const barColors = {
    Signal: 'bg-cyan-500/50',
    Ground: 'bg-emerald-500/50',
    Power:  'bg-amber-500/50',
    'Mixed (Signal + Power)': 'bg-violet-500/50',
  }

  return (
    <div className="flex flex-col items-center gap-0 w-full max-w-md mx-auto">
      {layers.map((l, i) => (
        <div key={l.id || i}>
          <div className="w-full flex items-center gap-2">
            {/* Copper bar */}
            <div className={`h-2 flex-1 ${barColors[l.layer_type] || barColors.Signal} rounded-sm`}
                 title={l.name} />
            <span className="text-[9px] text-muted-foreground w-28 truncate">{l.name}</span>
          </div>
          {/* Dielectric spacer between layers */}
          {i < layers.length - 1 && (
            <div className="w-full flex items-center gap-2 my-0.5">
              <div className="h-1 flex-1 bg-muted-foreground/10 rounded-sm" title={`Dielectric ${l.dielectric_thickness_mil || 4} mil`} />
              <span className="text-[8px] text-muted-foreground/40 w-28 truncate">{l.dielectric_thickness_mil || 4} mil</span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════
// Main page
// ═══════════════════════════════════════════════════════════════════════
export default function StackupDesigner() {
  // Architecture analysis
  const [diagrams, setDiagrams]             = useState([])
  const [selectedDiagram, setSelectedDiagram] = useState('')
  const [manualInterfaces, setManualInterfaces] = useState([])
  const [analysis, setAnalysis]             = useState(null)

  // Stackup editing
  const [templates, setTemplates]           = useState([])
  const [layers, setLayers]                 = useState([])
  const [stackupName, setStackupName]       = useState('Untitled Stackup')
  const [boardMaterial, setBoardMaterial]    = useState(MATERIALS[0])
  const [impTargets, setImpTargets]         = useState([])
  const [stackupId, setStackupId]           = useState(null)
  const [savedStackups, setSavedStackups]   = useState([])

  // Impedance calculator
  const [impCalc, setImpCalc] = useState({
    trace_width_mil: 5, dielectric_height_mil: 4, dk: 4.2,
    copper_oz: 1, trace_spacing_mil: 5, calc_type: 'microstrip',
  })
  const [impResult, setImpResult] = useState(null)

  // Loading & error states
  const [loading, setLoading] = useState({})
  const [error, setError]     = useState(null)

  // Available interfaces for manual selection
  const INTERFACE_OPTIONS = [
    'DDR4', 'DDR5', 'PCIe_Gen3', 'PCIe_Gen4', 'PCIe_Gen5',
    'USB3', 'Ethernet_10G', 'LVDS', 'SpaceWire', 'SpaceFibre',
    'MIL-STD-1553', 'SPI', 'I2C',
  ]

  // Load diagrams, templates, saved stackups on mount
  useEffect(() => {
    fetch(`${API}/api/diagrams`).then(r => r.json()).then(setDiagrams).catch(() => {})
    fetch(`${API}/api/stackup/templates`).then(r => r.json()).then(d => setTemplates(d.templates || [])).catch(() => {})
    fetch(`${API}/api/stackups`).then(r => r.json()).then(setSavedStackups).catch(() => {})
  }, [])

  // ── Architecture Analysis ─────────────────────────────────
  const runAnalysis = async () => {
    setLoading(p => ({ ...p, analyze: true }))
    try {
      const res = await fetch(`${API}/api/stackup/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diagram_id: selectedDiagram || null,
          interfaces: manualInterfaces,
        }),
      })
      const data = await res.json()
      setAnalysis(data)
      // Auto-set impedance targets from analysis
      if (data.impedance_targets?.length) setImpTargets(data.impedance_targets)
    } catch (e) { setError(e.message) }
    setLoading(p => ({ ...p, analyze: false }))
  }

  // ── Load template ─────────────────────────────────────────
  const loadTemplate = async (lc) => {
    setLoading(p => ({ ...p, template: true }))
    try {
      const res = await fetch(`${API}/api/stackup/template/${lc}`)
      const data = await res.json()
      setLayers(data.layers || [])
      setStackupName(data.name || `${lc}-Layer Stackup`)
      setStackupId(data.id)
    } catch (e) { setError(e.message) }
    setLoading(p => ({ ...p, template: false }))
  }

  // ── Layer editing ─────────────────────────────────────────
  const updateLayer = (idx, updated) => {
    setLayers(prev => prev.map((l, i) => i === idx ? updated : l))
  }
  const deleteLayer = (idx) => {
    setLayers(prev => {
      const next = prev.filter((_, i) => i !== idx)
      return next.map((l, i) => ({ ...l, order: i + 1 }))
    })
  }
  const addLayer = () => {
    const order = layers.length + 1
    setLayers(prev => [...prev, {
      id: crypto.randomUUID().slice(0, 8),
      order,
      name: `L${order} — New Layer`,
      layer_type: 'Signal',
      copper_weight: '1 oz',
      dielectric_thickness_mil: 4.0,
      dielectric_material: MATERIALS[0],
      notes: '',
    }])
  }

  // ── Save stackup ──────────────────────────────────────────
  const saveCurrentStackup = async () => {
    setLoading(p => ({ ...p, save: true }))
    const payload = {
      id: stackupId || crypto.randomUUID().slice(0, 8),
      name: stackupName,
      layer_count: layers.length,
      layers,
      impedance_targets: impTargets,
      board_material: boardMaterial,
      total_thickness_mil: layers.reduce((sum, l) => {
        const cu = { '0.5 oz': 0.7, '1 oz': 1.37, '2 oz': 2.74 }
        return sum + (cu[l.copper_weight] || 1.37) + (l.dielectric_thickness_mil || 4)
      }, 0).toFixed(1),
      diagram_id: selectedDiagram || null,
    }
    try {
      const res = await fetch(`${API}/api/stackups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const saved = await res.json()
      setStackupId(saved.id)
      // Refresh list
      const list = await fetch(`${API}/api/stackups`).then(r => r.json())
      setSavedStackups(list)
    } catch (e) { setError(e.message) }
    setLoading(p => ({ ...p, save: false }))
  }

  // ── Load saved stackup ────────────────────────────────────
  const loadSavedStackup = async (id) => {
    try {
      const res = await fetch(`${API}/api/stackups/${id}`)
      const data = await res.json()
      setLayers(data.layers || [])
      setStackupName(data.name || 'Loaded Stackup')
      setStackupId(data.id)
      setBoardMaterial(data.board_material || MATERIALS[0])
      setImpTargets(data.impedance_targets || [])
    } catch (e) { setError(e.message) }
  }

  // ── Export ────────────────────────────────────────────────
  const exportStackup = async () => {
    if (!stackupId) {
      await saveCurrentStackup()
    }
    const id = stackupId || 'temp'
    try {
      const res = await fetch(`${API}/api/stackup/export/${id}`, { method: 'POST' })
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `stackup_${id}.md`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) { setError(e.message) }
  }

  // ── Impedance calc ────────────────────────────────────────
  const calcImpedance = async () => {
    try {
      const res = await fetch(`${API}/api/stackup/impedance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(impCalc),
      })
      setImpResult(await res.json())
    } catch (e) { setError(e.message) }
  }

  // Toggle interface for manual selection
  const toggleIface = (iface) => {
    setManualInterfaces(prev =>
      prev.includes(iface) ? prev.filter(x => x !== iface) : [...prev, iface]
    )
  }

  // Computed total thickness
  const totalThickness = layers.reduce((sum, l) => {
    const cu = { '0.5 oz': 0.7, '1 oz': 1.37, '2 oz': 2.74 }
    return sum + (cu[l.copper_weight] || 1.37) + (l.dielectric_thickness_mil || 4)
  }, 0).toFixed(1)

  const signalCount = layers.filter(l => l.layer_type === 'Signal' || l.layer_type === 'Mixed (Signal + Power)').length
  const groundCount = layers.filter(l => l.layer_type === 'Ground').length
  const powerCount  = layers.filter(l => l.layer_type === 'Power').length

  return (
    <div>
      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Stackup Designer
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          PCB Stackup Designer
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Design your PCB layer stackup informed by your system architecture.
          Select interfaces or link a block diagram, get layer-count and material recommendations,
          then customize layers, estimate impedances, and export fab-ready documentation.
        </p>
      </section>

      {/* Error banner */}
      {error && (
        <div className="mb-6 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 flex items-center justify-between">
          <div>
            <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">Error</p>
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-muted-foreground hover:text-foreground ml-4 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* ── Step 1: Architecture Context ── */}
      <section className="mb-14">
        <SectionLabel icon={<Cpu className="h-4 w-4" />} step="1" label="Architecture Context" />
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground mb-4">
              Link a block diagram or select interfaces manually. The analyzer will suggest layer count, material, and impedance targets.
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-4">
              {/* Diagram selector */}
              <div>
                <label className="block text-[10px] text-muted-foreground mb-1.5 uppercase tracking-wider">
                  Block Diagram (optional)
                </label>
                <select
                  value={selectedDiagram}
                  onChange={e => setSelectedDiagram(e.target.value)}
                  className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground"
                >
                  <option value="">— No diagram selected —</option>
                  {diagrams.map(d => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.block_count} blocks, {d.connection_count} connections)
                    </option>
                  ))}
                </select>
              </div>

              {/* Manual interface selection */}
              <div>
                <label className="block text-[10px] text-muted-foreground mb-1.5 uppercase tracking-wider">
                  Interfaces on this board
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {INTERFACE_OPTIONS.map(iface => {
                    const on = manualInterfaces.includes(iface)
                    return (
                      <button
                        key={iface}
                        onClick={() => toggleIface(iface)}
                        className={[
                          'text-[10px] px-2 py-1 rounded-md border transition-colors',
                          on ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-muted-foreground/40',
                        ].join(' ')}
                      >
                        {iface}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>

            <Button size="sm" onClick={runAnalysis} disabled={loading.analyze}>
              {loading.analyze
                ? <><Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> Analyzing…</>
                : <><Zap className="mr-1.5 h-3.5 w-3.5" /> Analyze Architecture</>
              }
            </Button>

            {/* Analysis results */}
            {analysis && (
              <div className="mt-6 space-y-3">
                {/* Detected interfaces */}
                {analysis.interfaces_detected?.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Detected:</span>
                    {analysis.interfaces_detected.map(i => (
                      <Badge key={i} variant="outline" className="text-[10px] border-primary/30 text-primary">{i}</Badge>
                    ))}
                  </div>
                )}

                {/* Recommendations */}
                <div className="space-y-2">
                  {analysis.suggestions?.map((sug, i) => (
                    <div key={i} className="flex items-start gap-2.5 rounded-md border border-border bg-secondary/20 px-3 py-2">
                      {SEV_ICON[sug.severity] || SEV_ICON.Info}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-[10px] font-semibold text-foreground uppercase tracking-wider">{sug.category}</span>
                          {sug.related_interface && (
                            <Badge variant="outline" className="text-[9px] border-border text-muted-foreground">{sug.related_interface}</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">{sug.message}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Quick-load recommended template */}
                {analysis.recommended_layer_count > 0 && (
                  <Button size="sm" variant="outline" onClick={() => loadTemplate(analysis.recommended_layer_count)}>
                    <Layers className="mr-1.5 h-3.5 w-3.5" />
                    Load {analysis.recommended_layer_count}-Layer Template
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ── Step 2: Stackup Editor ── */}
      <section className="mb-14">
        <SectionLabel icon={<Layers className="h-4 w-4" />} step="2" label="Layer Stackup" />

        {/* Template picker + meta row */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <div>
            <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Start from Template</label>
            <div className="flex gap-1.5">
              {templates.map(t => (
                <button
                  key={t.layer_count}
                  onClick={() => loadTemplate(t.layer_count)}
                  className="text-[10px] px-2 py-1 rounded-md border border-border text-muted-foreground hover:border-primary/30 hover:text-primary transition-colors"
                  title={t.description}
                >
                  {t.layer_count}L
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1" />
          <div>
            <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Stackup Name</label>
            <input
              value={stackupName}
              onChange={e => setStackupName(e.target.value)}
              className="rounded-md border border-border bg-secondary/50 px-2 py-1 text-xs text-foreground w-48"
            />
          </div>
          <div>
            <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Board Material</label>
            <select
              value={boardMaterial}
              onChange={e => setBoardMaterial(e.target.value)}
              className="rounded-md border border-border bg-secondary/50 px-2 py-1 text-xs text-foreground w-56"
            >
              {MATERIALS.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </div>

        <Card>
          <CardContent className="pt-4 pb-3">
            {layers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-12">
                Select a template above or add layers manually to get started.
              </p>
            ) : (
              <>
                {/* Stats bar */}
                <div className="flex items-center gap-4 mb-3 text-[10px] text-muted-foreground">
                  <span><strong className="text-foreground">{layers.length}</strong> layers</span>
                  <span><strong className="text-cyan-300">{signalCount}</strong> signal</span>
                  <span><strong className="text-emerald-300">{groundCount}</strong> ground</span>
                  <span><strong className="text-amber-300">{powerCount}</strong> power</span>
                  <span>Total thickness: <strong className="text-foreground">{totalThickness} mil</strong></span>
                </div>

                {/* Layer list */}
                <div className="space-y-1">
                  {layers.map((layer, idx) => (
                    <LayerStrip
                      key={layer.id || idx}
                      layer={layer}
                      idx={idx}
                      total={layers.length}
                      onChange={updated => updateLayer(idx, updated)}
                      onDelete={() => deleteLayer(idx)}
                    />
                  ))}
                </div>
              </>
            )}

            {/* Add layer + actions */}
            <div className="mt-3 flex items-center gap-3">
              <Button size="sm" variant="outline" onClick={addLayer}>
                <Plus className="mr-1.5 h-3.5 w-3.5" /> Add Layer
              </Button>
              {layers.length > 0 && (
                <>
                  <Button size="sm" onClick={saveCurrentStackup} disabled={loading.save}>
                    <Save className="mr-1.5 h-3.5 w-3.5" />
                    {loading.save ? 'Saving…' : 'Save Stackup'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={exportStackup}>
                    <Download className="mr-1.5 h-3.5 w-3.5" /> Export Markdown
                  </Button>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Cross-section visual */}
        {layers.length > 0 && (
          <Card className="mt-4">
            <CardContent className="py-4">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-3 text-center">Cross-Section View</p>
              <StackupCrossSection layers={layers} />
              <div className="flex justify-center gap-4 mt-3 text-[9px] text-muted-foreground">
                <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-cyan-500/50 inline-block" /> Signal</span>
                <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-emerald-500/50 inline-block" /> Ground</span>
                <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-amber-500/50 inline-block" /> Power</span>
                <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-violet-500/50 inline-block" /> Mixed</span>
              </div>
            </CardContent>
          </Card>
        )}
      </section>

      {/* ── Step 3: Impedance Targets ── */}
      {(impTargets.length > 0 || layers.length > 0) && (
        <section className="mb-14">
          <SectionLabel icon={<Zap className="h-4 w-4" />} step="3" label="Impedance Targets" />
          <Card>
            <CardContent className="pt-4 pb-3">
              {impTargets.length > 0 ? (
                <table className="w-full text-xs mb-4">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="text-left py-2 px-2 font-medium">Interface</th>
                      <th className="text-left py-2 px-2 font-medium">Type</th>
                      <th className="text-left py-2 px-2 font-medium">Target (Ω)</th>
                      <th className="text-left py-2 px-2 font-medium">Tolerance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {impTargets.map((t, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="py-2 px-2 text-foreground">{t.interface}</td>
                        <td className="py-2 px-2 text-muted-foreground">{t.impedance_type}</td>
                        <td className="py-2 px-2 font-semibold text-foreground">{t.target_ohms}</td>
                        <td className="py-2 px-2 text-muted-foreground">±{t.tolerance_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-xs text-muted-foreground mb-4">
                  Run architecture analysis to auto-populate impedance targets, or use the calculator below.
                </p>
              )}

              {/* Impedance calculator */}
              <div className="rounded-lg border border-border bg-secondary/20 px-4 py-3">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <Calculator className="h-3 w-3" /> Impedance Calculator
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
                  <div>
                    <label className="block text-[10px] text-muted-foreground mb-1">Type</label>
                    <select
                      value={impCalc.calc_type}
                      onChange={e => setImpCalc(p => ({ ...p, calc_type: e.target.value }))}
                      className="w-full rounded border border-border bg-secondary/50 px-1.5 py-1 text-[10px] text-foreground"
                    >
                      <option value="microstrip">Microstrip</option>
                      <option value="stripline">Stripline</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] text-muted-foreground mb-1">Trace W (mil)</label>
                    <input type="number" value={impCalc.trace_width_mil}
                      onChange={e => setImpCalc(p => ({ ...p, trace_width_mil: +e.target.value }))}
                      className="w-full rounded border border-border bg-secondary/50 px-1.5 py-1 text-[10px] text-foreground"
                      min={1} max={50} step={0.5} />
                  </div>
                  <div>
                    <label className="block text-[10px] text-muted-foreground mb-1">Diel. H (mil)</label>
                    <input type="number" value={impCalc.dielectric_height_mil}
                      onChange={e => setImpCalc(p => ({ ...p, dielectric_height_mil: +e.target.value }))}
                      className="w-full rounded border border-border bg-secondary/50 px-1.5 py-1 text-[10px] text-foreground"
                      min={0.5} max={40} step={0.5} />
                  </div>
                  <div>
                    <label className="block text-[10px] text-muted-foreground mb-1">Dk</label>
                    <input type="number" value={impCalc.dk}
                      onChange={e => setImpCalc(p => ({ ...p, dk: +e.target.value }))}
                      className="w-full rounded border border-border bg-secondary/50 px-1.5 py-1 text-[10px] text-foreground"
                      min={2} max={12} step={0.1} />
                  </div>
                  <div>
                    <label className="block text-[10px] text-muted-foreground mb-1">Cu (oz)</label>
                    <input type="number" value={impCalc.copper_oz}
                      onChange={e => setImpCalc(p => ({ ...p, copper_oz: +e.target.value }))}
                      className="w-full rounded border border-border bg-secondary/50 px-1.5 py-1 text-[10px] text-foreground"
                      min={0.5} max={3} step={0.5} />
                  </div>
                  <div>
                    <label className="block text-[10px] text-muted-foreground mb-1">Spacing (mil)</label>
                    <input type="number" value={impCalc.trace_spacing_mil}
                      onChange={e => setImpCalc(p => ({ ...p, trace_spacing_mil: +e.target.value }))}
                      className="w-full rounded border border-border bg-secondary/50 px-1.5 py-1 text-[10px] text-foreground"
                      min={1} max={50} step={0.5} />
                  </div>
                  <div className="flex items-end">
                    <Button size="sm" className="w-full" onClick={calcImpedance}>
                      <Calculator className="mr-1 h-3 w-3" /> Calc
                    </Button>
                  </div>
                </div>

                {impResult && (
                  <div className="mt-3 flex items-center gap-6 text-xs">
                    <div>
                      <span className="text-muted-foreground">SE:</span>{' '}
                      <span className="font-semibold text-foreground">{impResult.single_ended_ohms} Ω</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Diff:</span>{' '}
                      <span className="font-semibold text-foreground">{impResult.differential_ohms} Ω</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">
                      ({impResult.calc_type}, W={impResult.trace_width_mil} mil, H={impResult.dielectric_height_mil} mil, Dk={impResult.dk})
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      {/* ── Saved Stackups ── */}
      {savedStackups.length > 0 && (
        <section className="mb-14">
          <SectionLabel icon={<RefreshCw className="h-4 w-4" />} label="Saved Stackups" />
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="space-y-1">
                {savedStackups.map(s => (
                  <button
                    key={s.id}
                    onClick={() => loadSavedStackup(s.id)}
                    className={[
                      'w-full text-left flex items-center justify-between rounded-md border px-3 py-2 transition-colors text-xs',
                      s.id === stackupId
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:border-muted-foreground/30',
                    ].join(' ')}
                  >
                    <span className="font-medium text-foreground">{s.name}</span>
                    <span>{s.layer_count} layers</span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  )
}
