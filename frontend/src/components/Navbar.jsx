import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Satellite, Menu, X } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/',              label: 'Librarian',    sublabel: 'Phase 1' },
  { to: '/fpga',          label: 'FPGA Bridge',  sublabel: 'Phase 2' },
  { to: '/constraints',   label: 'SI/PI Constr.', sublabel: 'Phase 3' },
  { to: '/block-diagram', label: 'Block Diagram', sublabel: 'Phase 4' },
  { to: '/com',           label: 'COM Analysis', sublabel: 'Phase 5' },
  { to: '/bom',           label: 'BOM Analyzer', sublabel: 'Phase 6' },
  { to: '/drc',           label: 'Schematic DRC', sublabel: 'Phase 7' },
]

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between">

          {/* Logo */}
          <div className="flex items-center gap-3 shrink-0">
            <Satellite className="h-6 w-6 text-primary shrink-0" />
            <div>
              <p className="font-heading font-bold text-sm text-foreground leading-tight">
                GDMS Space Hardware Assistant
              </p>
              <p className="text-xs text-muted-foreground uppercase tracking-widest hidden sm:block">
                Digital Hardware Engineering
              </p>
            </div>
          </div>

          {/* Desktop nav — hidden below 1200px */}
          <div className="hidden xl:flex items-center gap-0.5">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  [
                    'px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary',
                  ].join(' ')
                }
              >
                {item.label}
                <span className="ml-1 text-xs opacity-60">{item.sublabel}</span>
              </NavLink>
            ))}
          </div>

          {/* Hamburger button — shown below 1200px */}
          <button
            className="xl:hidden p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle navigation menu"
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div className="xl:hidden border-t border-border bg-card/95 backdrop-blur">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 py-3 grid grid-cols-2 gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  [
                    'flex items-center justify-between px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary',
                  ].join(' ')
                }
              >
                <span>{item.label}</span>
                <span className="text-xs opacity-50 ml-2">{item.sublabel}</span>
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </nav>
  )
}
