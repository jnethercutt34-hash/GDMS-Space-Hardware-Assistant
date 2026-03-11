import { useState, useEffect, useCallback } from 'react'
import {
  Ruler, ChevronRight, Download, Send, BarChart3,
  CheckCircle2, XCircle, AlertTriangle, Filter, Zap,
  MessageSquare, FileText, Cpu, Activity, Plus, Trash2,
  Upload, CheckCircle,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import SectionLabel from '../components/SectionLabel'
import UploadZone from '../components/UploadZone'
import { downloadBlob } from '../lib/downloadBlob'

const API = ''  // vite proxy

// ─── Category colors ──────────────────────────────────────────────────
const CAT_COLORS = {
  'Impedance':         'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'Length Matching':    'bg-violet-500/20 text-violet-300 border-violet-500/30',
  'Spacing / Crosstalk': 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  'Via Budget':        'bg-red-500/20 text-red-300 border-red-500/30',
  'Termination':       'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'Decoupling':        'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'Timing':            'bg-pink-500/20 text-pink-300 border-pink-500/30',
  'General':           'bg-gray-500/20 text-gray-300 border-gray-500/30',
}

const SEV_COLORS = {
  Required:    'text-red-400',
  Recommended: 'text-amber-400',
  Advisory:    'text-blue-400',
}

// ─── COM channel defaults ─────────────────────────────────────────────
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

// ─── Tiny input helpers (for COM section) ─────────────────────────────
function InputField({ label, type = 'text', value, onChange }) {
  return (
    <div>
      <label className="block text-[10px] text-muted-foreground mb-1">{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-transparent border border-border rounded px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary" />
    </div>
  )
}

function SelectField({ label, options, value, onChange }) {
  return (
    <div>
      <label className="block text-[10px] text-muted-foreground mb-1">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-transparent border border-border rounded px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary">
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

function MetricRow({ label, value }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════
export default function SiPiGuide() {
  // ── Interface & rules state ──
  const [interfaces, setInterfaces]     = useState([])
  const [selected, setSelected]         = useState([])
  const [rules, setRules]               = useState([])
  const [catFilter, setCatFilter]       = useState('')
  const [loading, setLoading]           = useState({})

  // ── Loss budget state ──
  const [lossBudget, setLossBudget]     = useState(null)
  const [lbIface, setLbIface]           = useState('')
  const [traceLen, setTraceLen]         = useState(6)
  const [numVias, setNumVias]           = useState(4)
  const [numConn, setNumConn]           = useState(0)
  const [material, setMaterial]         = useState('fr4')

  // ── COM channel state ──
  const [showCom, setShowCom]           = useState(false)
  const [channel, setChannel]           = useState(DEFAULT_CHANNEL)
  const [comResult, setComResult]       = useState(null)
  const [comError, setComError]         = useState(null)

  // ── AI advisor state ──
  const [advisorQ, setAdvisorQ]         = useState('')
  const [advisorA, setAdvisorA]         = useState(null)
  const [boardDetails, setBoardDetails] = useState('')

  // Load interfaces on mount
  useEffect(() => {
    fetch(`${API}/api/sipi/interfaces`)
      .then(r => r.json())
      .then(d => setInterfaces(d.interfaces || []))
      .catch(() => {})
  }, [])

  // Toggle interface selection
  const toggleInterface = (id) => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  // Fetch rules when selection changes
  const fetchRules = useCallback(async () => {
    if (!selected.length) { setRules([]); return }
    setLoading(p => ({ ...p, rules: true }))
    try {
      const res = await fetch(`${API}/api/sipi/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interfaces: selected }),
      })
      const data = await res.json()
      setRules(data.rules || [])
    } catch { setRules([]) }
    setLoading(p => ({ ...p, rules: false }))
  }, [selected])

  useEffect(() => { fetchRules() }, [fetchRules])

  // ── Loss budget ──
  const calcLossBudget = async () => {
    const iface = lbIface || selected[0]
    if (!iface) return
    setLoading(p => ({ ...p, lb: true }))
    try {
      const res = await fetch(`${API}/api/sipi/loss-budget`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interface: iface, trace_length_inches: traceLen, num_vias: numVias, num_connectors: numConn, material }),
      })
      setLossBudget(await res.json())
    } catch { setLossBudget(null) }
    setLoading(p => ({ ...p, lb: false }))
  }

  // ── COM channel helpers ──
  const updateChannel = (updates) => setChannel(prev => ({ ...prev, ...updates }))
  const updateSegment = (i, updates) => {
    const segs = [...channel.segments]
    segs[i] = { ...segs[i], ...updates }
    updateChannel({ segments: segs })
  }
  const addSegment = () => updateChannel({
    segments: [...channel.segments, { ...DEFAULT_SEGMENT, label: `Seg_${channel.segments.length + 1}` }],
  })
  const removeSegment = (i) => updateChannel({ segments: channel.segments.filter((_, idx) => idx !== i) })
  const updateTx = (updates) => updateChannel({ tx_params: { ...channel.tx_params, ...updates } })
  const updateRx = (updates) => updateChannel({ rx_params: { ...channel.rx_params, ...updates } })

  const handleComExtract = async (file) => {
    setLoading(p => ({ ...p, comExtract: true }))
    setComError(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API}/api/com/extract-channel`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json()).detail || 'Extraction failed')
      const data = await res.json()
      setChannel(data.channel)
      setComResult(null)
    } catch (e) { setComError(e.message) }
    setLoading(p => ({ ...p, comExtract: false }))
  }

  const handleComCalculate = async () => {
    setLoading(p => ({ ...p, com: true }))
    setComError(null)
    try {
      const res = await fetch(`${API}/api/com/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Calculation failed')
      const data = await res.json()
      setComResult(data.result)
      setChannel(data.channel)
    } catch (e) { setComError(e.message) }
    setLoading(p => ({ ...p, com: false }))
  }

  const handleComExport = async (format) => {
    if (!comResult) return
    try {
      const res = await fetch(`${API}/api/com/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, result: comResult, format }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Export failed')
      const blob = await res.blob()
      const ext = { ces: 'py', hyperlynx: 'csv', summary: 'md' }[format] || 'txt'
      downloadBlob(blob, `com_${format}.${ext}`)
    } catch (e) { setComError(e.message) }
  }

  const comBadge = (com) => {
    if (com >= 3) return 'bg-green-500/20 text-green-400 border-green-500/30'
    if (com >= 1) return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
    return 'bg-red-500/20 text-red-400 border-red-500/30'
  }

  // ── AI advisor ──
  const askAdvisor = async () => {
    if (!advisorQ.trim()) return
    setLoading(p => ({ ...p, advisor: true }))
    try {
      const res = await fetch(`${API}/api/sipi/advisor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: advisorQ, interfaces: selected, board_details: boardDetails }),
      })
      setAdvisorA(await res.json())
    } catch { setAdvisorA(null) }
    setLoading(p => ({ ...p, advisor: false }))
  }

  // ── Export rules ──
  const exportRules = async (fmt) => {
    if (!rules.length) return
    setLoading(p => ({ ...p, export: true }))
    try {
      const res = await fetch(`${API}/api/sipi/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules: filteredRules, format: fmt }),
      })
      const blob = await res.blob()
      const ext = fmt === 'markdown' ? 'md' : 'py'
      downloadBlob(blob, `sipi_design_rules.${ext}`)
    } catch {}
    setLoading(p => ({ ...p, export: false }))
  }

  // Derived
  const filteredRules = catFilter ? rules.filter(r => r.category === catFilter) : rules
  const categories = [...new Set(rules.map(r => r.category))]
  const HS_INTERFACES = ['PCIe_Gen3', 'PCIe_Gen4', 'PCIe_Gen5', 'USB3', 'USB4', 'Ethernet_10G', 'Ethernet_25G', 'SpaceFibre']
  const hasHsInterface = selected.some(s => HS_INTERFACES.includes(s))

  // Step numbering — dynamic based on what sections show
  let stepN = 1
  const step = () => String(stepN++)

  return (
    <div>
      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          SI/PI Design Guide
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          SI/PI Design Guide
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Set proactive, spec-driven design rules <em>before</em> HyperLynx simulation.
          Select interfaces, review constraints, estimate loss budgets, model full channels
          with COM analysis, and ask the AI advisor — all in one workflow.
        </p>
      </section>

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* STEP 1: Interface Selector                                    */}
      {/* ══════════════════════════════════════════════════════════════ */}
      <section className="mb-14">
        <SectionLabel icon={<Cpu className="h-4 w-4" />} step={step()} label="Select Board Interfaces" />
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground mb-4">
              Select every interface on your board. Design rules will be generated for all selected interfaces.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {interfaces.map(iface => {
                const isOn = selected.includes(iface.id)
                return (
                  <button key={iface.id} onClick={() => toggleInterface(iface.id)}
                    className={[
                      'text-left rounded-lg border px-3 py-2.5 transition-all text-xs',
                      isOn ? 'border-primary bg-primary/10 ring-1 ring-primary/30' : 'border-border bg-card hover:border-muted-foreground/30',
                    ].join(' ')}>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className={`font-semibold ${isOn ? 'text-primary' : 'text-foreground'}`}>{iface.name}</span>
                      {isOn && <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />}
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-snug line-clamp-2">{iface.data_rate}</p>
                  </button>
                )
              })}
            </div>
            {selected.length > 0 && (
              <div className="mt-4 flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">Selected:</span>
                {selected.map(id => (
                  <Badge key={id} variant="outline" className="text-[10px] border-primary/30 text-primary">{id}</Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* STEP 2: Design Rules                                          */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {selected.length > 0 && (
        <section className="mb-14">
          <SectionLabel icon={<Ruler className="h-4 w-4" />} step={step()} label={`Design Rules (${filteredRules.length})`} />

          {categories.length > 1 && (
            <div className="mb-4 flex items-center gap-2 flex-wrap">
              <Filter className="h-3.5 w-3.5 text-muted-foreground" />
              <button onClick={() => setCatFilter('')}
                className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${!catFilter ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-muted-foreground/40'}`}>
                All ({rules.length})
              </button>
              {categories.map(cat => (
                <button key={cat} onClick={() => setCatFilter(cat === catFilter ? '' : cat)}
                  className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${catFilter === cat ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-muted-foreground/40'}`}>
                  {cat} ({rules.filter(r => r.category === cat).length})
                </button>
              ))}
            </div>
          )}

          <Card>
            <CardContent className="pt-4 pb-2 overflow-x-auto">
              {loading.rules ? (
                <p className="text-xs text-muted-foreground py-8 text-center">Loading rules…</p>
              ) : filteredRules.length === 0 ? (
                <p className="text-xs text-muted-foreground py-8 text-center">No rules match the current filter.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="text-left py-2 px-2 font-medium">Rule ID</th>
                      <th className="text-left py-2 px-2 font-medium">Interface</th>
                      <th className="text-left py-2 px-2 font-medium">Category</th>
                      <th className="text-left py-2 px-2 font-medium">Signal Group</th>
                      <th className="text-left py-2 px-2 font-medium">Parameter</th>
                      <th className="text-left py-2 px-2 font-medium">Target</th>
                      <th className="text-left py-2 px-2 font-medium">Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRules.map((r, i) => (
                      <tr key={r.rule_id + i} className="border-b border-border/50 hover:bg-secondary/30 group">
                        <td className="py-2 px-2 font-mono text-primary/80">{r.rule_id}</td>
                        <td className="py-2 px-2 text-foreground">{r.interface}</td>
                        <td className="py-2 px-2">
                          <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded border ${CAT_COLORS[r.category] || CAT_COLORS.General}`}>{r.category}</span>
                        </td>
                        <td className="py-2 px-2 text-muted-foreground">{r.signal_group}</td>
                        <td className="py-2 px-2 text-foreground">
                          {r.parameter}
                          {r.rationale && <p className="text-[10px] text-muted-foreground/60 mt-0.5 leading-snug hidden group-hover:block max-w-xs">{r.rationale}</p>}
                        </td>
                        <td className="py-2 px-2 font-semibold text-foreground whitespace-nowrap">
                          {r.target} {r.tolerance && <span className="text-muted-foreground font-normal">{r.tolerance}</span>} {r.unit}
                        </td>
                        <td className={`py-2 px-2 font-medium ${SEV_COLORS[r.severity] || 'text-foreground'}`}>{r.severity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          {filteredRules.length > 0 && (
            <div className="mt-3 flex items-center gap-3">
              <Button size="sm" variant="outline" onClick={() => exportRules('ces')} disabled={loading.export}>
                <Download className="mr-1.5 h-3.5 w-3.5" /> Export CES Script
              </Button>
              <Button size="sm" variant="outline" onClick={() => exportRules('markdown')} disabled={loading.export}>
                <FileText className="mr-1.5 h-3.5 w-3.5" /> Export Markdown
              </Button>
              <span className="text-[10px] text-muted-foreground">
                {filteredRules.length} rules · {selected.length} interface{selected.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </section>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* STEP 3: Quick Loss Budget                                     */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {hasHsInterface && (
        <section className="mb-14">
          <SectionLabel icon={<BarChart3 className="h-4 w-4" />} step={step()} label="Quick Loss Budget" />
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground mb-4">
                Fast insertion-loss estimate against COM-derived limits. For detailed segment-by-segment analysis, expand the full channel model below.
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
                <div>
                  <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Interface</label>
                  <select value={lbIface || selected.find(s => HS_INTERFACES.includes(s)) || ''} onChange={e => setLbIface(e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground">
                    {selected.filter(s => HS_INTERFACES.includes(s)).map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Trace Length (in)</label>
                  <input type="number" value={traceLen} onChange={e => setTraceLen(+e.target.value)} min={0.5} max={40} step={0.5}
                    className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground" />
                </div>
                <div>
                  <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Vias</label>
                  <input type="number" value={numVias} onChange={e => setNumVias(+e.target.value)} min={0} max={20}
                    className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground" />
                </div>
                <div>
                  <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Connectors</label>
                  <input type="number" value={numConn} onChange={e => setNumConn(+e.target.value)} min={0} max={10}
                    className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground" />
                </div>
                <div>
                  <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Material</label>
                  <select value={material} onChange={e => setMaterial(e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground">
                    <option value="fr4">Standard FR-4</option>
                    <option value="low_loss">Low-Loss Laminate</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <Button size="sm" onClick={calcLossBudget} disabled={loading.lb} className="w-full">
                    <BarChart3 className="mr-1.5 h-3.5 w-3.5" />
                    {loading.lb ? 'Calculating…' : 'Calculate'}
                  </Button>
                </div>
              </div>

              {lossBudget && (
                <div className="mt-4 space-y-4">
                  <div className={`rounded-lg border px-4 py-3 flex items-center gap-3 ${lossBudget.passes ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-red-500/30 bg-red-500/10'}`}>
                    {lossBudget.passes ? <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" /> : <XCircle className="h-5 w-5 text-red-400 shrink-0" />}
                    <div>
                      <p className={`text-sm font-semibold ${lossBudget.passes ? 'text-emerald-300' : 'text-red-300'}`}>
                        {lossBudget.passes ? 'PASS' : 'FAIL'} — {lossBudget.total_loss_db} dB / {lossBudget.max_channel_loss_db} dB max
                      </p>
                      <p className="text-xs text-muted-foreground">Margin: {lossBudget.margin_db} dB at {lossBudget.nyquist_ghz} GHz Nyquist</p>
                    </div>
                  </div>

                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th className="text-left py-2 px-2 font-medium">Segment</th>
                        <th className="text-right py-2 px-2 font-medium">Loss (dB)</th>
                        <th className="text-left py-2 px-2 font-medium">Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lossBudget.segments.map((seg, i) => (
                        <tr key={i} className="border-b border-border/50">
                          <td className="py-2 px-2 text-foreground">{seg.segment}</td>
                          <td className="py-2 px-2 text-right font-mono text-foreground">{seg.loss_db}</td>
                          <td className="py-2 px-2 text-muted-foreground">{seg.notes}</td>
                        </tr>
                      ))}
                      <tr className="font-semibold">
                        <td className="py-2 px-2 text-foreground">Total</td>
                        <td className="py-2 px-2 text-right font-mono text-foreground">{lossBudget.total_loss_db}</td>
                        <td className="py-2 px-2 text-muted-foreground">Budget: {lossBudget.max_channel_loss_db} dB</td>
                      </tr>
                    </tbody>
                  </table>

                  {lossBudget.recommendations?.length > 0 && (
                    <div className="rounded-md border border-border bg-secondary/30 px-3 py-2.5">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <AlertTriangle className="h-3 w-3" /> Recommendations
                      </p>
                      {lossBudget.recommendations.map((rec, i) => (
                        <p key={i} className="text-xs text-muted-foreground leading-relaxed">{rec}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* STEP 4: Full Channel Model & COM (collapsible)                */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {hasHsInterface && (() => {
        const comStep = step()
        return (
        <section className="mb-14">
          <SectionLabel icon={<Activity className="h-4 w-4" />} step={comStep} label="Full Channel Model &amp; COM" />

          {/* Expand toggle */}
          <button
            onClick={() => setShowCom(!showCom)}
            className="mb-4 w-full text-left flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3 hover:border-primary/30 transition-colors"
          >
            <div>
              <p className="text-sm font-semibold text-foreground">Channel Operating Margin (IEEE 802.3)</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Build a detailed TX→RX channel model segment by segment, compute estimated COM, and export for HyperLynx.
              </p>
            </div>
            <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${showCom ? 'rotate-90' : ''}`} />
          </button>

          {showCom && (
            <div className="space-y-6">
              {/* Error */}
              {comError && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-destructive font-semibold uppercase tracking-widest mb-0.5">Error</p>
                    <p className="text-xs text-muted-foreground">{comError}</p>
                  </div>
                  <button onClick={() => setComError(null)} className="text-muted-foreground hover:text-foreground ml-4 text-lg leading-none">&times;</button>
                </div>
              )}

              {/* AI Extract */}
              <Card>
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">AI Extract (optional)</p>
                  <p className="text-xs text-muted-foreground mb-3">Upload a transceiver datasheet or stackup report to auto-populate channel parameters.</p>
                  <UploadZone onUpload={handleComExtract} isLoading={loading.comExtract} />
                </CardContent>
              </Card>

              {/* Channel builder */}
              <Card>
                <CardContent className="pt-6">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                    <InputField label="Channel Name" value={channel.name} onChange={v => updateChannel({ name: v })} />
                    <InputField label="Data Rate (Gbps)" type="number" value={channel.data_rate_gbps} onChange={v => updateChannel({ data_rate_gbps: parseFloat(v) || 0 })} />
                    <SelectField label="Modulation" options={MODULATIONS} value={channel.modulation} onChange={v => updateChannel({ modulation: v })} />
                  </div>

                  {/* TX / RX */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-4">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2">TX Parameters</p>
                      <div className="grid grid-cols-3 gap-2">
                        <InputField label="Swing (mV)" type="number" value={channel.tx_params.swing_mv} onChange={v => updateTx({ swing_mv: parseFloat(v) || 0 })} />
                        <InputField label="De-emph (dB)" type="number" value={channel.tx_params.de_emphasis_db} onChange={v => updateTx({ de_emphasis_db: parseFloat(v) || 0 })} />
                        <InputField label="Pre-cursor" type="number" value={channel.tx_params.pre_cursor_taps} onChange={v => updateTx({ pre_cursor_taps: parseInt(v) || 0 })} />
                      </div>
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2">RX Parameters</p>
                      <div className="grid grid-cols-3 gap-2">
                        <InputField label="CTLE (dB)" type="number" value={channel.rx_params.ctle_peaking_db} onChange={v => updateRx({ ctle_peaking_db: parseFloat(v) || 0 })} />
                        <InputField label="DFE taps" type="number" value={channel.rx_params.dfe_taps} onChange={v => updateRx({ dfe_taps: parseInt(v) || 0 })} />
                        <InputField label="DFE tap1 (mV)" type="number" value={channel.rx_params.dfe_tap1_mv} onChange={v => updateRx({ dfe_tap1_mv: parseFloat(v) || 0 })} />
                      </div>
                    </div>
                  </div>

                  {/* Pipeline visual */}
                  <div className="flex items-center gap-1 mb-3 overflow-x-auto pb-2">
                    <span className="text-xs font-bold text-primary shrink-0">TX →</span>
                    {channel.segments.map((seg, i) => (
                      <span key={i} className="shrink-0 px-2 py-1 rounded text-xs border border-border bg-card text-foreground">{seg.label || seg.type}</span>
                    ))}
                    <span className="text-xs font-bold text-primary shrink-0">→ RX</span>
                  </div>

                  {/* Segment table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border text-muted-foreground uppercase tracking-widest">
                          <th className="py-2 pr-2 text-left">Label</th>
                          <th className="py-2 pr-2 text-left">Type</th>
                          <th className="py-2 pr-2 text-right">Length (mm)</th>
                          <th className="py-2 pr-2 text-right">Z (Ω)</th>
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
                              <input className="bg-transparent border border-border rounded px-1.5 py-0.5 w-24 text-foreground text-xs"
                                value={seg.label} onChange={e => updateSegment(i, { label: e.target.value })} />
                            </td>
                            <td className="py-1.5 pr-2">
                              <select className="bg-transparent border border-border rounded px-1 py-0.5 text-foreground text-xs"
                                value={seg.type} onChange={e => updateSegment(i, { type: e.target.value })}>
                                {SEGMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                              </select>
                            </td>
                            <td className="py-1.5 pr-2 text-right">
                              <input type="number" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-16 text-right text-foreground text-xs"
                                value={seg.length_mm} onChange={e => updateSegment(i, { length_mm: parseFloat(e.target.value) || 0 })} />
                            </td>
                            <td className="py-1.5 pr-2 text-right">
                              <input type="number" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-16 text-right text-foreground text-xs"
                                value={seg.impedance_ohm} onChange={e => updateSegment(i, { impedance_ohm: parseFloat(e.target.value) || 0 })} />
                            </td>
                            <td className="py-1.5 pr-2 text-right">
                              <input type="number" step="0.1" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-16 text-right text-foreground text-xs"
                                value={seg.loss_db_per_inch} onChange={e => updateSegment(i, { loss_db_per_inch: parseFloat(e.target.value) || 0 })} />
                            </td>
                            <td className="py-1.5 pr-2 text-right">
                              <input type="number" step="0.1" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-14 text-right text-foreground text-xs"
                                value={seg.dielectric_constant} onChange={e => updateSegment(i, { dielectric_constant: parseFloat(e.target.value) || 1 })} />
                            </td>
                            <td className="py-1.5 pr-2 text-right">
                              <input type="number" step="0.001" className="bg-transparent border border-border rounded px-1.5 py-0.5 w-14 text-right text-foreground text-xs"
                                value={seg.loss_tangent} onChange={e => updateSegment(i, { loss_tangent: parseFloat(e.target.value) || 0 })} />
                            </td>
                            <td className="py-1.5 text-right">
                              <button onClick={() => removeSegment(i)} className="text-muted-foreground hover:text-destructive transition-colors p-0.5">
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
                    <Button onClick={handleComCalculate} disabled={loading.com || channel.segments.length === 0}>
                      <Activity className="mr-1.5 h-4 w-4" />
                      {loading.com ? 'Calculating…' : 'Calculate COM'}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* COM Result */}
              {comResult && (
                <div className="space-y-4">
                  {/* Big COM badge */}
                  <div className="flex items-center gap-4">
                    <div className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-lg font-bold ${comBadge(comResult.com_db)}`}>
                      {comResult.passed ? <CheckCircle className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
                      COM: {comResult.com_db} dB
                      <span className="text-sm font-medium ml-1">{comResult.passed ? 'PASS' : 'FAIL'}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader><CardTitle className="text-sm">Channel Metrics</CardTitle></CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          <MetricRow label="Eye Height" value={`${comResult.eye_height_mv} mV`} />
                          <MetricRow label="Eye Width" value={`${comResult.eye_width_ps} ps`} />
                          <MetricRow label="Insertion Loss @ Nyquist" value={`${comResult.total_il_db} dB`} />
                          <MetricRow label="Return Loss (worst)" value={`${comResult.rl_db} dB`} />
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader><CardTitle className="text-sm">Segment Loss Breakdown</CardTitle></CardHeader>
                      <CardContent>
                        {channel.segments.map((seg, i) => {
                          const loss = seg.loss_db_per_inch * (seg.length_mm / 25.4)
                          const maxLoss = Math.max(...channel.segments.map(s => s.loss_db_per_inch * (s.length_mm / 25.4)), 1)
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

                  {comResult.warnings?.length > 0 && (
                    <Card className="border-amber-500/30">
                      <CardContent className="pt-4">
                        <div className="flex items-center gap-2 mb-2">
                          <AlertTriangle className="h-4 w-4 text-amber-400" />
                          <p className="text-xs font-semibold uppercase tracking-widest text-amber-400">Warnings</p>
                        </div>
                        <ul className="space-y-1">
                          {comResult.warnings.map((w, i) => (
                            <li key={i} className="text-xs text-muted-foreground">⚠ {w}</li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>
                  )}

                  {/* Export */}
                  <Card>
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-3 flex-wrap">
                        <Button size="sm" onClick={() => handleComExport('summary')}>
                          <Download className="mr-1.5 h-3.5 w-3.5" /> Summary Report
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleComExport('ces')}>
                          <Download className="mr-1.5 h-3.5 w-3.5" /> CES Script
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleComExport('hyperlynx')}>
                          <Download className="mr-1.5 h-3.5 w-3.5" /> HyperLynx CSV
                        </Button>
                        <p className="text-xs text-muted-foreground">
                          Estimated COM — verify in HyperLynx for final signoff.
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
            </div>
          )}
        </section>
        )
      })()}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* STEP 5: AI Advisor                                            */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {selected.length > 0 && (
        <section className="mb-14">
          <SectionLabel icon={<MessageSquare className="h-4 w-4" />} step={step()} label="AI SI/PI Advisor" />
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground mb-4">
                Ask any SI/PI design question. The advisor uses your selected interfaces and rules as context.
              </p>

              <div className="space-y-3 mb-4">
                <textarea
                  value={advisorQ} onChange={e => setAdvisorQ(e.target.value)}
                  placeholder="e.g. What PCB material should I use for a 12-layer board with PCIe Gen4 and DDR4? Do I need back-drilling?"
                  rows={3}
                  className="w-full rounded-md border border-border bg-secondary/50 px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/50 resize-none"
                />
                <div className="flex items-end gap-3">
                  <div className="flex-1">
                    <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Board Details (optional)</label>
                    <input value={boardDetails} onChange={e => setBoardDetails(e.target.value)}
                      placeholder="e.g. 14-layer, 93 mil thick, Megtron-6, backplane connector"
                      className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50" />
                  </div>
                  <Button size="sm" onClick={askAdvisor} disabled={loading.advisor || !advisorQ.trim()}>
                    <Send className="mr-1.5 h-3.5 w-3.5" />
                    {loading.advisor ? 'Thinking…' : 'Ask Advisor'}
                  </Button>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                {[
                  'What impedance targets should I use?',
                  'Do I need back-drilling on this stackup?',
                  'What material should I specify?',
                  'How should I route differential pairs?',
                  'What decoupling strategy do you recommend?',
                  'Will my channel pass COM at this data rate?',
                ].map(q => (
                  <button key={q} onClick={() => setAdvisorQ(q)}
                    className="text-[10px] px-2 py-1 rounded-md border border-border text-muted-foreground hover:border-primary/30 hover:text-primary transition-colors">
                    <Zap className="inline h-2.5 w-2.5 mr-1" />{q}
                  </button>
                ))}
              </div>

              {advisorA && (
                <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                  <p className="text-[10px] text-primary uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                    <MessageSquare className="h-3 w-3" /> Advisor Response
                  </p>
                  <div className="text-xs text-foreground leading-relaxed whitespace-pre-wrap">{advisorA.answer}</div>
                  {advisorA.referenced_rules?.length > 0 && (
                    <div className="mt-3 flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] text-muted-foreground">Referenced rules:</span>
                      {advisorA.referenced_rules.map(rid => (
                        <Badge key={rid} variant="outline" className="text-[10px] border-primary/30 text-primary">{rid}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  )
}
