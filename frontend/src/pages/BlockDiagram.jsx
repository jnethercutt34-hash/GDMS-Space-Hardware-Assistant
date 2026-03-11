import { useState, useEffect, useCallback, useRef } from 'react'
import { Boxes, Plus, Cpu, Trash2, Download, Save, Sparkles, Link2, X } from 'lucide-react'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { downloadBlob } from '../lib/downloadBlob'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_COLORS = {
  FPGA:      'bg-violet-500/20 text-violet-400 border-violet-500/30',
  Memory:    'bg-blue-500/20 text-blue-400 border-blue-500/30',
  Power:     'bg-amber-500/20 text-amber-400 border-amber-500/30',
  Connector: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  Processor: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  Optics:    'bg-pink-500/20 text-pink-400 border-pink-500/30',
  Custom:    'bg-gray-500/20 text-gray-400 border-gray-500/30',
}

const CATEGORIES = Object.keys(CATEGORY_COLORS)

const BLOCK_W = 160
const BLOCK_H_BASE = 90  // minimum height; grows with port count
const PORT_SPACING = 16
const PORT_DOT_R = 5

/** Calculate actual block height based on port count. */
function blockHeight(block) {
  const portCount = Math.max(
    (block.ports || []).filter(p => p.direction === 'IN' || p.direction === 'BIDIR').length,
    (block.ports || []).filter(p => p.direction === 'OUT' || p.direction === 'BIDIR').length,
  )
  return Math.max(BLOCK_H_BASE, 40 + portCount * PORT_SPACING)
}

/** Get the absolute (x, y) for a port dot on a block. */
function portPosition(block, port) {
  const h = blockHeight(block)
  const isLeft = port.direction === 'IN'
  const isRight = port.direction === 'OUT'
  // BIDIR ports appear on both sides — we place them on the left by convention
  // but also allow connecting from the right.
  const side = isRight ? 'right' : 'left'

  // Separate ports by side
  const portsOnSide = (block.ports || []).filter(p =>
    side === 'right' ? p.direction === 'OUT' : (p.direction === 'IN' || p.direction === 'BIDIR')
  )
  const idx = portsOnSide.findIndex(p => p.id === port.id)
  if (idx < 0) {
    // fallback: put bidir on right side check
    const rightPorts = (block.ports || []).filter(p => p.direction === 'OUT' || p.direction === 'BIDIR')
    const ridx = rightPorts.findIndex(p => p.id === port.id)
    if (ridx >= 0) {
      const startY = (h - rightPorts.length * PORT_SPACING) / 2 + PORT_SPACING / 2
      return { x: (block.x || 0) + BLOCK_W, y: (block.y || 0) + startY + ridx * PORT_SPACING, side: 'right' }
    }
    return { x: block.x || 0, y: (block.y || 0) + h / 2, side: 'left' }
  }
  const startY = (h - portsOnSide.length * PORT_SPACING) / 2 + PORT_SPACING / 2
  const px = side === 'right' ? (block.x || 0) + BLOCK_W : (block.x || 0)
  const py = (block.y || 0) + startY + idx * PORT_SPACING
  return { x: px, y: py, side }
}

// ---------------------------------------------------------------------------
// SVG connection overlay
// ---------------------------------------------------------------------------

function ConnectionLines({ blocks, connections, wiringFrom, mousePos, onDeleteConnection }) {
  return (
    <svg
      className="absolute inset-0 pointer-events-none"
      style={{ width: '100%', height: '100%', overflow: 'visible' }}
    >
      <defs>
        <marker id="arrowhead" markerWidth="7" markerHeight="5" refX="6" refY="2.5" orient="auto">
          <polygon points="0 0, 7 2.5, 0 5" fill="#6366f1" opacity="0.7" />
        </marker>
        <marker id="arrowhead-temp" markerWidth="7" markerHeight="5" refX="6" refY="2.5" orient="auto">
          <polygon points="0 0, 7 2.5, 0 5" fill="#f59e0b" opacity="0.6" />
        </marker>
      </defs>

      {/* Existing connections */}
      {connections?.map(conn => {
        const srcBlock = blocks?.find(b => b.id === conn.source_block_id)
        const tgtBlock = blocks?.find(b => b.id === conn.target_block_id)
        if (!srcBlock || !tgtBlock) return null

        // Use port positions if available, else fallback to block center-edge
        const srcPort = srcBlock.ports?.find(p => p.id === conn.source_port_id)
        const tgtPort = tgtBlock.ports?.find(p => p.id === conn.target_port_id)

        let x1, y1, x2, y2
        if (srcPort) {
          const pos = portPosition(srcBlock, srcPort)
          x1 = pos.x; y1 = pos.y
        } else {
          x1 = (srcBlock.x || 0) + BLOCK_W
          y1 = (srcBlock.y || 0) + blockHeight(srcBlock) / 2
        }
        if (tgtPort) {
          const pos = portPosition(tgtBlock, tgtPort)
          x2 = pos.x; y2 = pos.y
        } else {
          x2 = tgtBlock.x || 0
          y2 = (tgtBlock.y || 0) + blockHeight(tgtBlock) / 2
        }

        const dx = Math.max(Math.abs(x2 - x1) * 0.5, 60)
        const cx1 = x1 + dx
        const cx2 = x2 - dx
        const midX = (x1 + x2) / 2
        const midY = (y1 + y2) / 2

        return (
          <g key={conn.id}>
            <path
              d={`M ${x1} ${y1} C ${cx1} ${y1} ${cx2} ${y2} ${x2} ${y2}`}
              stroke="#6366f1"
              strokeWidth={1.5}
              fill="none"
              strokeOpacity={0.6}
              markerEnd="url(#arrowhead)"
            />
            {/* Invisible wider hit area for delete on click */}
            <path
              d={`M ${x1} ${y1} C ${cx1} ${y1} ${cx2} ${y2} ${x2} ${y2}`}
              stroke="transparent"
              strokeWidth={12}
              fill="none"
              className="pointer-events-auto cursor-pointer"
              onClick={e => {
                e.stopPropagation()
                onDeleteConnection?.(conn.id)
              }}
            />
            {conn.signal_name && (
              <text
                x={midX}
                y={midY - 5}
                fill="#a5b4fc"
                fontSize={9}
                textAnchor="middle"
                fontFamily="monospace"
              >
                {conn.signal_name}
              </text>
            )}
          </g>
        )
      })}

      {/* Temporary wiring line */}
      {wiringFrom && mousePos && (() => {
        const x1 = wiringFrom.x
        const y1 = wiringFrom.y
        const x2 = mousePos.x
        const y2 = mousePos.y
        const dx = Math.max(Math.abs(x2 - x1) * 0.4, 40)
        return (
          <path
            d={`M ${x1} ${y1} C ${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}`}
            stroke="#f59e0b"
            strokeWidth={2}
            fill="none"
            strokeDasharray="6 3"
            strokeOpacity={0.7}
            markerEnd="url(#arrowhead-temp)"
          />
        )
      })()}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Port dot (clickable)
// ---------------------------------------------------------------------------

function PortDot({ x, y, port, isWiringSource, isWiringCandidate, onPortClick }) {
  const color = isWiringSource
    ? '#f59e0b'
    : isWiringCandidate
      ? '#22c55e'
      : port.direction === 'IN'
        ? '#4ade80'
        : port.direction === 'OUT'
          ? '#f87171'
          : '#60a5fa'

  return (
    <g
      className="cursor-crosshair"
      style={{ pointerEvents: 'auto' }}
      onClick={e => {
        e.stopPropagation()
        onPortClick?.(port)
      }}
    >
      <circle cx={x} cy={y} r={PORT_DOT_R + 4} fill="transparent" />
      <circle
        cx={x} cy={y} r={PORT_DOT_R}
        fill={color}
        fillOpacity={0.8}
        stroke={color}
        strokeWidth={isWiringSource || isWiringCandidate ? 2 : 1}
        strokeOpacity={0.4}
      />
    </g>
  )
}

// ---------------------------------------------------------------------------
// Block tile (draggable, with port dots)
// ---------------------------------------------------------------------------

function BlockTile({ block, onMouseDown, selected, wiringFrom, onPortClick }) {
  const colorClass = CATEGORY_COLORS[block.category] || CATEGORY_COLORS.Custom
  const h = blockHeight(block)

  return (
    <div
      className="absolute select-none"
      style={{ left: block.x || 0, top: block.y || 0, width: BLOCK_W, height: h }}
    >
      {/* Block card body — drag handle */}
      <div
        className={`rounded-lg border px-3 py-2 shadow-md transition-shadow h-full ${colorClass} ${
          selected ? 'ring-2 ring-primary' : ''
        }`}
        style={{ cursor: wiringFrom ? 'default' : 'grab' }}
        onMouseDown={e => {
          if (wiringFrom) return // don't drag while wiring
          onMouseDown(e, block.id)
        }}
      >
        <div className="flex items-center gap-1.5 mb-1">
          <Cpu className="h-3 w-3 shrink-0" />
          <span className="text-xs font-semibold truncate">{block.label}</span>
        </div>
        {block.part_number && (
          <p className="text-[10px] opacity-70 truncate">{block.part_number}</p>
        )}
        <Badge variant="outline" className="text-[9px] mt-1">
          {block.category}
        </Badge>
        {/* Port labels (inside block) */}
        {block.ports?.length > 0 && (
          <div className="mt-1.5 space-y-0.5">
            {block.ports.slice(0, 6).map(p => (
              <div key={p.id} className="text-[9px] opacity-60 flex items-center gap-1">
                <span
                  className={
                    p.direction === 'IN'  ? 'text-green-400' :
                    p.direction === 'OUT' ? 'text-red-400'   : 'text-blue-400'
                  }
                >
                  {p.direction === 'IN' ? '→' : p.direction === 'OUT' ? '←' : '↔'}
                </span>
                <span className="truncate">
                  {p.label}{p.bus_width > 1 ? `[${p.bus_width}]` : ''}
                </span>
              </div>
            ))}
            {block.ports.length > 6 && (
              <p className="text-[9px] opacity-40">+{block.ports.length - 6} more</p>
            )}
          </div>
        )}
      </div>

      {/* Port dots (SVG overlay on block — outside the card's clip) */}
      <svg
        className="absolute inset-0 pointer-events-none overflow-visible"
        style={{ width: BLOCK_W, height: h }}
      >
        {block.ports?.map(port => {
          const pos = portPosition(block, port)
          // Translate to block-local coords
          const lx = pos.x - (block.x || 0)
          const ly = pos.y - (block.y || 0)
          const isSource = wiringFrom?.portId === port.id && wiringFrom?.blockId === block.id
          const isCandidate = wiringFrom && wiringFrom.blockId !== block.id
          return (
            <PortDot
              key={port.id}
              x={lx}
              y={ly}
              port={port}
              isWiringSource={isSource}
              isWiringCandidate={isCandidate}
              onPortClick={onPortClick ? () => onPortClick(block, port) : undefined}
            />
          )
        })}
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Add-block form
// ---------------------------------------------------------------------------

function AddBlockForm({ onAdd }) {
  const [label, setLabel] = useState('')
  const [category, setCategory] = useState('Custom')
  const [partNumber, setPartNumber] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!label.trim()) return
    onAdd({ label: label.trim(), category, part_number: partNumber.trim() || null })
    setLabel('')
    setPartNumber('')
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 rounded-lg border border-border bg-secondary/40 p-3 space-y-2">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest flex items-center gap-1">
        <Plus className="h-3 w-3" /> Add Block
      </p>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded-md border border-border bg-secondary px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground"
          placeholder="Block label (e.g. Zynq UltraScale+)…"
          value={label}
          onChange={e => setLabel(e.target.value)}
          required
        />
        <select
          className="rounded-md border border-border bg-secondary px-2 py-1.5 text-xs text-foreground"
          value={category}
          onChange={e => setCategory(e.target.value)}
        >
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded-md border border-border bg-secondary px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground"
          placeholder="Part number (optional)…"
          value={partNumber}
          onChange={e => setPartNumber(e.target.value)}
        />
        <Button type="submit" size="sm">
          <Plus className="h-3 w-3" />
        </Button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Add-port form (inline in selected block sidebar)
// ---------------------------------------------------------------------------

function AddPortForm({ onAdd }) {
  const [label, setLabel] = useState('')
  const [direction, setDirection] = useState('BIDIR')

  const handleSubmit = e => {
    e.preventDefault()
    if (!label.trim()) return
    onAdd({ label: label.trim(), direction })
    setLabel('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-1 mt-2">
      <input
        className="flex-1 rounded-md border border-border bg-secondary px-2 py-1 text-[10px] text-foreground placeholder:text-muted-foreground"
        placeholder="Port name…"
        value={label}
        onChange={e => setLabel(e.target.value)}
        required
      />
      <select
        className="rounded-md border border-border bg-secondary px-1 py-1 text-[10px] text-foreground"
        value={direction}
        onChange={e => setDirection(e.target.value)}
      >
        <option value="IN">IN</option>
        <option value="OUT">OUT</option>
        <option value="BIDIR">BI</option>
      </select>
      <Button type="submit" size="sm" className="h-6 px-1.5">
        <Plus className="h-2.5 w-2.5" />
      </Button>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Signal name modal
// ---------------------------------------------------------------------------

function SignalNameModal({ onConfirm, onCancel }) {
  const [name, setName] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSubmit = e => {
    e.preventDefault()
    onConfirm(name.trim() || null)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <form
        onSubmit={handleSubmit}
        className="rounded-lg border border-border bg-background p-4 shadow-xl w-80 space-y-3"
      >
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Link2 className="h-4 w-4 text-primary" /> New Connection
        </h3>
        <p className="text-xs text-muted-foreground">
          Enter a signal name for this connection (optional).
        </p>
        <input
          ref={inputRef}
          className="w-full rounded-md border border-border bg-secondary px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground"
          placeholder="Signal name (e.g. SPI_MOSI, DDR4_DQ[0:7])…"
          value={name}
          onChange={e => setName(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" size="sm">
            <Link2 className="mr-1 h-3 w-3" /> Connect
          </Button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function BlockDiagram() {
  const [diagrams, setDiagrams]       = useState([])
  const [current, setCurrent]         = useState(null)
  const [isLoading, setIsLoading]     = useState(false)
  const [error, setError]             = useState(null)
  const [newName, setNewName]         = useState('')
  const [genPartNums, setGenPartNums] = useState('')
  const [selectedBlockId, setSelectedBlockId] = useState(null)

  // Drag state
  const draggingRef = useRef(null)
  const canvasRef   = useRef(null)

  // Wiring state
  const [wiringFrom, setWiringFrom]   = useState(null) // { blockId, portId, x, y }
  const [mousePos, setMousePos]       = useState(null)  // { x, y } in canvas coords
  const [pendingWire, setPendingWire] = useState(null)  // { source, target } — awaiting signal name

  // ---------------------------------------------------------------------------
  // API helpers
  // ---------------------------------------------------------------------------

  const loadDiagrams = useCallback(async () => {
    try {
      const res = await fetch('/api/diagrams')
      if (res.ok) setDiagrams(await res.json())
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadDiagrams() }, [loadDiagrams])

  const loadDiagram = async (id) => {
    try {
      const res = await fetch(`/api/diagrams/${id}`)
      if (res.ok) setCurrent(await res.json())
    } catch { /* ignore */ }
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/diagrams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim(), blocks: [], connections: [] }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Create failed')
      const data = await res.json()
      setCurrent(data)
      setNewName('')
      loadDiagrams()
    } catch (e) { setError(e.message) } finally { setIsLoading(false) }
  }

  const handleDelete = async (id) => {
    try {
      await fetch(`/api/diagrams/${id}`, { method: 'DELETE' })
      if (current?.id === id) setCurrent(null)
      loadDiagrams()
    } catch { /* ignore */ }
  }

  const handleSave = async () => {
    if (!current) return
    setIsLoading(true)
    try {
      const res = await fetch(`/api/diagrams/${current.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(current),
      })
      if (res.ok) {
        setCurrent(await res.json())
        loadDiagrams()
      }
    } catch { /* ignore */ } finally { setIsLoading(false) }
  }

  const handleGenerate = async () => {
    const pns = genPartNums.split(',').map(s => s.trim()).filter(Boolean)
    if (!pns.length) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/diagrams/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ part_numbers: pns, diagram_name: 'AI Generated' }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Generation failed')
      }
      const data = await res.json()
      setCurrent(data)
      loadDiagrams()
    } catch (e) { setError(e.message) } finally { setIsLoading(false) }
  }

  const handleExport = async (format) => {
    if (!current) return
    try {
      const res = await fetch(`/api/diagrams/${current.id}/export-netlist?format=${format}`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      downloadBlob(blob, format === 'csv' ? 'netlist_seed.csv' : 'xpedition_netlist_seed.py')
    } catch (e) { setError(e.message) }
  }

  // ---------------------------------------------------------------------------
  // Add block manually
  // ---------------------------------------------------------------------------

  const handleAddBlock = ({ label, category, part_number }) => {
    const id = `blk_${Date.now()}`
    const count = current?.blocks?.length || 0
    const col = count % 4
    const row = Math.floor(count / 4)
    const x = 16 + col * (BLOCK_W + 24)
    const y = 16 + row * (BLOCK_H_BASE + 24)
    setCurrent(prev => ({
      ...prev,
      blocks: [
        ...(prev.blocks || []),
        { id, label, category, part_number, x, y, ports: [] },
      ],
    }))
  }

  const handleDeleteBlock = (blockId) => {
    setCurrent(prev => ({
      ...prev,
      blocks: (prev.blocks || []).filter(b => b.id !== blockId),
      connections: (prev.connections || []).filter(
        c => c.source_block_id !== blockId && c.target_block_id !== blockId
      ),
    }))
    if (selectedBlockId === blockId) setSelectedBlockId(null)
  }

  // ---------------------------------------------------------------------------
  // Add port to selected block
  // ---------------------------------------------------------------------------

  const handleAddPort = ({ label, direction }) => {
    if (!selectedBlockId || !current) return
    const portId = `port_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
    setCurrent(prev => ({
      ...prev,
      blocks: (prev.blocks || []).map(b =>
        b.id === selectedBlockId
          ? { ...b, ports: [...(b.ports || []), { id: portId, label, direction, bus_width: 1 }] }
          : b
      ),
    }))
  }

  // ---------------------------------------------------------------------------
  // Drag-and-drop
  // ---------------------------------------------------------------------------

  const handleBlockMouseDown = useCallback((e, blockId) => {
    e.preventDefault()
    e.stopPropagation()
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const block = current?.blocks?.find(b => b.id === blockId)
    if (!block) return
    draggingRef.current = {
      id: blockId,
      offsetX: e.clientX - rect.left - (block.x || 0),
      offsetY: e.clientY - rect.top - (block.y || 0),
    }
    setSelectedBlockId(blockId)
  }, [current])

  const handleCanvasMouseMove = useCallback((e) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()

    // Drag block
    if (draggingRef.current) {
      const x = Math.max(0, e.clientX - rect.left - draggingRef.current.offsetX)
      const y = Math.max(0, e.clientY - rect.top - draggingRef.current.offsetY)
      const id = draggingRef.current.id
      setCurrent(prev => ({
        ...prev,
        blocks: (prev.blocks || []).map(b => b.id === id ? { ...b, x, y } : b),
      }))
      return
    }

    // Wiring: track mouse for temp line
    if (wiringFrom) {
      setMousePos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
    }
  }, [wiringFrom])

  const handleCanvasMouseUp = useCallback(() => {
    draggingRef.current = null
  }, [])

  // Release drag if mouse leaves window
  useEffect(() => {
    const onUp = () => { draggingRef.current = null }
    window.addEventListener('mouseup', onUp)
    return () => window.removeEventListener('mouseup', onUp)
  }, [])

  // ESC to cancel wiring
  useEffect(() => {
    const onKey = e => {
      if (e.key === 'Escape') {
        setWiringFrom(null)
        setMousePos(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // ---------------------------------------------------------------------------
  // Port-to-port wiring
  // ---------------------------------------------------------------------------

  const handlePortClick = useCallback((block, port) => {
    if (!wiringFrom) {
      // Start wiring
      const pos = portPosition(block, port)
      setWiringFrom({ blockId: block.id, portId: port.id, x: pos.x, y: pos.y })
      setSelectedBlockId(block.id)
      return
    }

    // Complete wiring
    if (wiringFrom.blockId === block.id) {
      // Can't connect to same block — cancel
      setWiringFrom(null)
      setMousePos(null)
      return
    }

    setPendingWire({
      source: { blockId: wiringFrom.blockId, portId: wiringFrom.portId },
      target: { blockId: block.id, portId: port.id },
    })
    setWiringFrom(null)
    setMousePos(null)
  }, [wiringFrom])

  const handleWireConfirm = (signalName) => {
    if (!pendingWire || !current) return
    const connId = `conn_${Date.now()}`
    setCurrent(prev => ({
      ...prev,
      connections: [
        ...(prev.connections || []),
        {
          id: connId,
          source_block_id: pendingWire.source.blockId,
          source_port_id: pendingWire.source.portId,
          target_block_id: pendingWire.target.blockId,
          target_port_id: pendingWire.target.portId,
          signal_name: signalName || null,
          net_class: null,
        },
      ],
    }))
    setPendingWire(null)
  }

  const handleWireCancel = () => {
    setPendingWire(null)
  }

  const handleDeleteConnection = (connId) => {
    setCurrent(prev => ({
      ...prev,
      connections: (prev.connections || []).filter(c => c.id !== connId),
    }))
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div>
      {/* Signal name modal */}
      {pendingWire && (
        <SignalNameModal onConfirm={handleWireConfirm} onCancel={handleWireCancel} />
      )}

      {/* Hero */}
      <section className="mb-14">
        <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
          Step 2 · Block Diagram Builder
        </Badge>
        <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          System Block Diagram
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Visually construct or AI-generate system-level block diagrams. Drag blocks to
          reposition, click ports to wire connections, then export as a structured Xpedition netlist seed.
        </p>
      </section>

      {error && (
        <div className="mb-6 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 flex items-center justify-between">
          <p className="text-xs text-destructive">{error}</p>
          <button onClick={() => setError(null)} className="text-xs text-destructive/60 hover:text-destructive ml-4">✕</button>
        </div>
      )}

      {/* Wiring mode indicator */}
      {wiringFrom && (
        <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 flex items-center justify-between">
          <p className="text-xs text-amber-400 flex items-center gap-2">
            <Link2 className="h-3 w-3" />
            <span><strong>Wiring mode</strong> — click a port on another block to connect, or press <kbd className="px-1 py-0.5 rounded bg-secondary text-[10px]">Esc</kbd> to cancel</span>
          </p>
          <button
            onClick={() => { setWiringFrom(null); setMousePos(null) }}
            className="text-amber-400/60 hover:text-amber-400"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-14">
        {/* Sidebar */}
        <div className="space-y-4">
          {/* Diagram list */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Boxes className="h-4 w-4 text-primary" /> Diagrams
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-md border border-border bg-secondary px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground"
                  placeholder="New diagram name…"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleCreate()}
                />
                <Button size="sm" onClick={handleCreate} disabled={isLoading}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {diagrams.map(d => (
                <div
                  key={d.id}
                  className={`flex items-center justify-between rounded-md px-2 py-1.5 text-xs cursor-pointer transition-colors ${
                    current?.id === d.id
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-secondary'
                  }`}
                  onClick={() => loadDiagram(d.id)}
                >
                  <span className="truncate">{d.name}</span>
                  <div className="flex items-center gap-1 shrink-0 ml-2">
                    <span className="text-muted-foreground/60">{d.block_count}B</span>
                    <button
                      onClick={e => { e.stopPropagation(); handleDelete(d.id) }}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
              {diagrams.length === 0 && (
                <p className="text-xs text-muted-foreground/60 text-center py-2">No diagrams yet</p>
              )}
            </CardContent>
          </Card>

          {/* AI Generate */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" /> AI Generate
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <input
                className="w-full rounded-md border border-border bg-secondary px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground"
                placeholder="Part numbers (comma-separated)…"
                value={genPartNums}
                onChange={e => setGenPartNums(e.target.value)}
              />
              <Button size="sm" onClick={handleGenerate} disabled={isLoading} className="w-full">
                <Sparkles className="mr-1 h-3 w-3" /> Generate
              </Button>
            </CardContent>
          </Card>

          {/* Selected block info + port management */}
          {selectedBlockId && current && (() => {
            const blk = current.blocks?.find(b => b.id === selectedBlockId)
            if (!blk) return null
            return (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center justify-between">
                    <span>Selected Block</span>
                    <button
                      onClick={() => handleDeleteBlock(selectedBlockId)}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-xs text-muted-foreground">
                  <p><span className="text-foreground font-medium">Label:</span> {blk.label}</p>
                  <p><span className="text-foreground font-medium">Category:</span> {blk.category}</p>
                  {blk.part_number && (
                    <p><span className="text-foreground font-medium">PN:</span> {blk.part_number}</p>
                  )}
                  <p><span className="text-foreground font-medium">Position:</span> ({Math.round(blk.x || 0)}, {Math.round(blk.y || 0)})</p>
                  <p><span className="text-foreground font-medium">Ports:</span> {blk.ports?.length || 0}</p>

                  {/* Port list */}
                  {blk.ports?.length > 0 && (
                    <div className="mt-2 space-y-0.5">
                      {blk.ports.map(p => (
                        <div key={p.id} className="flex items-center justify-between text-[10px]">
                          <span className="flex items-center gap-1">
                            <span className={
                              p.direction === 'IN' ? 'text-green-400' :
                              p.direction === 'OUT' ? 'text-red-400' : 'text-blue-400'
                            }>
                              {p.direction === 'IN' ? '→' : p.direction === 'OUT' ? '←' : '↔'}
                            </span>
                            {p.label}
                          </span>
                          <button
                            className="text-muted-foreground/40 hover:text-destructive"
                            onClick={() => {
                              setCurrent(prev => ({
                                ...prev,
                                blocks: (prev.blocks || []).map(b =>
                                  b.id === selectedBlockId
                                    ? { ...b, ports: (b.ports || []).filter(pp => pp.id !== p.id) }
                                    : b
                                ),
                                connections: (prev.connections || []).filter(
                                  c => c.source_port_id !== p.id && c.target_port_id !== p.id
                                ),
                              }))
                            }}
                          >
                            <X className="h-2.5 w-2.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add port form */}
                  <AddPortForm onAdd={handleAddPort} />
                </CardContent>
              </Card>
            )
          })()}
        </div>

        {/* Canvas */}
        <div className="lg:col-span-2">
          {current ? (
            <Card>
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-sm">{current.name}</CardTitle>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={handleSave} disabled={isLoading}>
                    <Save className="mr-1 h-3 w-3" /> Save
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleExport('script')}>
                    <Download className="mr-1 h-3 w-3" /> Script
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleExport('csv')}>
                    <Download className="mr-1 h-3 w-3" /> CSV
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {/* Drag canvas with SVG overlay */}
                <div
                  ref={canvasRef}
                  className="relative rounded-lg border border-border bg-secondary/30 overflow-auto"
                  style={{ minHeight: 420, height: 520 }}
                  onMouseMove={handleCanvasMouseMove}
                  onMouseUp={handleCanvasMouseUp}
                  onClick={() => {
                    if (!wiringFrom) setSelectedBlockId(null)
                  }}
                >
                  {/* Dot-grid background */}
                  <svg
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <defs>
                      <pattern id="dotgrid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
                        <circle cx="1" cy="1" r="0.8" fill="currentColor" className="text-border/40" />
                      </pattern>
                    </defs>
                    <rect width="100%" height="100%" fill="url(#dotgrid)" />
                  </svg>

                  {/* SVG connection lines + temp wiring line */}
                  <ConnectionLines
                    blocks={current.blocks}
                    connections={current.connections}
                    wiringFrom={wiringFrom}
                    mousePos={mousePos}
                    onDeleteConnection={handleDeleteConnection}
                  />

                  {/* Block tiles */}
                  {current.blocks?.length > 0 ? (
                    current.blocks.map(block => (
                      <BlockTile
                        key={block.id}
                        block={block}
                        selected={selectedBlockId === block.id}
                        onMouseDown={handleBlockMouseDown}
                        wiringFrom={wiringFrom}
                        onPortClick={handlePortClick}
                      />
                    ))
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-muted-foreground/40">
                      <div className="text-center">
                        <Boxes className="h-10 w-10 mx-auto mb-2" />
                        <p className="text-sm">No blocks yet — use the form below or AI Generate</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Add block form (inline under canvas) */}
                <AddBlockForm onAdd={handleAddBlock} />

                {/* Connections table */}
                {current.connections?.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-2">
                      Connections ({current.connections.length})
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-border text-muted-foreground">
                            <th className="text-left py-1 px-2">Signal</th>
                            <th className="text-left py-1 px-2">Source</th>
                            <th className="text-left py-1 px-2">Target</th>
                            <th className="text-left py-1 px-2">Net Class</th>
                            <th className="text-right py-1 px-2 w-8"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {current.connections.map(c => {
                            const srcBlock = current.blocks?.find(b => b.id === c.source_block_id)
                            const tgtBlock = current.blocks?.find(b => b.id === c.target_block_id)
                            const srcPort  = srcBlock?.ports?.find(p => p.id === c.source_port_id)
                            const tgtPort  = tgtBlock?.ports?.find(p => p.id === c.target_port_id)
                            return (
                              <tr key={c.id} className="border-b border-border/50">
                                <td className="py-1 px-2 text-foreground">{c.signal_name || '—'}</td>
                                <td className="py-1 px-2 text-muted-foreground">
                                  {srcBlock?.label || '?'}
                                  {srcPort && <span className="text-muted-foreground/50">.{srcPort.label}</span>}
                                </td>
                                <td className="py-1 px-2 text-muted-foreground">
                                  {tgtBlock?.label || '?'}
                                  {tgtPort && <span className="text-muted-foreground/50">.{tgtPort.label}</span>}
                                </td>
                                <td className="py-1 px-2">
                                  {c.net_class
                                    ? <Badge variant="outline" className="text-[9px]">{c.net_class}</Badge>
                                    : '—'}
                                </td>
                                <td className="py-1 px-2 text-right">
                                  <button
                                    onClick={() => handleDeleteConnection(c.id)}
                                    className="text-muted-foreground/40 hover:text-destructive"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-20 text-center">
                <Boxes className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">Select or create a diagram to get started</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
