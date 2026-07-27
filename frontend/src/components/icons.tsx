// Minimal hand-rolled icon set — stroke-based, 20x20, inherits currentColor.
// No icon library dependency; kept small and purpose-built for this dashboard.
import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export function IconLayers(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3 2.5 8 12 13l9.5-5L12 3Z" />
      <path d="m2.5 13 9.5 5 9.5-5" />
      <path d="m2.5 18 9.5 5 9.5-5" opacity="0.5" />
    </svg>
  )
}

export function IconClock(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5.2l3.4 2" />
    </svg>
  )
}

export function IconCoins(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <ellipse cx="9" cy="7" rx="6.5" ry="3.5" />
      <path d="M2.5 7v6c0 1.93 2.91 3.5 6.5 3.5s6.5-1.57 6.5-3.5V7" />
      <path d="M2.5 13c0 1.93 2.91 3.5 6.5 3.5s6.5-1.57 6.5-3.5" />
      <path d="M14.8 6.2c2.65.53 4.7 1.87 4.7 3.8s-2.05 3.27-4.7 3.8" opacity="0.55" />
    </svg>
  )
}

export function IconWallet(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="2.5" y="6" width="19" height="13" rx="2.4" />
      <path d="M2.5 10h19" />
      <path d="M15.5 14.2h3.2" />
    </svg>
  )
}

export function IconCheckCircle(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.3 2.6 2.6L16.2 9" />
    </svg>
  )
}

export function IconBarChart(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M4 20V10" />
      <path d="M12 20V4" />
      <path d="M20 20v-6.5" />
      <path d="M2.5 20.5h19" opacity="0.5" />
    </svg>
  )
}

export function IconInbox(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M3 12.5 5.8 4h12.4l2.8 8.5" />
      <path d="M3 12.5v5.3c0 1.2 1 2.2 2.2 2.2h13.6c1.2 0 2.2-1 2.2-2.2v-5.3" />
      <path d="M3 12.5h5.2l1.2 2.4h5.2l1.2-2.4H21" />
    </svg>
  )
}

export function IconImage(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2.2" />
      <circle cx="8.5" cy="9.5" r="1.6" />
      <path d="m5 18 5.2-5.6a1.8 1.8 0 0 1 2.6.05L15 15.5" />
      <path d="m13.5 17-2.2-2.4a1.8 1.8 0 0 1 2.6-.05L18 18" />
    </svg>
  )
}

export function IconShieldCheck(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3.2 5 5.7v5.4c0 4.6 3 7.9 7 9.7 4-1.8 7-5.1 7-9.7V5.7L12 3.2Z" />
      <path d="m9 12 2.3 2.3L15.5 10" />
    </svg>
  )
}

export function IconRefresh(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M20 11a8 8 0 0 0-14.5-4.2M4 5v4.5h4.5" />
      <path d="M4 13a8 8 0 0 0 14.5 4.2M20 19v-4.5h-4.5" />
    </svg>
  )
}

export function IconScale(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M4 20h9" />
      <path d="M8.5 4v16" />
      <path d="M8.5 4H15" />
      <path d="m4 11 2.3-4.5L8.5 11Z" />
      <path d="m13 11 2.3-4.5L17.5 11Z" />
    </svg>
  )
}

export function IconSparkles(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3v4M12 17v4M4 12h4M16 12h4" />
      <path d="M6.3 6.3 9 9M15 15l2.7 2.7M17.7 6.3 15 9M9 15l-2.7 2.7" />
    </svg>
  )
}

export function IconLogoMark(props: IconProps) {
  return (
    <svg {...base} strokeWidth={2} {...props}>
      <path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z" />
      <path d="m8.2 12.4 2.6 2.7 5-5.6" />
    </svg>
  )
}

export function IconChevronRight(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}
