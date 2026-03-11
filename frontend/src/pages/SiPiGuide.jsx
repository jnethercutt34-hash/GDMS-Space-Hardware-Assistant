import { useState, useEffect, useCallback } from 'react'
import {
  Ruler, ChevronRight, Download, Send, BarChart3,
  CheckCircle2, XCircle, AlertTriangle, Filter, Zap,
  MessageSquare, FileText, Cpu,
} from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import SectionLabel from '../components/SectionLabel'

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

// ─── Main Component ───────────────────────────────────────────────────
export default function SiPiGuide() {
  const [interfaces, setInterfaces]     = useState([])
  const [selected, setSelected]         = useState([])
  const [rules, setRules]               = useState([])
  const [catFilter, setCatFilter]       = useState('')
  const [lossBudget, setLossBudget]     = useState(null)
  const [advisorQ, setAdvisorQ]         = useState('')
  const [advisorA, setAdvisorA]         = useState(null)
  const [boardDetails, setBoardDetails] = useState('')
  const [loading, setLoading]           = useState({})

  // Loss budget form state
  const [lbIface, setLbIface]           = useState('')
  const [traceLen, setTraceLen]         = useState(6)
  const [numVias, setNumVias]           = useState(4)
  const [numConn, setNumConn]           = useState(0)
  const [material, setMaterial]         = useState('fr4')

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

  // Loss budget calculation
  const calcLossBudget = async () => {
    const iface = lbIface || selected[0]
    if (!iface) return
    setLoading(p => ({ ...p, lb: true }))
    try {
      const res = await fetch(`${API}/api/sipi/loss-budget`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          interface: iface,
          trace_length_inches: traceLen,
          num_vias: numVias,
          num_connectors: numConn,
          material,
        }),
      })
      setLossBudget(await res.json())
    } catch { setLossBudget(null) }
    setLoading(p => ({ ...p, lb: false }))
  }

  // AI advisor
  const askAdvisor = async () => {
    if (!advisorQ.trim()) return
    setLoading(p => ({ ...p, advisor: true }))
    try {
      const res = await fetch(`${API}/api/sipi/advisor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: advisorQ,
          interfaces: selected,
          board_details: boardDetails,
        }),
      })
      setAdvisorA(await res.json())
    } catch { setAdvisorA(null) }
    setLoading(p => ({ ...p, advisor: false }))
  }

  // Export
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
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `sipi_design_rules.${ext}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {}
    setLoading(p => ({ ...p, export: false }))
  }

  // Filtered rules
  const filteredRules = catFilter
    ? rules.filter(r => r.category === catFilter)
    : rules

  // Unique categories from current rules
  const categories = [...new Set(rules.map(r => r.category))]

  // High-speed interfaces (show loss budget panel)
  const HS_INTERFACES = ['PCIe_Gen3', 'PCIe_Gen4', 'PCIe_Gen5', 'USB3', 'USB4', 'Ethernet_10G', 'Ethernet_25G', 'SpaceFibre']
  const hasHsInterface = selected.some(s => HS_INTERFACES.includes(s))

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
          Select your board's interfaces, review industry-sourced constraints,
          estimate channel loss budgets, and ask the AI advisor for tailored guidance.
        </p>
      </section>

      {/* ── Step 1: Interface Selector ── */}
      <section className="mb-14">
        <SectionLabel icon={<Cpu className="h-4 w-4" />} step="1" label="Select Board Interfaces" />
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground mb-4">
              Select every interface on your board. Design rules will be generated for all selected interfaces.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {interfaces.map(iface => {
                const isOn = selected.includes(iface.id)
                return (
                  <button
                    key={iface.id}
                    onClick={() => toggleInterface(iface.id)}
                    className={[
                      'text-left rounded-lg border px-3 py-2.5 transition-all text-xs',
                      isOn
                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30'
                        : 'border-border bg-card hover:border-muted-foreground/30',
                    ].join(' ')}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className={`font-semibold ${isOn ? 'text-primary' : 'text-foreground'}`}>
                        {iface.name}
                      </span>
                      {isOn && <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />}
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-snug line-clamp-2">
                      {iface.data_rate}
                    </p>
                  </button>
                )
              })}
            </div>

            {selected.length > 0 && (
              <div className="mt-4 flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">Selected:</span>
                {selected.map(id => (
                  <Badge key={id} variant="outline" className="text-[10px] border-primary/30 text-primary">
                    {id}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ── Step 2: Design Rules ── */}
      {selected.length > 0 && (
        <section className="mb-14">
          <SectionLabel icon={<Ruler className="h-4 w-4" />} step="2" label={`Design Rules (${filteredRules.length})`} />

          {/* Category filter bar */}
          {categories.length > 1 && (
            <div className="mb-4 flex items-center gap-2 flex-wrap">
              <Filter className="h-3.5 w-3.5 text-muted-foreground" />
              <button
                onClick={() => setCatFilter('')}
                className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${
                  !catFilter ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-muted-foreground/40'
                }`}
              >
                All ({rules.length})
              </button>
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setCatFilter(cat === catFilter ? '' : cat)}
                  className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${
                    catFilter === cat ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-muted-foreground/40'
                  }`}
                >
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
                          <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded border ${CAT_COLORS[r.category] || CAT_COLORS.General}`}>
                            {r.category}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-muted-foreground">{r.signal_group}</td>
                        <td className="py-2 px-2 text-foreground">
                          {r.parameter}
                          {r.rationale && (
                            <p className="text-[10px] text-muted-foreground/60 mt-0.5 leading-snug hidden group-hover:block max-w-xs">
                              {r.rationale}
                            </p>
                          )}
                        </td>
                        <td className="py-2 px-2 font-semibold text-foreground whitespace-nowrap">
                          {r.target} {r.tolerance && <span className="text-muted-foreground font-normal">{r.tolerance}</span>} {r.unit}
                        </td>
                        <td className={`py-2 px-2 font-medium ${SEV_COLORS[r.severity] || 'text-foreground'}`}>
                          {r.severity}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          {/* Export bar */}
          {filteredRules.length > 0 && (
            <div className="mt-3 flex items-center gap-3">
              <Button size="sm" variant="outline" onClick={() => exportRules('ces')} disabled={loading.export}>
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Export CES Script
              </Button>
              <Button size="sm" variant="outline" onClick={() => exportRules('markdown')} disabled={loading.export}>
                <FileText className="mr-1.5 h-3.5 w-3.5" />
                Export Markdown
              </Button>
              <span className="text-[10px] text-muted-foreground">
                {filteredRules.length} rules · {selected.length} interface{selected.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </section>
      )}

      {/* ── Step 3: Loss Budget ── */}
      {hasHsInterface && (
        <section className="mb-14">
          <SectionLabel icon={<BarChart3 className="h-4 w-4" />} step="3" label="Channel Loss Budget" />
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground mb-4">
                Estimate insertion loss for a high-speed channel and check against COM-derived limits.
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
                <div>
                  <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Interface</label>
                  <select
                    value={lbIface || selected.find(s => HS_INTERFACES.includes(s)) || ''}
                    onChange={e => setLbIface(e.target.value)}
                    className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground"
                  >
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

              {/* Loss budget results */}
              {lossBudget && (
                <div className="mt-4 space-y-4">
                  {/* Pass/fail banner */}
                  <div className={`rounded-lg border px-4 py-3 flex items-center gap-3 ${
                    lossBudget.passes
                      ? 'border-emerald-500/30 bg-emerald-500/10'
                      : 'border-red-500/30 bg-red-500/10'
                  }`}>
                    {lossBudget.passes
                      ? <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                      : <XCircle className="h-5 w-5 text-red-400 shrink-0" />
                    }
                    <div>
                      <p className={`text-sm font-semibold ${lossBudget.passes ? 'text-emerald-300' : 'text-red-300'}`}>
                        {lossBudget.passes ? 'PASS' : 'FAIL'} — {lossBudget.total_loss_db} dB / {lossBudget.max_channel_loss_db} dB max
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Margin: {lossBudget.margin_db} dB at {lossBudget.nyquist_ghz} GHz Nyquist
                      </p>
                    </div>
                  </div>

                  {/* Segments table */}
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

                  {/* Recommendations */}
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

      {/* ── Step 4: AI Advisor ── */}
      {selected.length > 0 && (
        <section className="mb-14">
          <SectionLabel icon={<MessageSquare className="h-4 w-4" />} step={hasHsInterface ? '4' : '3'} label="AI SI/PI Advisor" />
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground mb-4">
                Ask any SI/PI design question. The advisor uses your selected interfaces and rules as context.
              </p>

              <div className="space-y-3 mb-4">
                <textarea
                  value={advisorQ}
                  onChange={e => setAdvisorQ(e.target.value)}
                  placeholder="e.g. What PCB material should I use for a 12-layer board with PCIe Gen4 and DDR4? Do I need back-drilling?"
                  rows={3}
                  className="w-full rounded-md border border-border bg-secondary/50 px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/50 resize-none"
                />
                <div className="flex items-end gap-3">
                  <div className="flex-1">
                    <label className="block text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">
                      Board Details (optional)
                    </label>
                    <input
                      value={boardDetails}
                      onChange={e => setBoardDetails(e.target.value)}
                      placeholder="e.g. 14-layer, 93 mil thick, Megtron-6, backplane connector"
                      className="w-full rounded-md border border-border bg-secondary/50 px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50"
                    />
                  </div>
                  <Button size="sm" onClick={askAdvisor} disabled={loading.advisor || !advisorQ.trim()}>
                    <Send className="mr-1.5 h-3.5 w-3.5" />
                    {loading.advisor ? 'Thinking…' : 'Ask Advisor'}
                  </Button>
                </div>
              </div>

              {/* Quick-ask buttons */}
              <div className="flex flex-wrap gap-2 mb-4">
                {[
                  'What impedance targets should I use?',
                  'Do I need back-drilling on this stackup?',
                  'What material should I specify?',
                  'How should I route differential pairs?',
                  'What decoupling strategy do you recommend?',
                ].map(q => (
                  <button
                    key={q}
                    onClick={() => setAdvisorQ(q)}
                    className="text-[10px] px-2 py-1 rounded-md border border-border text-muted-foreground hover:border-primary/30 hover:text-primary transition-colors"
                  >
                    <Zap className="inline h-2.5 w-2.5 mr-1" />{q}
                  </button>
                ))}
              </div>

              {/* Answer */}
              {advisorA && (
                <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                  <p className="text-[10px] text-primary uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                    <MessageSquare className="h-3 w-3" /> Advisor Response
                  </p>
                  <div className="text-xs text-foreground leading-relaxed whitespace-pre-wrap">
                    {advisorA.answer}
                  </div>
                  {advisorA.referenced_rules?.length > 0 && (
                    <div className="mt-3 flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] text-muted-foreground">Referenced rules:</span>
                      {advisorA.referenced_rules.map(rid => (
                        <Badge key={rid} variant="outline" className="text-[10px] border-primary/30 text-primary">
                          {rid}
                        </Badge>
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
