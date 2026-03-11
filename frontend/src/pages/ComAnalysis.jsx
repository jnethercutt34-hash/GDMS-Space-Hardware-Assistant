import { useState } from 'react'
import {
  Upload, Activity, Download, Plus, Trash2,
  ChevronDown, AlertTriangle, CheckCircle, XCircle,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import UploadZone from '../components/UploadZone'
import ModuleGuide from '../components/ModuleGuide'
import SectionLabel from '../components/SectionLabel'
import { downloadBlob } from '../lib/downloadBlob'

const SEGMENT_TYPES = ['PCB_trace', 'connector', 'via', 'cable', 'package']
const MODULATIONS   = ['NRZ', 'PAM4']

const DEFAULT_SEGMENT = {
  label: '', type: 'PCB_trace', length_mm: 50, impedance_ohm: 100,
  loss_db_per_inch: 0.5, dielectric_constant: 4.0, loss_tangent: 0.02,
}

const DEFAULT_CHANNEL = {
  name: 'New Channel',
  data_rate_gbps: 10,
  modulation: 'NRZ',
  segments: [
    { ...DEFAULT_SEGMENT, label: 'TX_pkg', type: 'package', length_mm: 5, loss_db_per_inch: 0.8 },
    { ...DEFAULT_SEGMENT, label: 'PCB_trace', type: 'PCB_trace', length_mm: 100 },
    { ...DEFAULT_SEGMENT, label: 'RX_pkg', type: 'package', length_mm: 5, loss_db_per_inch: 0.8 },
  ],
  tx_params: { swing_mv: 800, de_emphasis_db: 3.5, pre_cursor_taps: 1 },
  rx_params: { ctle_peaking_db: 6.0, dfe_taps: 1, dfe_tap1_mv: 50 },
  crosstalk_aggressors: [],
}

export default function ComAnalysis() {
  const [channel, setChannel]           = useState(DEFAULT_CHANNEL)
  const [comResult, setComResult]       = useState(null)
  const [isLoading, setIsLoading]       = useState(false)
  const [isExtracting, setIsExtracting] = useState(false)
  const [error, setError]               = useState(null)

  // --- Channel builder helpers ---
  const updateChannel = (updates) => setChannel(prev => ({ ...prev, ...updates }))

  const updateSegment = (i, updates) => {
    const segs = [...channel.segments]
    segs[i] = { ...segs[i], ...updates }
    updateChannel({ segments: segs })
  }

  const addSegment = () => {
    updateChannel({
      segments: [
        ...channel.segments,
        { ...DEFAULT_SEGMENT, label: `Seg_${channel.segments.length + 1}` },
      ],
    })
  }

  const removeSegment = (i) => {
    updateChannel({ segments: channel.segments.filter((_, idx) => idx !== i) })
  }

  const updateTx = (updates) => updateChannel({ tx_params: { ...channel.tx_params, ...updates } })
  const updateRx = (updates) => updateChannel({ rx_params: { ...channel.rx_params, ...updates } })

  // --- AI Extract ---
  const handleExtract = async (file) => {
    setIsExtracting(true)
    setError(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch('/api/com/extract-channel', { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Extraction failed')
      }
      const data = await res.json()
      setChannel(data.channel)
      setComResult(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setIsExtracting(false)
    }
  }

  // --- Calculate COM ---
  const handleCalculate = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/com/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Calculation failed')
      }
      const data = await res.json()
      setComResult(data.result)
      setChannel(data.channel)
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  // --- Export ---
  const handleExport = async (format) => {
    if (!comResult) return
    try {
      const res = await fetch('/api/com/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, result: comResult, format }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Export failed')
      }
      const blob = await res.blob()
      const ext = { ces: 'py', hyperlynx: 'csv', summary: 'md' }[format] || 'txt'
      downloadBlob(blob, `com_${format}.${ext}`)
    } catch (e) {
      setError(e.message)
    }
  }

  // --- COM badge color ---
  const comBadge = (com) => {
    if (com >= 3) return 'bg-green-500/20 text-green-400 border-green-500/30'
    if (com >= 1) return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
    return 'bg-red-500/20 text-red-400 border-red-500/30'
  }

  return (
    <div>
      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Phase 5 · COM Channel Analysis
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Channel Operating Margin
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Model high-speed serial link channels, compute estimated COM per IEEE 802.3,
          and export constraints for Xpedition CES and HyperLynx.
        </p>
      </section>

      <ModuleGuide
        title="COM Channel Analysis Guide"
        purpose="Channel Operating Margin (COM) is the IEEE 802.3 standard metric for determining whether a high-speed serial link will work reliably. This module lets you model a complete TX-to-RX channel — including PCB traces, connectors, vias, cables, and packages — and computes an estimated COM value. A COM ≥ 3 dB generally means the link passes."
        inputFormat="Either manually build the channel using the segment table, or upload a datasheet/stackup report PDF to let AI auto-populate the channel parameters."
        outputFormat="COM value (dB) with pass/fail assessment, eye height/width metrics, per-segment loss breakdown, and warnings. Exportable as Markdown summary, CES Python script, or HyperLynx CSV."
        workflow={[
          { step: 'AI Extract (Optional)', description: 'Upload a transceiver datasheet or PCB stackup report. AI extracts TX/RX parameters and channel loss characteristics.' },
          { step: 'Build or Refine the Channel', description: 'Set data rate and modulation. Define each segment in the TX→RX path with impedance, loss per inch, Dk, and Df.' },
          { step: 'Configure TX/RX Parameters', description: 'Set transmitter swing, de-emphasis, and pre-cursor taps. Set receiver CTLE peaking and DFE configuration.' },
          { step: 'Calculate COM', description: 'Click "Calculate COM". Review COM value, eye metrics, and per-segment loss breakdown. COM ≥ 3 dB = pass.' },
          { step: 'Export Results', description: 'Download summary report, CES constraint script, or HyperLynx CSV.' },
        ]}
        tips={[
          'Start with AI extract if you have a transceiver datasheet — saves significant parameter entry time.',
          'Get loss_db_per_inch and Dk/Df from your PCB fab stackup report. Generic values (Dk=4.0, Df=0.02) are rough estimates.',
          'Add separate segments for each impedance discontinuity: package → trace → via → trace → connector.',
          'COM is an estimate — run final signoff in HyperLynx with full S-parameter models.',
        ]}
        warnings={[
          'This is an estimated COM calculation, not a full IEEE 802.3 simulation. No crosstalk or jitter breakdown — use for early feasibility only.',
          'Loss values vary with frequency. For PAM4 links above 25 Gbps, full-wave simulation is strongly recommended.',
          'A 5 Ω impedance mismatch can shift COM by 1+ dB — verify stackup values.',
        ]}
      />

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

      {/* Step 1 — AI Extract (optional) */}
      <section className="mb-14">
        <SectionLabel icon={<Upload className="h-4 w-4" />} step="1" label="AI Extract (optional)" />
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground mb-3">
              Upload a datasheet or stackup report to auto-populate channel parameters.
            </p>
            <UploadZone onUpload={handleExtract} isLoading={isExtracting} />
          </CardContent>
        </Card>
      </section>

      {/* Step 2 — Channel Builder */}
      <section className="mb-14">
        <SectionLabel icon={<Activity className="h-4 w-4" />} step="2" label="Channel Builder" />

        {/* Top-level params */}
        <Card className="mb-4">
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
              <InputField label="Channel Name" value={channel.name}
                onChange={v => updateChannel({ name: v })} />
              <InputField label="Data Rate (Gbps)" type="number" value={channel.data_rate_gbps}
                onChange={v => updateChannel({ data_rate_gbps: parseFloat(v) || 0 })} />
              <SelectField label="Modulation" options={MODULATIONS} value={channel.modulation}
                onChange={v => updateChannel({ modulation: v })} />
            </div>

            {/* TX / RX params */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">TX Parameters</p>
                <div className="grid grid-cols-3 gap-2">
                  <InputField label="Swing (mV)" type="number" value={channel.tx_params.swing_mv}
                    onChange={v => updateTx({ swing_mv: parseFloat(v) || 0 })} />
                  <InputField label="De-emphasis (dB)" type="number" value={channel.tx_params.de_emphasis_db}
                    onChange={v => updateTx({ de_emphasis_db: parseFloat(v) || 0 })} />
                  <InputField label="Pre-cursor taps" type="number" value={channel.tx_params.pre_cursor_taps}
                    onChange={v => updateTx({ pre_cursor_taps: parseInt(v) || 0 })} />
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">RX Parameters</p>
                <div className="grid grid-cols-3 gap-2">
                  <InputField label="CTLE peaking (dB)" type="number" value={channel.rx_params.ctle_peaking_db}
                    onChange={v => updateRx({ ctle_peaking_db: parseFloat(v) || 0 })} />
                  <InputField label="DFE taps" type="number" value={channel.rx_params.dfe_taps}
                    onChange={v => updateRx({ dfe_taps: parseInt(v) || 0 })} />
                  <InputField label="DFE tap1 (mV)" type="number" value={channel.rx_params.dfe_tap1_mv}
                    onChange={v => updateRx({ dfe_tap1_mv: parseFloat(v) || 0 })} />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Segment pipeline visual */}
        <div className="flex items-center gap-1 mb-3 overflow-x-auto pb-2">
          <span className="text-xs font-bold text-primary shrink-0">TX &rarr;</span>
          {channel.segments.map((seg, i) => (
            <span key={i} className="shrink-0 px-2 py-1 rounded text-xs border border-border bg-card text-foreground">
              {seg.label || seg.type}
            </span>
          ))}
          <span className="text-xs font-bold text-primary shrink-0">&rarr; RX</span>
        </div>

        {/* Segment table */}
        <Card>
          <CardContent className="pt-6">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground uppercase tracking-widest">
                    <th className="py-2 pr-2 text-left">Label</th>
                    <th className="py-2 pr-2 text-left">Type</th>
                    <th className="py-2 pr-2 text-right">Length (mm)</th>
                    <th className="py-2 pr-2 text-right">Z (&Omega;)</th>
                    <th className="py-2 pr-2 text-right">Loss (dB/in)</th>
                    <th className="py-2 pr-2 text-right">Dk</th>
                    <th className="py-2 pr-2 text-right">Df</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {channel.segments.map((seg, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-secondary/30">
                      <td className="py-1.5 pr-2">
                        <input
                          className="bg-transparent border border-border rounded px-1.5 py-0.5 w-24 text-foreground"
                          value={seg.label}
                          onChange={e => updateSegment(i, { label: e.target.value })}
                        />
                      </td>
                      <td className="py-1.5 pr-2">
                        <select
                          className="bg-transparent border border-border rounded px-1 py-0.5 text-foreground"
                          value={seg.type}
                          onChange={e => updateSegment(i, { type: e.target.value })}
                        >
                          {SEGMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                      </td>
                      <td className="py-1.5 pr-2 text-right">
                        <input type="number" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-16 text-right text-foreground"
                          value={seg.length_mm} onChange={e => updateSegment(i, { length_mm: parseFloat(e.target.value) || 0 })} />
                      </td>
                      <td className="py-1.5 pr-2 text-right">
                        <input type="number" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-16 text-right text-foreground"
                          value={seg.impedance_ohm} onChange={e => updateSegment(i, { impedance_ohm: parseFloat(e.target.value) || 0 })} />
                      </td>
                      <td className="py-1.5 pr-2 text-right">
                        <input type="number" step="0.1" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-16 text-right text-foreground"
                          value={seg.loss_db_per_inch} onChange={e => updateSegment(i, { loss_db_per_inch: parseFloat(e.target.value) || 0 })} />
                      </td>
                      <td className="py-1.5 pr-2 text-right">
                        <input type="number" step="0.1" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-14 text-right text-foreground"
                          value={seg.dielectric_constant} onChange={e => updateSegment(i, { dielectric_constant: parseFloat(e.target.value) || 1 })} />
                      </td>
                      <td className="py-1.5 pr-2 text-right">
                        <input type="number" step="0.001" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-14 text-right text-foreground"
                          value={seg.loss_tangent} onChange={e => updateSegment(i, { loss_tangent: parseFloat(e.target.value) || 0 })} />
                      </td>
                      <td className="py-1.5 text-right">
                        <button
                          onClick={() => removeSegment(i)}
                          className="text-muted-foreground hover:text-destructive transition-colors p-0.5"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={addSegment}>
                <Plus className="mr-1.5 h-3.5 w-3.5" /> Add Segment
              </Button>
              <Button onClick={handleCalculate} disabled={isLoading || channel.segments.length === 0}>
                <Activity className="mr-1.5 h-4 w-4" />
                {isLoading ? 'Calculating\u2026' : 'Calculate COM'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Step 3 — Results */}
      {comResult && (
        <section className="mb-14">
          <SectionLabel icon={<CheckCircle className="h-4 w-4" />} step="3" label="COM Result" />

          {/* Big COM badge */}
          <div className="mb-4 flex items-center gap-4">
            <div className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-lg font-bold ${comBadge(comResult.com_db)}`}>
              {comResult.passed
                ? <CheckCircle className="h-5 w-5" />
                : <XCircle className="h-5 w-5" />
              }
              COM: {comResult.com_db} dB
              <span className="text-sm font-medium ml-1">{comResult.passed ? 'PASS' : 'FAIL'}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {/* Metrics */}
            <Card>
              <CardHeader><CardTitle className="text-sm">Channel Metrics</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <MetricRow label="Eye Height"            value={`${comResult.eye_height_mv} mV`} />
                  <MetricRow label="Eye Width"             value={`${comResult.eye_width_ps} ps`} />
                  <MetricRow label="Insertion Loss @ Nyquist" value={`${comResult.total_il_db} dB`} />
                  <MetricRow label="Return Loss (worst)"   value={`${comResult.rl_db} dB`} />
                </div>
              </CardContent>
            </Card>

            {/* Per-segment loss */}
            <Card>
              <CardHeader><CardTitle className="text-sm">Segment Loss Breakdown</CardTitle></CardHeader>
              <CardContent>
                {channel.segments.map((seg, i) => {
                  const loss = seg.loss_db_per_inch * (seg.length_mm / 25.4)
                  const maxLoss = Math.max(
                    ...channel.segments.map(s => s.loss_db_per_inch * (s.length_mm / 25.4)),
                    1
                  )
                  const pct = Math.min((loss / maxLoss) * 100, 100)
                  return (
                    <div key={i} className="mb-2">
                      <div className="flex justify-between text-xs text-muted-foreground mb-0.5">
                        <span>{seg.label || seg.type}</span>
                        <span>{loss.toFixed(2)} dB</span>
                      </div>
                      <div className="h-2 rounded-full bg-secondary overflow-hidden">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          </div>

          {/* Warnings */}
          {comResult.warnings?.length > 0 && (
            <Card className="mb-4 border-amber-500/30">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <p className="text-xs font-semibold uppercase tracking-widest text-amber-400">Warnings</p>
                </div>
                <ul className="space-y-1">
                  {comResult.warnings.map((w, i) => (
                    <li key={i} className="text-xs text-muted-foreground">&warning; {w}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Export */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3 flex-wrap">
                <Button onClick={() => handleExport('summary')}>
                  <Download className="mr-1.5 h-4 w-4" /> Summary Report
                </Button>
                <Button variant="outline" onClick={() => handleExport('ces')}>
                  <Download className="mr-1.5 h-4 w-4" /> CES Script
                </Button>
                <Button variant="outline" onClick={() => handleExport('hyperlynx')}>
                  <Download className="mr-1.5 h-4 w-4" /> HyperLynx CSV
                </Button>
                <p className="text-xs text-muted-foreground">
                  Estimated COM &mdash; verify in HyperLynx for final signoff.
                </p>
              </div>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  )
}

// ── Small helper components ────────────────────────────────────────────────

function InputField({ label, type = 'text', value, onChange }) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-transparent border border-border rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
      />
    </div>
  )
}

function SelectField({ label, options, value, onChange }) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-transparent border border-border rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
      >
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

function MetricRow({ label, value }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  )
}
