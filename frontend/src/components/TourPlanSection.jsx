import { Bar, Doughnut } from 'react-chartjs-2'
import SectionLabel from './SectionLabel'
import ChartCard from './ChartCard'
import KpiCard from './KpiCard'
import DataTable from './DataTable'
import Badge from './Badge'
import { baseOptions, baseOptionsNoScale } from '../utils/chartConfig'

const GREEN    = 'rgba(34,197,94,0.65)'
const GREEN_BD = 'rgba(34,197,94,1)'
const RED      = 'rgba(239,68,68,0.5)'
const RED_BD   = 'rgba(239,68,68,0.85)'

const DELEGATE_COLORS = [
  { bg: 'rgba(59,130,246,0.55)',  bd: 'rgba(59,130,246,1)'  },   // blue
  { bg: 'rgba(245,158,11,0.55)', bd: 'rgba(245,158,11,1)'  },   // amber
  { bg: 'rgba(16,185,129,0.55)', bd: 'rgba(16,185,129,1)'  },   // green
  { bg: 'rgba(168,85,247,0.55)', bd: 'rgba(168,85,247,1)'  },   // purple
  { bg: 'rgba(236,72,153,0.55)', bd: 'rgba(236,72,153,1)'  },   // pink
  { bg: 'rgba(251,146,60,0.55)', bd: 'rgba(251,146,60,1)'  },   // orange
]

function coverageVariant(pct) {
  if (pct >= 80) return 'g'
  if (pct >= 50) return 'w'
  return 'd'
}

const ENTRY_COLS = [
  { key: 'date',          label: 'Date' },
  { key: 'planned_area',  label: 'Planned Area' },
  { key: 'actual_area',   label: 'Actual Area' },
  { key: 'status_badge',  label: 'Status' },
  { key: 'joint_working', label: 'Joint Working' },
]

function buildEntryRows(entries) {
  return entries.map(e => ({
    ...e,
    planned_area:  e.planned_area  || '—',
    actual_area:   e.actual_area   || '—',
    joint_working: e.joint_working || '—',
    status_badge:  e.covered
      ? <Badge text="✓ Covered" variant="g" />
      : <Badge text="✗ Missed"  variant="d" />,
  }))
}

export default function TourPlanSection({ tourPlan = {}, cfg }) {
  const s    = tourPlan.summary         || {}
  const bd   = tourPlan.by_delegate     || []
  const ebd  = tourPlan.entries_by_delegate || {}

  if (!s.total) return null

  // ── Overall Covered vs Missed stacked bar ──
  const barData = {
    labels: bd.map(d => d.mr),
    datasets: [
      {
        label: 'Covered',
        data: bd.map(d => d.covered),
        backgroundColor: GREEN,
        borderColor: GREEN_BD,
        borderWidth: 1,
        borderRadius: 3,
      },
      {
        label: 'Missed',
        data: bd.map(d => d.uncovered),
        backgroundColor: RED,
        borderColor: RED_BD,
        borderWidth: 1,
        borderRadius: 3,
      },
    ],
  }

  const barOptions = baseOptions({
    indexAxis: 'y',
    scales: {
      x: {
        stacked: true,
        ticks: { color: '#64748b', stepSize: 1 },
        grid: { color: 'rgba(26,31,53,0.8)' },
      },
      y: {
        stacked: true,
        ticks: { color: '#64748b' },
        grid: { color: 'rgba(26,31,53,0.8)' },
      },
    },
    plugins: {
      legend: { display: true, position: 'top' },
      tooltip: {
        callbacks: {
          label: ctx => {
            const del = bd[ctx.dataIndex]
            return `${ctx.dataset.label}: ${ctx.parsed.x} day(s) — ${del.coverage_pct}% covered overall`
          },
        },
      },
    },
  })

  // ── Doughnut: overall coverage split ──
  const donutData = {
    labels: ['Covered', 'Missed'],
    datasets: [{
      data: [s.covered, s.uncovered],
      backgroundColor: [GREEN, RED],
      borderColor: 'var(--card)',
      borderWidth: 3,
    }],
  }

  const donutOptions = baseOptionsNoScale({
    plugins: {
      legend: { display: true, position: 'bottom' },
      tooltip: {
        callbacks: {
          label: ctx => {
            const val = ctx.parsed
            const total = s.total
            return `${ctx.label}: ${val} (${Math.round(val / total * 100)}%)`
          },
        },
      },
    },
  })

  const badgeVariant = coverageVariant(s.coverage_pct)

  return (
    <>
      <SectionLabel
        tag={cfg.label.toUpperCase()}
        text="TOUR PLAN — FIELD COVERAGE"
        monthColor={cfg.sectionCls}
      />

      {/* ── Summary KPIs ── */}
      <div className="kpi-grid">
        <KpiCard label="Days Planned"       value={s.total}             monthColor={cfg.cls} />
        <KpiCard label="Days Covered"       value={s.covered}           sub={`${s.coverage_pct}% adherence`} monthColor="g" />
        <KpiCard label="Days Missed"        value={s.uncovered}         monthColor={s.uncovered > 0 ? 'd' : 'g'} />
        <KpiCard label="Active Delegates"   value={s.delegates_active}  monthColor={cfg.cls} />
        <KpiCard label="Joint Working Days" value={s.joint_working}     sub="CM accompanied visits" monthColor={cfg.cls} />
      </div>

      {/* ── Charts ── */}
      <div className="grid-2">
        <ChartCard
          title={`Coverage by Delegate — ${cfg.label}`}
          sub="Covered vs Missed days · sorted by adherence rate"
          height="h300"
          monthColor={cfg.cls}
        >
          <Bar data={barData} options={barOptions} />
        </ChartCard>

        <ChartCard
          title="Overall Plan Coverage"
          sub={`${s.coverage_pct}% of planned areas visited`}
          height="h300"
          monthColor={cfg.cls}
        >
          <Doughnut data={donutData} options={donutOptions} />
        </ChartCard>
      </div>

      {/* ── Per-Delegate Tables (dynamic) ── */}
      <SectionLabel
        tag={cfg.label.toUpperCase()}
        text="TOUR PLAN — PER DELEGATE DETAIL"
        monthColor={cfg.sectionCls}
      />

      {bd.map((delInfo, idx) => {
        const { mr, planned, covered, uncovered, coverage_pct } = delInfo
        const color = DELEGATE_COLORS[idx % DELEGATE_COLORS.length]
        const delegateEntries = ebd[mr] || []
        const rows = buildEntryRows(delegateEntries)
        const variant = coverageVariant(coverage_pct)

        return (
          <DataTable
            key={mr}
            title={mr}
            badge={{
              text: `${planned} days · ${covered} covered · ${uncovered} missed · ${coverage_pct}% adherence`,
              variant,
            }}
            borderColor={color.bd}
            columns={ENTRY_COLS}
            rows={rows}
          />
        )
      })}
    </>
  )
}
