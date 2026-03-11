import { useState } from 'react'
import { BookOpen, ChevronDown, ChevronRight, Lightbulb, AlertTriangle, CheckCircle, ArrowRight } from 'lucide-react'
import { Card, CardContent } from './ui/card'

/**
 * ModuleGuide — collapsible engineer's guide panel for each module.
 *
 * Props:
 *   title       — short guide title (e.g. "Component Librarian Guide")
 *   purpose     — 1-2 sentence plain-English explanation of what this module does
 *   workflow     — ordered array of { step, description } objects
 *   tips        — array of helpful tip strings
 *   warnings    — array of "watch out for" strings
 *   inputFormat — description of what files/data the module expects
 *   outputFormat — description of what the module produces
 */
export default function ModuleGuide({ title, purpose, workflow, tips, warnings, inputFormat, outputFormat }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <Card className="mb-8 border-primary/20 bg-primary/[0.02]">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-3 px-6 py-4 text-left transition-colors hover:bg-primary/5"
      >
        <BookOpen className="h-5 w-5 text-primary shrink-0" />
        <span className="flex-1 text-sm font-semibold text-foreground">{title}</span>
        <span className="text-xs text-primary font-medium uppercase tracking-widest mr-2">
          Engineer&apos;s Guide
        </span>
        {isOpen
          ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
          : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
      </button>

      {isOpen && (
        <CardContent className="pt-0 pb-6 px-6">
          <div className="border-t border-primary/10 pt-5 space-y-6">
            {/* Purpose */}
            <div>
              <SectionHeading icon={<Lightbulb className="h-4 w-4" />} label="What This Module Does" />
              <p className="text-sm text-muted-foreground leading-relaxed">{purpose}</p>
            </div>

            {/* Input / Output */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {inputFormat && (
                <div className="rounded-md border border-border bg-secondary/20 px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1.5">
                    📥 Input
                  </p>
                  <p className="text-sm text-muted-foreground leading-relaxed">{inputFormat}</p>
                </div>
              )}
              {outputFormat && (
                <div className="rounded-md border border-border bg-secondary/20 px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1.5">
                    📤 Output
                  </p>
                  <p className="text-sm text-muted-foreground leading-relaxed">{outputFormat}</p>
                </div>
              )}
            </div>

            {/* Step-by-step Workflow */}
            {workflow?.length > 0 && (
              <div>
                <SectionHeading icon={<ArrowRight className="h-4 w-4" />} label="Step-by-Step Workflow" />
                <ol className="space-y-2.5 ml-1">
                  {workflow.map(({ step, description }, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <span className="shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-primary/15 text-primary text-xs font-bold mt-0.5">
                        {i + 1}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-foreground">{step}</p>
                        <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">{description}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Tips */}
            {tips?.length > 0 && (
              <div>
                <SectionHeading icon={<CheckCircle className="h-4 w-4" />} label="Pro Tips" />
                <ul className="space-y-1.5">
                  {tips.map((tip, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <span className="text-green-400 shrink-0 mt-0.5">✓</span>
                      {tip}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Warnings */}
            {warnings?.length > 0 && (
              <div>
                <SectionHeading icon={<AlertTriangle className="h-4 w-4" />} label="Watch Out For" />
                <ul className="space-y-1.5">
                  {warnings.map((warning, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <span className="text-amber-400 shrink-0 mt-0.5">⚠</span>
                      {warning}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  )
}

function SectionHeading({ icon, label }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <span className="text-primary">{icon}</span>
      <p className="text-xs font-semibold uppercase tracking-widest text-primary">{label}</p>
    </div>
  )
}
