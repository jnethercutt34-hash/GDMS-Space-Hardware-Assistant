/**
 * SectionLabel — step heading used in every module workflow.
 *
 * Props:
 *   icon  – React element (Lucide icon, already sized)
 *   step  – optional step number (omit to hide "Step N —" prefix)
 *   label – text description
 */
export default function SectionLabel({ icon, step, label }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="text-primary">{icon}</span>
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        {step ? `Step ${step} \u2014 ` : ''}{label}
      </p>
    </div>
  )
}
