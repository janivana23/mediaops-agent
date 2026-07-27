import type { ReactNode } from 'react'

export function SectionHeading({
  icon,
  title,
  subtitle,
  action,
}: {
  icon: ReactNode
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className="section-head">
      <div className="section-head-main">
        <span className="section-icon" aria-hidden="true">
          {icon}
        </span>
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="section-subtitle">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="section-head-action">{action}</div>}
    </div>
  )
}
