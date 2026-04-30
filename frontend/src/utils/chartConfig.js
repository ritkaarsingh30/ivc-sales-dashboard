export const baseOptions = (overrides = {}) => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
    tooltip: {
      backgroundColor: '#111320',
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
      borderColor: '#1a1f35',
      borderWidth: 1
    }
  },
  scales: {
    x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(26,31,53,0.8)' } },
    y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(26,31,53,0.8)' } }
  },
  ...overrides
})

export const baseOptionsNoScale = (overrides = {}) => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
    tooltip: {
      backgroundColor: '#111320',
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
      borderColor: '#1a1f35',
      borderWidth: 1
    }
  },
  ...overrides
})

export const COLORS = {
  jan: '#3b82f6', janA: 'rgba(59,130,246,0.6)', janS: 'rgba(59,130,246,0.2)',
  feb: '#f59e0b', febA: 'rgba(245,158,11,0.6)', febS: 'rgba(245,158,11,0.15)',
  mar: '#10b981', marA: 'rgba(16,185,129,0.6)', marS: 'rgba(16,185,129,0.15)',
  q1: '#a855f7',  q1A: 'rgba(168,85,247,0.6)',  q1S: 'rgba(168,85,247,0.15)',
  danger: '#ef4444', dangerA: 'rgba(239,68,68,0.6)',
  warn: '#f97316',   warnA: 'rgba(249,115,22,0.6)',
  good: '#22c55e',   goodA: 'rgba(34,197,94,0.6)',
  neutral: '#94a3b8',
  pink: '#f472b6',
  sky: '#38bdf8',
}

export const PALETTE = [
  '#3b82f6','#f59e0b','#10b981','#a855f7','#f472b6','#38bdf8',
  '#fb923c','#84cc16','#06b6d4','#8b5cf6','#ec4899','#14b8a6'
]
