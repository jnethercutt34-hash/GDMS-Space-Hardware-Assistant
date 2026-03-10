export function Badge({ className = '', variant = 'default', children, ...props }) {
  const variants = {
    default:   'border-transparent bg-primary text-primary-foreground',
    secondary: 'border-transparent bg-secondary text-secondary-foreground',
    outline:   'text-foreground border-border',
  }
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors ${variants[variant] ?? variants.default} ${className}`}
      {...props}
    >
      {children}
    </span>
  )
}
