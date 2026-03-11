import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Satellite, Menu, X } from 'lucide-react'

// Ordered by design flow: define → architect → stackup → constrain+COM → bridge → audit → verify
const NAV_ITEMS = [
  { to: '/librarian',      label: 'Librarian',       step: '1' },
  { to: '/block-diagram',  label: 'Block Diagram',   step: '2' },
  { to: '/stackup',        label: 'Stackup',         step: '3' },
  { to: '/constraints',    label: 'SI/PI Guide',     step: '4' },
  { to: '/fpga',           label: 'FPGA Bridge',     step: '5' },
  { to: '/bom',            label: 'BOM Analyzer',    step: '6' },
  { to: '/drc',            label: 'Schematic DRC',   step: '7' },
]

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between">

          {/* Logo — links to home */}
          <NavLink to="/" className="flex items-center gap-3 shrink-0 hover:opacity-80 transition-opacity">
            <Satellite className="h-6 w-6 text-primary shrink-0" />
            <div>
              <p className="font-heading font-bold text-sm text-foreground leading-tight">
                GDMS Space Hardware Assistant
              </p>
              <p className="text-xs text-muted-foreground uppercase tracking-widest hidden sm:block">
                Digital Hardware Engineering
              </p>
            </div>
          </NavLink>

          {/* Desktop nav */}
          <div className="hidden xl:flex items-center gap-0.5">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap flex items-center gap-1.5',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary',
                  ].join(' ')
                }
              >
                <span className="text-[9px] font-mono opacity-50">{item.step}</span>
                {item.label}
              </NavLink>
            ))}
          </div>

          {/* Hamburger */}
          <button
            className="xl:hidden p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle navigation menu"
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="xl:hidden border-t border-border bg-card/95 backdrop-blur">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 py-3 grid grid-cols-2 gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  [
                    'flex items-center gap-2 px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary',
                  ].join(' ')
                }
              >
                <span className="text-[9px] font-mono opacity-50">{item.step}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </nav>
  )
}
