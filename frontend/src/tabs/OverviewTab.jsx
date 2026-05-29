import { useState, useCallback, useRef } from 'react'
import { Bar, Doughnut } from 'react-chartjs-2'
import { useOverview, useInsights, useRefreshInsights, useRefreshData } from '../hooks/useDashboard'
import { MONTH_CONFIG } from '../utils/monthConfig'
import SectionLabel from '../components/SectionLabel'
import InsightBox from '../components/InsightBox'
import ChartCard from '../components/ChartCard'
import KpiCard from '../components/KpiCard'
import { baseOptions, baseOptionsNoScale, COLORS, PALETTE, monthColor } from '../utils/chartConfig'
import { useFilter } from '../context/FilterContext'

const REFRESH_COOLDOWN_MS = 8000

function fmt(n, decimals = 0) {
  if (n === null || n === undefined) return '—'
  return `€${Number(n).toLocaleString(undefined, { maximumFractionDigits: decimals })}`
}
function fmtPct(n) { return n !== null && n !== undefined ? `${n}%` : '—' }

export default function OverviewTab() {
  const { data: ov, isLoading, isError } = useOverview()
  const { data: insightsData, isLoading: insightsLoading } = useInsights()
  const refreshMut = useRefreshInsights()
  const refreshData = useRefreshData()
  const { activeMonths: filteredMonths } = useFilter()

  const [refreshCooldown, setRefreshCooldown] = useState(false)
  const [insightsCooldown, setInsightsCooldown] = useState(false)
  const [refreshMsg, setRefreshMsg] = useState(null)
  const [insightsMsg, setInsightsMsg] = useState(null)
  const refreshMsgTimer = useRef(null)
  const insightsMsgTimer = useRef(null)

  const showMsg = (setter, timerRef, msg, durationMs = 4000) => {
    setter(msg)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setter(null), durationMs)
  }

  const handleRefreshData = useCallback(() => {
    if (refreshData.isPending || refreshCooldown) return
    refreshData.mutate(undefined, {
      onSuccess: (data) => {
        setRefreshCooldown(true)
        setTimeout(() => setRefreshCooldown(false), REFRESH_COOLDOWN_MS)
        if (data?.status === 'skipped') {
          showMsg(setRefreshMsg, refreshMsgTimer, 'Refresh skipped (local mode)')
        }
      },
      onError: (err) => {
        const status = err?.response?.status
        const reason = err?.response?.data?.reason
        if (status === 409) {
          showMsg(setRefreshMsg, refreshMsgTimer, 'Already refreshing — please wait')
        } else {
          showMsg(setRefreshMsg, refreshMsgTimer, reason || 'Refresh failed')
        }
      },
    })
  }, [refreshData, refreshCooldown])

  const handleRefreshInsights = useCallback(() => {
    if (refreshMut.isPending || insightsCooldown) return
    refreshMut.mutate(undefined, {
      onSuccess: () => {
        setInsightsCooldown(true)
        setTimeout(() => setInsightsCooldown(false), REFRESH_COOLDOWN_MS)
      },
      onError: (err) => {
        const status = err?.response?.status
        const reason = err?.response?.data?.reason
        if (status === 409) {
          showMsg(setInsightsMsg, insightsMsgTimer, 'Already generating — please wait')
        } else {
          showMsg(setInsightsMsg, insightsMsgTimer, reason || 'Generation failed')
        }
      },
    })
  }, [refreshMut, insightsCooldown])

  if (isLoading) return <div className="loading">⟳ Loading overview data...</div>
  if (isError) return <div className="error">✕ Failed to load overview. Is the backend running?</div>

  const q1 = ov.q1_summary || {}
  const mcAll = ov.month_comparison || []
  const mc = mcAll.filter(m => filteredMonths.includes(m.key))
  const months = mc.map(m => m.key)
  const trend = ov.all_products_trend || []
  const delegateVisits = q1.delegate_visits_all || q1.delegate_visits_q1 || []

  const monthLabels = mc.map(m => m.month)

  // ── Sales + Projection bar+line combo ──
  const salesVsProjData = {
    labels: monthLabels,
    datasets: [
      {
        type: 'bar',
        label: 'Actual Sales (€)',
        data: mc.map(m => m.sales || 0),
        backgroundColor: mc.map(m => monthColor(m.key).alpha),
        borderColor: mc.map(m => monthColor(m.key).solid),
        borderWidth: 2,
        borderRadius: 6,
        order: 2,
      },
      {
        type: 'line',
        label: 'Projection (€)',
        data: mc.map(m => m.projection || 0),
        borderColor: COLORS.neutral,
        backgroundColor: 'transparent',
        borderWidth: 2,
        borderDash: [6, 3],
        pointRadius: 5,
        pointBackgroundColor: COLORS.neutral,
        fill: false,
        tension: 0.4,
        order: 1,
      },
    ],
  }

  // ── Delegate visits doughnut ──
  const dvLabels = delegateVisits.map(d => d.delegate)
  const dvValues = delegateVisits.map(d => d.visits)
  const doughnutData = {
    labels: dvLabels,
    datasets: [{
      data: dvValues,
      backgroundColor: PALETTE.slice(0, dvLabels.length),
      borderColor: '#0d1117',
      borderWidth: 2,
    }],
  }

  // ── All products grouped bar — one dataset per loaded month ──
  const productLabels = trend.map(t => t.product)
  const allProductsData = {
    labels: productLabels,
    datasets: months.map(key => {
      const mc_entry = MONTH_CONFIG[key] || {}
      const col = monthColor(key)
      return {
        label: mc_entry.label || key,
        data: trend.map(t => t[key] || 0),
        backgroundColor: col.alpha,
        borderColor: col.solid,
        borderWidth: 1,
      }
    }),
  }

  const insights = insightsData?.insights || []
  const periodLabel = months.length > 0
    ? (months.length <= 3 ? `${MONTH_CONFIG[months[0]]?.short || months[0].toUpperCase()}–${MONTH_CONFIG[months[months.length - 1]]?.short || months[months.length - 1].toUpperCase()}` : `${months.length}M`)
    : 'Period'

  // helper: visits sub label
  const visitsSub = months.map(k => `${MONTH_CONFIG[k]?.short || k} ${q1.total_visits?.[k] || 0}`).join(' · ')
  const drsSub    = months.map(k => `${MONTH_CONFIG[k]?.short || k} ${q1.drs_converted?.[k] ?? 0}`).join(' · ')

  return (
    <div>
      {/* ── KPI CARDS ── */}
      <SectionLabel tag={periodLabel} text="KEY PERFORMANCE INDICATORS" monthColor="ov-s" />
      <div className="kpi-grid">
        <KpiCard
          label="Total Sales"
          value={fmt(q1.total_sales_eur)}
          sub={`${monthLabels.join(' + ')}`}
          monthColor="q"
        />
        {mc.map(m => {
          const cfg = MONTH_CONFIG[m.key] || {}
          const ach = q1.month_achievement_pct?.[m.key]
          return (
            <KpiCard
              key={m.key}
              label={`${m.month} Sales`}
              value={fmt(m.sales)}
              sub={ach !== null && ach !== undefined ? `${fmtPct(ach)} of target` : undefined}
              monthColor={cfg.cls || 'q'}
            />
          )
        })}
        <KpiCard
          label="Total Visits"
          value={(q1.total_visits_all ?? q1.total_visits_q1 ?? 0).toLocaleString()}
          sub={visitsSub}
          monthColor="q"
        />
        <KpiCard
          label="Drs Converted"
          value={q1.drs_converted_all ?? q1.drs_converted_q1 ?? '—'}
          sub={drsSub}
          monthColor="d"
        />
        <KpiCard
          label="Best Month"
          value={q1.best_month || '—'}
          sub={fmt(q1.best_month_sales)}
          monthColor="g"
        />
        <KpiCard
          label="Top Product"
          value={q1.top_product_all || q1.top_product_q1 || '—'}
          sub={fmt(q1.top_product_all_val || q1.top_product_q1_val)}
          monthColor="q"
        />
      </div>

      {/* ── SALES TREND & PROJECTION ── */}
      <SectionLabel tag={periodLabel} text="SALES TREND & PROJECTION GAP" monthColor="ov-s" />
      <div className="full">
        <ChartCard
          title="Monthly Sales: Actual vs Projection (€)"
          sub={`${monthLabels.join(' · ')} | Projection shown as dashed`}
          height="h300"
          monthColor="tri"
        >
          <Bar data={salesVsProjData} options={baseOptions({
            plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } }
          })} />
        </ChartCard>
      </div>

      {/* ── DELEGATE VISITS ── */}
      <SectionLabel tag={periodLabel} text="VISIT & DELEGATE PERFORMANCE" monthColor="ov-s" />
      <div className="grid-2">
        <ChartCard
          title={`Total Visits by Delegate (${periodLabel})`}
          sub={`Aggregate visits across ${monthLabels.join(', ')}`}
          height="h300"
          monthColor="q"
        >
          {dvLabels.length > 0 ? (
            <Doughnut
              data={doughnutData}
              options={baseOptionsNoScale({
                plugins: {
                  legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 11 }, padding: 14 } },
                  tooltip: {
                    callbacks: {
                      label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} visits`
                    },
                    backgroundColor: '#111320', titleColor: '#e2e8f0', bodyColor: '#94a3b8',
                    borderColor: '#1a1f35', borderWidth: 1,
                  }
                },
                cutout: '62%',
              })}
            />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
              No visit data available
            </div>
          )}
        </ChartCard>

        {/* Month-wise summary mini-table */}
        <div className="chart-card q" style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          <div style={{ padding: '16px 20px 8px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Month-wise Summary
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Sales · Visits · Drs Converted · Achievement
            </div>
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly', padding: '12px 20px' }}>
            {mc.map(m => {
              const col = monthColor(m.key).solid
              const visits = q1.total_visits?.[m.key]
              const ach = q1.month_achievement_pct?.[m.key]
              return (
                <div key={m.key} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ width: 3, height: 40, borderRadius: 2, background: col, flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ color: col, fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{m.month} 2026</div>
                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Sales <strong style={{ color: 'var(--text)' }}>{fmt(m.sales)}</strong></span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Visits <strong style={{ color: 'var(--text)' }}>{(visits ?? 0).toLocaleString()}</strong></span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Drs Conv. <strong style={{ color: 'var(--good)' }}>{m.drs_converted ?? 0}</strong></span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        Achieved <strong style={{ color: ach >= 80 ? 'var(--good)' : ach >= 60 ? 'var(--warn)' : 'var(--danger)' }}>
                          {fmtPct(ach)}
                        </strong>
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── PRODUCT MIX ── */}
      <SectionLabel tag={periodLabel} text="PRODUCT MIX EVOLUTION" monthColor="ov-s" />
      <div className="full">
        <ChartCard
          title={`All Products — Sales Value (${months.map(k => `${MONTH_CONFIG[k]?.emoji || ''} ${MONTH_CONFIG[k]?.short || k}`).join(' · ')})`}
          sub="Grouped bar showing each product's performance across all loaded months"
          height="h340"
          monthColor="tri"
        >
          <Bar data={allProductsData} options={baseOptions({ plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } } })} />
        </ChartCard>
      </div>

      {/* ── MONTH-WISE DEEP COMPARISON ── */}
      <SectionLabel tag={periodLabel} text="MONTH-WISE DEEP COMPARISON" monthColor="ov-s" />
      <div className="month-trio">
        {mc.map(m => {
          const cfg = MONTH_CONFIG[m.key] || {}
          const col = monthColor(m.key).solid
          const colorCls = cfg.cls || 'q'
          const ach = q1.month_achievement_pct?.[m.key]
          const visits = q1.total_visits?.[m.key]
          const pctColor = ach !== null && ach !== undefined
            ? (ach >= 80 ? 'var(--good)' : ach >= 60 ? 'var(--warn)' : 'var(--danger)')
            : 'var(--text-muted)'
          return (
            <div key={m.key} className="month-col">
              <div className={`month-col-hdr ${colorCls}`}>{cfg.emoji || '📅'} {m.month.toUpperCase()} 2026</div>
              <div className="month-col-body">
                <div className="stat-row"><span className="stat-lbl">Sales</span><span className="stat-val" style={{ color: col }}>{fmt(m.sales)}</span></div>
                <div className="stat-row"><span className="stat-lbl">Projection</span><span className="stat-val" style={{ color: 'var(--text-muted)' }}>{fmt(m.projection)}</span></div>
                <div className="stat-row"><span className="stat-lbl">Achievement</span><span className="stat-val" style={{ color: pctColor }}>{fmtPct(ach)}</span></div>
                <div className="stat-row"><span className="stat-lbl">Total Visits</span><span className="stat-val">{(visits ?? 0).toLocaleString()}</span></div>
                <div className="stat-row"><span className="stat-lbl">Prescriber Calls</span><span className="stat-val">{m.prescriber_calls ?? '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Pharmacy Calls</span><span className="stat-val">{m.pharmacy_calls ?? '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Drs Converted</span><span className="stat-val" style={{ color: (m.drs_converted || 0) > 0 ? 'var(--good)' : 'var(--danger)' }}>{m.drs_converted ?? 0}</span></div>
                <div className="stat-row"><span className="stat-lbl">Active Delegates</span><span className="stat-val">{m.active_delegates ?? '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Activity Spent</span><span className="stat-val">{m.activity_spent_eur !== null && m.activity_spent_eur !== undefined ? `€${m.activity_spent_eur.toLocaleString()}` : '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Closing Balance</span><span className="stat-val" style={{ color: (m.closing_balance_eur || 0) >= 0 ? 'var(--good)' : 'var(--danger)' }}>{m.closing_balance_eur !== null && m.closing_balance_eur !== undefined ? `€${m.closing_balance_eur.toLocaleString()}` : '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Top Product</span><span className="stat-val">{m.top_product ?? '—'}</span></div>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── AI INSIGHTS ── */}
      <SectionLabel tag={periodLabel} text="KEY INSIGHTS" monthColor="ov-s" />
      <div className="insights-header">
        <span className="ai-label">Key Action Points</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {insightsData && (
            <span className={`badge ${insightsData.cached ? 'n' : 'g'}`}>
              {insightsData.cached ? 'Cached' : 'Live'}
            </span>
          )}
          {refreshMsg && (
            <span style={{ fontSize: '0.75rem', color: 'var(--danger)', whiteSpace: 'nowrap' }}>{refreshMsg}</span>
          )}
          {insightsMsg && (
            <span style={{ fontSize: '0.75rem', color: 'var(--danger)', whiteSpace: 'nowrap' }}>{insightsMsg}</span>
          )}
          <button
            className="refresh-btn"
            style={{ borderColor: 'rgba(16,185,129,.4)', background: 'rgba(16,185,129,.1)', color: 'var(--mar)' }}
            onClick={handleRefreshData}
            disabled={refreshData.isPending || refreshCooldown}
            id="refresh-data-btn"
          >
            {refreshData.isPending ? '⟳ Refreshing...' : refreshCooldown ? '✓ Done' : '⟳ Refresh Data'}
          </button>
          <button
            className="refresh-btn"
            onClick={handleRefreshInsights}
            disabled={refreshMut.isPending || insightsCooldown}
            id="regenerate-insights-btn"
          >
            {refreshMut.isPending ? '⟳ Generating...' : insightsCooldown ? '✓ Done' : '↺ Regenerate'}
          </button>
        </div>
      </div>
      <div className="insight-grid">
        {insightsLoading || refreshMut.isPending
          ? Array(6).fill(0).map((_, i) => <InsightBox key={i} loading />)
          : insights.map((ins, i) => (
              <InsightBox key={i} type={ins.type} icon={ins.icon} title={ins.title} text={ins.text} />
            ))
        }
      </div>
    </div>
  )
}
