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
  jan: '#3b82f6', janA: 'rgba(59,130,246,0.6)',  janS: 'rgba(59,130,246,0.2)',
  feb: '#f59e0b', febA: 'rgba(245,158,11,0.6)',  febS: 'rgba(245,158,11,0.15)',
  mar: '#10b981', marA: 'rgba(16,185,129,0.6)',  marS: 'rgba(16,185,129,0.15)',
  apr: '#a855f7', aprA: 'rgba(168,85,247,0.6)',  aprS: 'rgba(168,85,247,0.15)',
  may: '#fb923c', mayA: 'rgba(251,146,60,0.6)',  mayS: 'rgba(251,146,60,0.15)',
  jun: '#ef4444', junA: 'rgba(239,68,68,0.6)',   junS: 'rgba(239,68,68,0.15)',
  jul: '#6b7280', julA: 'rgba(107,114,128,0.6)', julS: 'rgba(107,114,128,0.15)',
  aug: '#0ea5e9', augA: 'rgba(14,165,233,0.6)',  augS: 'rgba(14,165,233,0.15)',
  sep: '#64748b', sepA: 'rgba(100,116,139,0.6)', sepS: 'rgba(100,116,139,0.15)',
  oct: '#d97706', octA: 'rgba(217,119,6,0.6)',   octS: 'rgba(217,119,6,0.15)',
  nov: '#6366f1', novA: 'rgba(99,102,241,0.6)',  novS: 'rgba(99,102,241,0.15)',
  dec: '#14b8a6', decA: 'rgba(20,184,166,0.6)',  decS: 'rgba(20,184,166,0.15)',
  q1: '#a855f7',  q1A: 'rgba(168,85,247,0.6)',   q1S: 'rgba(168,85,247,0.15)',
  danger: '#ef4444', dangerA: 'rgba(239,68,68,0.6)',
  warn: '#f97316',   warnA: 'rgba(249,115,22,0.6)',
  good: '#22c55e',   goodA: 'rgba(34,197,94,0.6)',
  neutral: '#94a3b8',
  pink: '#f472b6',
  sky: '#38bdf8',
}

/** Return the main + alpha color for a month key (falls back to neutral). */
export function monthColor(key) {
  return {
    solid: COLORS[key] || COLORS.neutral,
    alpha: COLORS[`${key}A`] || 'rgba(148,163,184,0.6)',
    soft:  COLORS[`${key}S`] || 'rgba(148,163,184,0.15)',
  }
}

// Consistent stacked call-breakdown chart used across all month tabs
export function buildCallChartData(cb) {
  return {
    labels: cb.labels || [],
    datasets: [
      { label: 'Prescriber',     data: cb.prescriber     || [], backgroundColor: 'rgba(59,130,246,0.6)',  borderColor: '#3b82f6', borderWidth: 1, stack: 'calls' },
      { label: 'Non-Prescriber', data: cb.non_prescriber || [], backgroundColor: 'rgba(168,85,247,0.55)', borderColor: '#a855f7', borderWidth: 1, stack: 'calls' },
      { label: 'Pharmacy',       data: cb.pharmacy       || [], backgroundColor: 'rgba(34,197,94,0.55)',  borderColor: '#22c55e', borderWidth: 1, stack: 'calls' },
    ],
  }
}

export function buildCallChartOptions() {
  return baseOptions({
    scales: {
      x: { stacked: true, ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(26,31,53,0.8)' } },
      y: { stacked: true, ticks: { color: '#64748b', font: { size: 10 }, stepSize: 1 }, grid: { color: 'rgba(26,31,53,0.8)' } },
    },
  })
}

export const PALETTE = [
  '#3b82f6','#f59e0b','#10b981','#a855f7','#f472b6','#38bdf8',
  '#fb923c','#84cc16','#06b6d4','#8b5cf6','#ec4899','#14b8a6'
]
