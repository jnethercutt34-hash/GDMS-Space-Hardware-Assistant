import { useNavigate } from 'react-router-dom'
import {
  Satellite, Upload, Cpu, GitCompare, Ruler, Boxes, Radio,
  ClipboardList, ShieldCheck, ArrowRight, Zap,
} from 'lucide-react'
import { Card, CardContent } from '../components/ui/card'

// ---------------------------------------------------------------------------
// Module definitions
// ---------------------------------------------------------------------------

const MODULES = [
  {
    to: '/librarian',
    icon: Upload,
    title: 'Component Librarian',
    color: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    summary:
      'Upload a manufacturer PDF datasheet and let AI extract Xpedition-ready parameters — voltage ratings, package, pin count, radiation hardness, and more. Every part is saved to a searchable library you can tag by program.',
    bullets: [
      'Drag-and-drop PDF upload',
      'AI extracts 12+ engineering fields per part',
      'Auto-saves to a persistent, searchable part library',
      'One-click push to Xpedition Databook',
    ],
  },
  {
    to: '/fpga',
    icon: GitCompare,
    title: 'FPGA I/O Bridge',
    color: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
    summary:
      'Compare two FPGA pin-map CSVs side-by-side and instantly see every pin swap. AI flags SI/PI risk for each change so you can catch bank moves and termination issues before layout.',
    bullets: [
      'Upload old vs. new pin-map CSVs',
      'Delta engine highlights every swap',
      'AI risk assessment per pin change',
      'Export Xpedition I/O Designer script',
    ],
  },
  {
    to: '/constraints',
    icon: Ruler,
    title: 'SI/PI Constraint Editor',
    color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    summary:
      'Paste or upload signal-integrity specs and let AI convert them into structured constraint rules — impedance, length matching, spacing, and differential pair targets ready for your constraint system.',
    bullets: [
      'AI parses free-text SI/PI requirements',
      'Structured rule table with net-class mapping',
      'Export Xpedition CES constraint script',
    ],
  },
  {
    to: '/block-diagram',
    icon: Boxes,
    title: 'Block Diagram Builder',
    color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    summary:
      'Build system-level block diagrams on a drag-and-drop canvas or let AI generate one from a parts list. Click ports to wire connections, name signals, then export a netlist seed for Xpedition.',
    bullets: [
      'Drag-and-drop block canvas with dot grid',
      'Click-to-wire port connections',
      'AI generates diagrams from part numbers',
      'Export netlist CSV or Xpedition script',
    ],
  },
  {
    to: '/com',
    icon: Radio,
    title: 'COM Channel Analysis',
    color: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
    summary:
      'Model high-speed serial channels segment by segment and estimate Channel Operating Margin per IEEE 802.3. Quickly check whether a link will close before committing to a full simulation.',
    bullets: [
      'Build channel models (trace, via, connector, package)',
      'AI extracts channel parameters from specs',
      'Simplified COM calculator (Annex 93A)',
      'Export to HyperLynx CSV or CES script',
    ],
  },
  {
    to: '/bom',
    icon: ClipboardList,
    title: 'BOM Analyzer',
    color: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    summary:
      'Upload a Bill of Materials CSV and get instant cross-referencing against your part library plus AI-powered lifecycle and radiation risk assessment for every line item.',
    bullets: [
      'Auto-detects column mapping from any BOM format',
      'Fuzzy-match cross-reference against part library',
      'AI flags obsolescence, radiation, and alternate parts',
      'Export annotated BOM CSV + Markdown risk report',
    ],
  },
  {
    to: '/drc',
    icon: ShieldCheck,
    title: 'Schematic DRC',
    color: 'text-red-400 bg-red-500/10 border-red-500/20',
    summary:
      'Upload a netlist and run 13 deterministic design-rule checks plus AI heuristics. Catches unconnected power pins, missing decoupling, unterminated clocks, and space-compliance gaps like missing SEL protection.',
    bullets: [
      'Parses Xpedition ASC, OrCAD, and CSV netlists',
      '13 built-in rules (power, connectivity, naming, space)',
      'AI checks interface protocols & power sequencing',
      'Export DRC report as Markdown or CSV',
    ],
  },
]

// ---------------------------------------------------------------------------
// Module card
// ---------------------------------------------------------------------------

function ModuleCard({ mod }) {
  const navigate = useNavigate()
  const Icon = mod.icon

  return (
    <Card
      className="group cursor-pointer hover:border-primary/40 transition-all hover:shadow-lg hover:shadow-primary/5"
      onClick={() => navigate(mod.to)}
    >
      <CardContent className="py-5 px-5">
        <div className="flex items-start gap-4">
          <div className={`shrink-0 rounded-lg border p-2.5 ${mod.color}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <h3 className="font-heading text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                {mod.title}
              </h3>
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-primary group-hover:translate-x-0.5 transition-all shrink-0" />
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed mb-3">
              {mod.summary}
            </p>
            <ul className="space-y-1">
              {mod.bullets.map((b, i) => (
                <li key={i} className="text-[11px] text-muted-foreground/70 flex items-start gap-1.5">
                  <Zap className="h-3 w-3 text-primary/50 shrink-0 mt-0.5" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Home page
// ---------------------------------------------------------------------------

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="mb-16 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 mb-6">
          <Satellite className="h-4 w-4 text-primary" />
          <span className="text-xs font-semibold text-primary uppercase tracking-widest">
            GDMS Space Hardware Assistant
          </span>
        </div>

        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl max-w-4xl mx-auto">
          AI-Powered Digital Hardware
          <br />
          <span className="text-primary">Engineering Toolkit</span>
        </h1>

        <p className="mt-6 max-w-2xl mx-auto text-lg text-muted-foreground leading-relaxed">
          A unified suite of tools for space and defense hardware engineers.
          Extract component data from datasheets, compare FPGA pin maps, define
          SI/PI constraints, build system block diagrams, analyze high-speed
          channels, audit BOMs for risk, and run schematic design-rule checks —
          all with AI acceleration and Xpedition integration.
        </p>

        <div className="mt-8 flex flex-wrap justify-center gap-6 text-xs text-muted-foreground/60">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> 7 Engineering Modules
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" /> AI-Assisted Extraction
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-violet-400" /> Xpedition Export
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" /> Air-Gap Ready
          </span>
        </div>
      </section>

      {/* Module grid */}
      <section className="mb-14">
        <h2 className="font-heading text-lg font-semibold text-foreground mb-6 text-center">
          Modules
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {MODULES.map(mod => (
            <ModuleCard key={mod.to} mod={mod} />
          ))}
        </div>
      </section>

      {/* Quick-start tips */}
      <section className="mb-14 rounded-lg border border-border bg-secondary/20 p-6">
        <h2 className="font-heading text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
          <Cpu className="h-4 w-4 text-primary" /> Getting Started
        </h2>
        <div className="grid gap-4 sm:grid-cols-3 text-xs text-muted-foreground leading-relaxed">
          <div>
            <p className="font-semibold text-foreground mb-1">1. Build your parts library</p>
            <p>
              Start with the <strong>Component Librarian</strong> — upload datasheets for the parts
              on your board. AI extracts all key parameters and saves them to a searchable library
              that other modules reference.
            </p>
          </div>
          <div>
            <p className="font-semibold text-foreground mb-1">2. Design & constrain</p>
            <p>
              Use the <strong>Block Diagram Builder</strong> to map your system architecture, then
              define signal-integrity rules in the <strong>SI/PI Constraint Editor</strong>.
              Check your FPGA pin map with the <strong>FPGA I/O Bridge</strong>.
            </p>
          </div>
          <div>
            <p className="font-semibold text-foreground mb-1">3. Verify & export</p>
            <p>
              Run a <strong>BOM Analyzer</strong> audit for lifecycle and radiation risk.
              Upload your netlist to <strong>Schematic DRC</strong> for a full rule check.
              Every module exports Xpedition-ready scripts.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
