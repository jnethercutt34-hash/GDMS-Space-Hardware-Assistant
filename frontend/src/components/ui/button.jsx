import { cloneElement, Children } from 'react'

const BASE =
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2'

const VARIANTS = {
  default:     'bg-primary text-primary-foreground hover:bg-primary/90',
  outline:     'border border-border bg-transparent hover:bg-secondary text-foreground',
  ghost:       'hover:bg-secondary text-foreground',
  destructive: 'bg-destructive text-white hover:bg-destructive/90',
}

export function Button({ className = '', variant = 'default', asChild = false, children, ...props }) {
  const cls = `${BASE} ${VARIANTS[variant] ?? VARIANTS.default} ${className}`

  if (asChild) {
    const child = Children.only(children)
    return cloneElement(child, {
      className: `${cls} ${child.props.className ?? ''}`.trim(),
      ...props,
    })
  }

  return (
    <button className={cls} {...props}>
      {children}
    </button>
  )
}
