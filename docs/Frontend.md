Update this app's frontend to match the following design system and UI conventions exactly.                                                  
                                                                                                                                               
  ## Tech Stack   
  - Next.js (App Router), React, TypeScript
  - Tailwind CSS v4
  - shadcn/ui components (Card, Badge, Button, Input, Tabs, etc.) via Radix UI
  - lucide-react for icons
  - Fonts: Inter (body) + Space Grotesk (headings) via next/font/google

  ## Theme — "Tactical Aerospace" Always-Dark

  Force dark mode at the html element level: `<html className="dark">`. Do NOT use a light/dark toggle.

  Apply these CSS custom properties in globals.css:

  ```css
  :root, .dark {
    --background:         hsl(222 47% 4%);   /* Deep Void */
    --foreground:         hsl(210 40% 98%);
    --card:               hsl(222 47% 7%);
    --card-foreground:    hsl(210 40% 98%);
    --popover:            hsl(222 47% 7%);
    --popover-foreground: hsl(210 40% 98%);
    --primary:            hsl(217 91% 60%);  /* Mission Blue */
    --primary-foreground: hsl(222 47% 4%);
    --secondary:          hsl(222 47% 12%);
    --secondary-foreground: hsl(210 40% 98%);
    --muted:              hsl(222 47% 12%);
    --muted-foreground:   hsl(215 20% 55%);
    --accent:             hsl(262 80% 60%);  /* Intelligence Purple */
    --accent-foreground:  hsl(210 40% 98%);
    --destructive:        hsl(0 84% 60%);
    --border:             hsl(222 47% 15%);
    --input:              hsl(222 47% 15%);
    --ring:               hsl(217 91% 60%);
    --radius:             0.5rem;
  }

  Register fonts in globals.css @theme inline:
  --font-sans:    var(--font-inter);
  --font-heading: var(--font-space-grotesk);

  Add utility classes:
  .font-heading { font-family: var(--font-space-grotesk); }
  .font-body    { font-family: var(--font-inter); }

  Layout

  - body class: antialiased min-h-screen bg-background font-body
  - Persistent top <Navbar /> component across all pages
  - Page content: <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
  - Sections spaced with mb-14

  Typography Conventions

  - Page hero h1: font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl
  - Section h2: font-heading text-2xl font-semibold mb-1 text-foreground
  - Section subtitle: text-muted-foreground mb-6 text-sm
  - Body text: text-sm text-muted-foreground leading-relaxed
  - Stat labels: text-xs text-muted-foreground uppercase tracking-widest mb-1
  - Stat values: font-heading text-3xl font-bold (color varies by semantic: primary, accent, foreground, muted-foreground)

  Card Patterns

  Standard card grid layout:
  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <Card>
      <CardHeader>
        <CardTitle className="font-heading text-base">Title</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground leading-relaxed">...</p>
      </CardContent>
    </Card>
  </div>

  Clickable/linked cards:
  <Link href="..." className="block group">
    <Card className="hover:border-primary/50 transition-colors h-full">
      ...
      <p className="text-xs text-muted-foreground group-hover:text-primary transition-colors text-right pt-1">
        View details →
      </p>
    </Card>
  </Link>

  Badge Patterns

  - Primary accent: bg-primary/20 text-primary border-primary/30
  - Secondary/neutral: variant="secondary"
  - Violet/special: bg-violet-500/20 text-violet-400 border-violet-500/30
  - Amber/warning: bg-amber-500/20 text-amber-400 border-amber-500/30

  Inline Spec Chips (mini stat rows inside cards)

  <div className="grid grid-cols-3 gap-2 text-center">
    {specs.map(({ label, value }) => (
      <div key={label} className="rounded-md bg-secondary/30 px-2 py-1.5">
        <p className="text-xs text-muted-foreground uppercase tracking-widest leading-none mb-1">{label}</p>
        <p className="text-sm font-semibold text-foreground font-mono">{value}</p>
      </div>
    ))}
  </div>

  Callout / Highlight Boxes Inside Cards

  {/* Blue callout */}
  <div className="rounded-md border border-primary/20 bg-primary/5 px-3 py-2">
    <p className="text-xs text-primary font-semibold uppercase tracking-widest mb-0.5">Label</p>
    <p className="text-xs text-muted-foreground">Description</p>
  </div>

  {/* Green success/savings */}
  <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2">
    <p className="text-xs text-emerald-400 font-semibold uppercase tracking-widest mb-0.5">Label</p>
    <p className="text-xs text-muted-foreground">Description</p>
  </div>

  {/* Amber warning/special */}
  <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2">
    <p className="text-xs text-amber-400 font-semibold uppercase tracking-widest mb-0.5">Label</p>
    <p className="text-xs text-muted-foreground">Description</p>
  </div>

  Tag/Pill Chips

  {/* Primary blue chip */}
  <span className="inline-block rounded border border-primary/25 bg-primary/10 px-1.5 py-0.5 text-xs text-primary/80">
    Tag
  </span>

  {/* Neutral chip */}
  <span className="inline-block rounded border border-border bg-secondary/50 px-1.5 py-0.5 text-xs text-muted-foreground">
    Tag
  </span>

  Hero Section Pattern

  <section className="mb-14">
    <Badge className="mb-4 bg-primary/20 text-primary border-primary/30">
      Category · Subcategory
    </Badge>
    <h1 className="font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
      Page Title
    </h1>
    <p className="mt-4 max-w-2xl text-lg text-muted-foreground leading-relaxed">
      Subtitle description.
    </p>
    <div className="mt-6 flex flex-wrap gap-3">
      <Button asChild><Link href="/primary-action">Primary CTA →</Link></Button>
      <Button variant="outline" asChild><Link href="/secondary">Secondary</Link></Button>
    </div>
  </section>

  Summary Stats Bar (inside cards, at bottom)

  <div className="flex flex-wrap gap-8 border-t border-border pt-5">
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">Label</p>
      <p className="font-heading text-3xl font-bold text-primary">{value}</p>
    </div>
  </div>

  General Rules

  - Always dark — no light mode
  - Use font-heading (Space Grotesk) for all CardTitle, h1, h2, stat values
  - Use font-mono for numeric spec values inside chips
  - Borders: border-border (dim) or color-specific at /20–/30 opacity for callouts
  - Backgrounds: bg-secondary/30 for subtle fills, bg-primary/5–/10 for colored fills
  - Hover states: hover:border-primary/50, group-hover:text-primary with transition-colors
  - Spacing rhythm: mb-14 between sections, gap-4 in grids, space-y-3 inside card content
  - No light-mode fallbacks, no theme toggle, no .dark: variants needed
