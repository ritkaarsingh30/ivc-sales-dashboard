import { useState, useMemo } from 'react'
import { Bar, Doughnut } from 'react-chartjs-2'
import { useActivities } from '../hooks/useDashboard'
import { MONTH_CONFIG } from '../utils/monthConfig'
import { baseOptions, baseOptionsNoScale, COLORS, monthColor } from '../utils/chartConfig'
import SectionLabel from '../components/SectionLabel'
import KpiCard from '../components/KpiCard'
import ChartCard from '../components/ChartCard'

const STATUS_CFG = {
  executed:         { label: 'Executed',  color: 'var(--good)',    bg: 'rgba(34,197,94,0.15)',    cls: 'g'  },
  planned_not_done: { label: 'Not Done',  color: 'var(--danger)',  bg: 'rgba(239,68,68,0.15)',    cls: 'err' },
  unplanned:        { label: 'Unplanned', color: 'var(--warn)',    bg: 'rgba(249,115,22,0.15)',   cls: 'w'  },
}

function fmtFcfa(n) {
  if (n === null || n === undefined || n === 0) return '—'
  return `${Number(n).toLocaleString()} FCFA`
}
function fmtEur(n) {
  if (n === null || n === undefined) return '—'
  return `€${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || {}
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10,
      fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase',
      color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.color}33`,
    }}>
      {cfg.label}
    </span>
  )
}

function OutcomeCell({ outcome }) {
  if (!outcome || outcome.length === 0) return <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {outcome.map((o, i) => (
        <span key={i} style={{ fontSize: 10, background: 'rgba(34,197,94,0.15)', color: 'var(--good)', borderRadius: 3, padding: '1px 5px', border: '1px solid rgba(34,197,94,0.3)' }}>
          {o.product_name} ×{o.qty}
        </span>
      ))}
    </div>
  )
}

export default function ActivitiesTab() {
  const { data: acts, isLoading, isError } = useActivities()
  const [monthFilter, setMonthFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const overall   = acts?.overall || {}
  const byMonth   = acts?.by_month || {}
  const months    = acts?.months || []
  const breakdown = acts?.activity_breakdown || []

  // ── Flatten all rows for the table ──────────────────────────────────────────
  const allRows = useMemo(() => {
    const rows = []
    const src = monthFilter === 'all' ? months : [monthFilter]
    for (const mk of src) {
      const m = byMonth[mk]
      if (!m) continue
      const label = m.label || mk
      for (const r of m.matched)          rows.push({ ...r, month: mk, monthLabel: label })
      for (const r of m.planned_not_done) rows.push({ ...r, month: mk, monthLabel: label })
      for (const r of m.unplanned_done)   rows.push({ ...r, month: mk, monthLabel: label })
    }
    return rows
  }, [monthFilter, byMonth, months])

  if (isLoading) return <div className="loading">⟳ Loading activity plan data...</div>
  if (isError)   return <div className="error">✕ Failed to load activity data.</div>
  if (!acts)     return null

  const filteredRows = statusFilter === 'all'
    ? allRows
    : allRows.filter(r => r.status === statusFilter)

  // ── Execution bar chart ──────────────────────────────────────────────────────
  const barData = {
    labels: months.map(mk => MONTH_CONFIG[mk]?.short || mk.toUpperCase()),
    datasets: [
      {
        label: 'Executed',
        data: months.map(mk => byMonth[mk]?.summary?.executed || 0),
        backgroundColor: 'rgba(34,197,94,0.7)', borderColor: '#22c55e', borderWidth: 1,
      },
      {
        label: 'Not Done',
        data: months.map(mk => byMonth[mk]?.summary?.not_executed || 0),
        backgroundColor: 'rgba(239,68,68,0.7)', borderColor: '#ef4444', borderWidth: 1,
      },
      {
        label: 'Unplanned',
        data: months.map(mk => byMonth[mk]?.summary?.unplanned || 0),
        backgroundColor: 'rgba(249,115,22,0.7)', borderColor: '#f97316', borderWidth: 1,
      },
    ],
  }

  // ── Budget comparison bar chart ──────────────────────────────────────────────
  const budgetData = {
    labels: months.map(mk => MONTH_CONFIG[mk]?.short || mk.toUpperCase()),
    datasets: [
      {
        label: 'Planned Budget (FCFA)',
        data: months.map(mk => byMonth[mk]?.summary?.planned_budget_fcfa || 0),
        backgroundColor: 'rgba(168,85,247,0.6)', borderColor: '#a855f7', borderWidth: 1,
      },
      {
        label: 'Actual Spent (FCFA)',
        data: months.map(mk => byMonth[mk]?.summary?.actual_spent_fcfa || 0),
        backgroundColor: 'rgba(59,130,246,0.6)', borderColor: '#3b82f6', borderWidth: 1,
      },
    ],
  }

  // ── Activity type doughnut ───────────────────────────────────────────────────
  const topBreakdown = breakdown.slice(0, 8)
  const actDoughnut = {
    labels: topBreakdown.map(a => a.activity),
    datasets: [{
      data: topBreakdown.map(a => a.count),
      backgroundColor: [COLORS.jan, COLORS.feb, COLORS.mar, COLORS.apr, COLORS.may, COLORS.jun, COLORS.jul, COLORS.aug],
      borderColor: '#0d1117', borderWidth: 2,
    }],
  }

  const execColor = overall.execution_rate_pct >= 60 ? 'var(--good)' : overall.execution_rate_pct >= 30 ? 'var(--warn)' : 'var(--danger)'

  return (
    <div>
      {/* ── KPI CARDS ── */}
      <SectionLabel tag="PLAN" text="ACTIVITY PLAN vs ACTUAL EXECUTION" monthColor="ov-s" />
      <div className="kpi-grid">
        <KpiCard label="Total Planned"   value={overall.total_planned ?? 0}    sub="Activities in plan"       monthColor="q" />
        <KpiCard label="Executed"        value={overall.executed ?? 0}          sub={`${overall.execution_rate_pct ?? 0}% of plan`} monthColor="g" />
        <KpiCard label="Not Executed"    value={overall.not_executed ?? 0}      sub="Planned but not done"    monthColor="err" />
        <KpiCard label="Unplanned Done"  value={overall.unplanned ?? 0}         sub="Done without plan"       monthColor="w" />
        <KpiCard label="Planned Budget"  value={fmtFcfa(overall.planned_budget_fcfa)} sub="Activity plan budget"  monthColor="q" />
        <KpiCard label="Actual Spent"    value={fmtFcfa(overall.actual_spent_fcfa)}   sub="Total activities spent" monthColor="j" />
      </div>

      {/* ── CHARTS ── */}
      <SectionLabel tag="ANALYTICS" text="EXECUTION OVERVIEW" monthColor="ov-s" />
      <div className="grid-2">
        <ChartCard title="Planned vs Executed vs Unplanned (by Month)" sub="Green=Executed · Red=Not Done · Orange=Unplanned" height="h260" monthColor="tri">
          <Bar data={barData} options={baseOptions({ plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } } })} />
        </ChartCard>
        <ChartCard title="Budget: Planned vs Actual (FCFA)" sub="Planned activity budget vs actual expense spent" height="h260" monthColor="tri">
          <Bar data={budgetData} options={baseOptions({ plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } } })} />
        </ChartCard>
      </div>

      {/* ── PER-MONTH SUMMARY CARDS ── */}
      <SectionLabel tag="MONTHS" text="MONTH-BY-MONTH SUMMARY" monthColor="ov-s" />
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        {months.map(mk => {
          const m = byMonth[mk]
          const s = m?.summary || {}
          const col = monthColor(mk).solid
          const rate = s.execution_rate_pct ?? 0
          const rateCol = rate >= 60 ? 'var(--good)' : rate >= 30 ? 'var(--warn)' : 'var(--danger)'
          return (
            <div key={mk} className="chart-card" style={{ flex: '1 1 220px', minWidth: 200, padding: '14px 18px' }}>
              <div style={{ fontWeight: 700, color: col, fontSize: 13, marginBottom: 8 }}>
                {MONTH_CONFIG[mk]?.emoji || '📅'} {m?.label || mk.toUpperCase()}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Planned</span><strong>{s.total_planned ?? 0}</strong>
                <span style={{ color: 'var(--good)' }}>Executed</span><strong style={{ color: 'var(--good)' }}>{s.executed ?? 0}</strong>
                <span style={{ color: 'var(--danger)' }}>Not Done</span><strong style={{ color: 'var(--danger)' }}>{s.not_executed ?? 0}</strong>
                <span style={{ color: 'var(--warn)' }}>Unplanned</span><strong style={{ color: 'var(--warn)' }}>{s.unplanned ?? 0}</strong>
                <span style={{ color: 'var(--text-muted)' }}>Exec Rate</span><strong style={{ color: rateCol }}>{rate}%</strong>
                <span style={{ color: 'var(--text-muted)' }}>Budget</span><strong style={{ fontSize: 10 }}>{s.planned_budget_fcfa ? `${(s.planned_budget_fcfa / 1000).toFixed(0)}k` : '—'} FCFA</strong>
                <span style={{ color: 'var(--text-muted)' }}>Spent</span><strong style={{ fontSize: 10 }}>{s.actual_spent_fcfa ? `${(s.actual_spent_fcfa / 1000).toFixed(0)}k` : '—'} FCFA</strong>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── ACTIVITY TABLE ── */}
      <SectionLabel tag="DETAIL" text="ACTIVITY-BY-ACTIVITY BREAKDOWN" monthColor="ov-s" />

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 4 }}>MONTH:</span>
        {['all', ...months].map(mk => (
          <button key={mk} onClick={() => setMonthFilter(mk)} style={{
            padding: '3px 10px', borderRadius: 4, border: `1px solid ${monthFilter === mk ? monthColor(mk === 'all' ? 'q1' : mk).solid : 'var(--border)'}`,
            background: monthFilter === mk ? monthColor(mk === 'all' ? 'q1' : mk).soft : 'transparent',
            color: monthFilter === mk ? monthColor(mk === 'all' ? 'q1' : mk).solid : 'var(--text-muted)',
            cursor: 'pointer', fontSize: 11, fontWeight: 600,
          }}>
            {mk === 'all' ? 'All' : (MONTH_CONFIG[mk]?.short || mk.toUpperCase())}
          </button>
        ))}
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 12, marginRight: 4 }}>STATUS:</span>
        {[
          ['all', 'All', 'var(--text-muted)'],
          ['executed', 'Executed', 'var(--good)'],
          ['planned_not_done', 'Not Done', 'var(--danger)'],
          ['unplanned', 'Unplanned', 'var(--warn)'],
        ].map(([val, lbl, col]) => (
          <button key={val} onClick={() => setStatusFilter(val)} style={{
            padding: '3px 10px', borderRadius: 4, border: `1px solid ${statusFilter === val ? col : 'var(--border)'}`,
            background: statusFilter === val ? `${col}22` : 'transparent',
            color: statusFilter === val ? col : 'var(--text-muted)',
            cursor: 'pointer', fontSize: 11, fontWeight: 600,
          }}>
            {lbl} ({val === 'all' ? allRows.length : allRows.filter(r => r.status === val).length})
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid var(--border)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: 'var(--surface2)', borderBottom: '1px solid var(--border)' }}>
              {['Status', 'Month', 'Doctor', 'Hospital', 'Speciality', 'Activity', 'Delegate / Resp.', 'Planned FCFA', 'Actual FCFA', 'Visits', 'Sales Outcome', 'Sales Value €'].map(h => (
                <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-muted)', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.length === 0 ? (
              <tr><td colSpan={12} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>No activities match this filter.</td></tr>
            ) : filteredRows.map((r, i) => {
              const col = monthColor(r.month).solid
              const isExec = r.status === 'executed'
              const isNotDone = r.status === 'planned_not_done'
              return (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>
                    <StatusBadge status={r.status} />
                  </td>
                  <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>
                    <span style={{ color: col, fontWeight: 600, fontSize: 11 }}>
                      {MONTH_CONFIG[r.month]?.emoji || '📅'} {r.monthLabel}
                    </span>
                  </td>
                  <td style={{ padding: '7px 10px', color: 'var(--text)', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.doctor || '—'}</td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-muted)', maxWidth: 110, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.hospital || '—'}</td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{r.speciality || '—'}</td>
                  <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>
                    <span style={{ color: '#a855f7', fontWeight: 600 }}>{r.activity || '—'}</span>
                  </td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-muted)', fontSize: 11, maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.delegate || r.responsible || '—'}
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'right', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>
                    {!isNotDone ? '—' : fmtFcfa(r.planned_fcfa)}
                    {isExec && r.planned_fcfa ? (
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{fmtFcfa(r.planned_fcfa)}</div>
                    ) : null}
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {isNotDone ? '—' : (
                      <span style={{ color: isExec && r.variance_fcfa < 0 ? 'var(--good)' : isExec && r.variance_fcfa > 0 ? 'var(--danger)' : 'var(--text)' }}>
                        {fmtFcfa(r.actual_fcfa)}
                      </span>
                    )}
                    {isExec && r.variance_fcfa !== undefined ? (
                      <div style={{ fontSize: 10, color: r.variance_fcfa > 0 ? 'var(--danger)' : 'var(--good)' }}>
                        {r.variance_fcfa > 0 ? `+${r.variance_fcfa.toLocaleString()}` : r.variance_fcfa.toLocaleString()}
                      </div>
                    ) : null}
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'center', color: (r.num_visits > 0) ? 'var(--text)' : 'var(--text-muted)' }}>
                    {r.num_visits > 0 ? r.num_visits : '—'}
                  </td>
                  <td style={{ padding: '7px 10px', maxWidth: 160 }}>
                    {isNotDone
                      ? <span style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>{r.focus_products || '—'}</span>
                      : <OutcomeCell outcome={r.sales_outcome} />
                    }
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {r.sales_outcome_eur > 0
                      ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>€{Number(r.sales_outcome_eur).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                      : <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>
                    }
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
        Showing {filteredRows.length} of {allRows.length} activities
      </div>
    </div>
  )
}
