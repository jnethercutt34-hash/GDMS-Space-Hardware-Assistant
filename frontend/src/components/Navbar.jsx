import { Satellite } from 'lucide-react'

const NAV_ITEMS = [
  { id: 'librarian', label: 'Component Librarian', sublabel: 'Phase 1' },
  { id: 'fpga',      label: 'FPGA I/O Bridge',     sublabel: 'Phase 2' },
]

export default function Navbar({ currentPage, setCurrentPage }) {
  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <Satellite className="h-6 w-6 text-primary shrink-0" />
            <div>
              <p className="font-heading font-bold text-sm text-foreground leading-tight">
                GDMS Space Hardware Assistant
              </p>
              <p className="text-xs text-muted-foreground uppercase tracking-widest">
                Digital Hardware Engineering
              </p>
            </div>
          </div>

          {/* Nav links */}
          <div className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const active = currentPage === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentPage(item.id)}
                  className={[
                    'px-4 py-2 rounded-md text-sm font-medium transition-colors',
                    active
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary',
                  ].join(' ')}
                >
                  {item.label}
                  <span
                    className={`ml-1.5 text-xs ${active ? 'text-primary/70' : 'text-muted-foreground/60'}`}
                  >
                    {item.sublabel}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}
