import { Bar, Line, Doughnut } from 'react-chartjs-2'
import { useOverview, useInsights, useRefreshInsights, useRefreshData } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import InsightBox from '../components/InsightBox'
import ChartCard from '../components/ChartCard'
import KpiCard from '../components/KpiCard'
import { baseOptions, baseOptionsNoScale, COLORS, PALETTE } from '../utils/chartConfig'

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

  if (isLoading) return <div className="loading">⟳ Loading Q1 overview data...</div>
  if (isError) return <div className="error">✕ Failed to load overview. Is the backend running?</div>

  const q1 = ov.q1_summary || {}
  const mc = ov.month_comparison || []
  const jan = mc[0] || {}
  const feb = mc[1] || {}
  const mar = mc[2] || {}
  const trend = ov.all_products_trend || []
  const delegateVisits = q1.delegate_visits_q1 || []

  // ── Sales + Projection bar+line combo ──
  const monthLabels = ['January', 'February', 'March']
  const salesVsProjData = {
    labels: monthLabels,
    datasets: [
      {
        type: 'bar',
        label: 'Actual Sales (€)',
        data: [q1.jan_sales || 0, q1.feb_sales || 0, q1.mar_sales || 0],
        backgroundColor: [COLORS.janA, COLORS.febA, COLORS.marA],
        borderColor: [COLORS.jan, COLORS.feb, COLORS.mar],
        borderWidth: 2,
        borderRadius: 6,
        order: 2,
      },
      {
        type: 'line',
        label: 'Projection (€)',
        data: [jan.projection || 0, feb.projection || 0, mar.projection || 0],
        borderColor: COLORS.q1,
        backgroundColor: COLORS.q1S,
        borderWidth: 2,
        borderDash: [6, 3],
        pointRadius: 5,
        pointBackgroundColor: COLORS.q1,
        fill: false,
        tension: 0.4,
        order: 1,
      },
    ],
  }

  // ── Cumulative build-up line ──
  const janSales = q1.jan_sales || 0
  const febSales = q1.feb_sales || 0
  const marSales = q1.mar_sales || 0
  const janProj = jan.projection || 0
  const febProj = feb.projection || 0
  const marProj = mar.projection || 0

  const cumulativeData = {
    labels: monthLabels,
    datasets: [
      {
        label: 'Cumulative Actual (€)',
        data: [janSales, janSales + febSales, janSales + febSales + marSales],
        borderColor: COLORS.q1,
        backgroundColor: COLORS.q1S,
        borderWidth: 2,
        pointRadius: 5,
        fill: true,
        tension: 0.4,
      },
      {
        label: 'Cumulative Projection (€)',
        data: [janProj, janProj + febProj, janProj + febProj + marProj],
        borderColor: COLORS.neutral,
        backgroundColor: 'transparent',
        borderWidth: 2,
        borderDash: [6, 3],
        pointRadius: 4,
        fill: false,
        tension: 0.4,
      },
    ],
  }

  // ── Delegate visits pie ──
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

  // ── All products grouped bar ──
  const productLabels = trend.map(t => t.product)
  const allProductsData = {
    labels: productLabels,
    datasets: [
      { label: 'January', data: trend.map(t => t.jan), backgroundColor: COLORS.janA, borderColor: COLORS.jan, borderWidth: 1 },
      { label: 'February', data: trend.map(t => t.feb), backgroundColor: COLORS.febA, borderColor: COLORS.feb, borderWidth: 1 },
      { label: 'March', data: trend.map(t => t.mar), backgroundColor: COLORS.marA, borderColor: COLORS.mar, borderWidth: 1 },
    ]
  }

  const insights = insightsData?.insights || []
  const annualPct = q1.annual_achievement_pct
  const annualPctColor = annualPct >= 80 ? 'var(--good)' : annualPct >= 50 ? 'var(--warn)' : 'var(--danger)'

  return (
    <div>
      {/* ── KPI CARDS ── */}
      <SectionLabel tag="Q1 2026" text="KEY PERFORMANCE INDICATORS" monthColor="ov-s" />
      <div className="kpi-grid">
        <KpiCard
          label="Q1 Total Sales"
          value={fmt(q1.total_sales_eur)}
          sub="Jan + Feb + Mar"
          monthColor="q"
        />
        <KpiCard
          label="January Sales"
          value={fmt(q1.jan_sales)}
          sub={jan.sales && jan.projection ? `${fmtPct(jan.achievement)} of target` : undefined}
          monthColor="j"
        />
        <KpiCard
          label="February Sales"
          value={fmt(q1.feb_sales)}
          sub={feb.achievement !== null ? `${fmtPct(feb.achievement)} of target` : undefined}
          monthColor="f"
        />
        <KpiCard
          label="March Sales"
          value={fmt(q1.mar_sales)}
          sub={mar.achievement !== null ? `${fmtPct(mar.achievement)} of target` : undefined}
          monthColor="m"
        />
        <KpiCard
          label="Annual Target"
          value={`€${(q1.annual_target_eur || 205000).toLocaleString()}`}
          sub={`Q1 = ${fmtPct(q1.annual_achievement_pct)} achieved`}
          monthColor="q"
        />
        <KpiCard
          label="Q1 Total Visits"
          value={(q1.total_visits_q1 || 0).toLocaleString()}
          sub={`Jan ${q1.total_visits?.jan || 0} · Feb ${q1.total_visits?.feb || 0} · Mar ${q1.total_visits?.mar || 0}`}
          monthColor="q"
        />
        <KpiCard
          label="Drs Converted"
          value={q1.drs_converted_q1 ?? '—'}
          sub={`Jan ${q1.drs_converted?.jan ?? 0} · Feb ${q1.drs_converted?.feb ?? 0} · Mar ${q1.drs_converted?.mar ?? 0}`}
          monthColor="d"
        />
        <KpiCard
          label="Best Month"
          value={q1.best_month || '—'}
          sub={fmt(q1.best_month_sales)}
          monthColor="g"
        />
        <KpiCard
          label="Top Product Q1"
          value={q1.top_product_q1 || '—'}
          sub={fmt(q1.top_product_q1_val)}
          monthColor="q"
        />
      </div>

      {/* ── SALES TREND & PROJECTION ── */}
      <SectionLabel tag="Q1" text="SALES TREND & PROJECTION GAP" monthColor="ov-s" />
      <div className="grid-2">
        <ChartCard
          title="Monthly Sales: Actual vs Projection (€)"
          sub="Jan (blue) · Feb (amber) · Mar (green) | Projection shown as dashed"
          height="h300"
          monthColor="tri"
        >
          <Bar data={salesVsProjData} options={baseOptions({
            plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } }
          })} />
        </ChartCard>
        <ChartCard
          title="Cumulative Q1 Sales Build-up (€)"
          sub="Month-over-month cumulative and projection pace"
          height="h300"
          monthColor="tri"
        >
          <Line data={cumulativeData} options={baseOptions({
            plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } }
          })} />
        </ChartCard>
      </div>

      {/* ── DELEGATE VISITS ── */}
      <SectionLabel tag="Q1" text="VISIT & DELEGATE PERFORMANCE" monthColor="ov-s" />
      <div className="grid-2">
        <ChartCard
          title="Q1 Total Visits by Delegate"
          sub="Aggregate visits across January, February, and March"
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
            {[
              { label: 'January', d: jan, color: COLORS.jan, visits: q1.total_visits?.jan },
              { label: 'February', d: feb, color: COLORS.feb, visits: q1.total_visits?.feb },
              { label: 'March', d: mar, color: COLORS.mar, visits: q1.total_visits?.mar },
            ].map(({ label, d, color, visits }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ width: 3, height: 40, borderRadius: 2, background: color, flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ color, fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{label} 2026</div>
                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Sales <strong style={{ color: 'var(--text)' }}>{fmt(d.sales)}</strong></span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Visits <strong style={{ color: 'var(--text)' }}>{(visits ?? 0).toLocaleString()}</strong></span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Drs Conv. <strong style={{ color: 'var(--good)' }}>{d.drs_converted ?? 0}</strong></span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      Achieved <strong style={{ color: d.achievement >= 80 ? 'var(--good)' : d.achievement >= 60 ? 'var(--warn)' : 'var(--danger)' }}>
                        {fmtPct(d.achievement)}
                      </strong>
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── PRODUCT MIX ── */}
      <SectionLabel tag="Q1" text="PRODUCT MIX EVOLUTION" monthColor="ov-s" />
      <div className="full">
        <ChartCard
          title="All Products — Sales Value Q1 2026 (Jan=Blue · Feb=Amber · Mar=Green)"
          sub="Grouped bar showing each product's performance across all three months"
          height="h340"
          monthColor="tri"
        >
          <Bar data={allProductsData} options={baseOptions({ plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } } })} />
        </ChartCard>
      </div>

      {/* ── MONTH-WISE DEEP COMPARISON ── */}
      <SectionLabel tag="Q1" text="MONTH-WISE DEEP COMPARISON" monthColor="ov-s" />
      <div className="month-trio">
        {[
          { label: 'JANUARY', d: jan, colorCls: 'j', emoji: '🔵', visits: q1.total_visits?.jan },
          { label: 'FEBRUARY', d: feb, colorCls: 'f', emoji: '🟡', visits: q1.total_visits?.feb },
          { label: 'MARCH', d: mar, colorCls: 'm', emoji: '🟢', visits: q1.total_visits?.mar },
        ].map(({ label, d, colorCls, emoji, visits }) => {
          const pctColor = d.achievement !== null && d.achievement !== undefined
            ? (d.achievement >= 80 ? 'var(--good)' : d.achievement >= 60 ? 'var(--warn)' : 'var(--danger)')
            : 'var(--text-muted)'
          return (
            <div key={label} className="month-col">
              <div className={`month-col-hdr ${colorCls}`}>{emoji} {label} 2026</div>
              <div className="month-col-body">
                <div className="stat-row"><span className="stat-lbl">Sales</span><span className="stat-val" style={{ color: `var(--${colorCls === 'j' ? 'jan' : colorCls === 'f' ? 'feb' : 'mar'})` }}>{fmt(d.sales)}</span></div>
                <div className="stat-row"><span className="stat-lbl">Projection</span><span className="stat-val" style={{ color: 'var(--text-muted)' }}>{fmt(d.projection)}</span></div>
                <div className="stat-row"><span className="stat-lbl">Achievement</span><span className="stat-val" style={{ color: pctColor }}>{fmtPct(d.achievement)}</span></div>
                <div className="stat-row"><span className="stat-lbl">Total Visits</span><span className="stat-val">{(visits ?? 0).toLocaleString()}</span></div>
                <div className="stat-row"><span className="stat-lbl">Prescriber Calls</span><span className="stat-val">{d.prescriber_calls ?? '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Pharmacy Calls</span><span className="stat-val">{d.pharmacy_calls ?? '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Drs Converted</span><span className="stat-val" style={{ color: (d.drs_converted || 0) > 0 ? 'var(--good)' : 'var(--danger)' }}>{d.drs_converted ?? 0}</span></div>
                <div className="stat-row"><span className="stat-lbl">Active Delegates</span><span className="stat-val">{d.active_delegates ?? '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Activity Spent</span><span className="stat-val">{d.activity_spent_eur !== null && d.activity_spent_eur !== undefined ? `€${d.activity_spent_eur.toLocaleString()}` : '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Closing Balance</span><span className="stat-val" style={{ color: (d.closing_balance_eur || 0) >= 0 ? 'var(--good)' : 'var(--danger)' }}>{d.closing_balance_eur !== null && d.closing_balance_eur !== undefined ? `€${d.closing_balance_eur.toLocaleString()}` : '—'}</span></div>
                <div className="stat-row"><span className="stat-lbl">Top Product</span><span className="stat-val">{d.top_product ?? '—'}</span></div>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── AI INSIGHTS ── */}
      <SectionLabel tag="Q1" text="KEY INSIGHTS" monthColor="ov-s" />
      <div className="insights-header">
        <span className="ai-label">🤖 AI-Powered Insights · Groq llama-3.1-8b-instant</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {insightsData && (
            <span className={`badge ${insightsData.cached ? 'n' : 'g'}`}>
              {insightsData.cached ? 'Cached' : 'Live'}
            </span>
          )}
          <button
            className="refresh-btn"
            style={{ borderColor: 'rgba(16,185,129,.4)', background: 'rgba(16,185,129,.1)', color: 'var(--mar)' }}
            onClick={() => refreshData.mutate()}
            disabled={refreshData.isPending}
            id="refresh-data-btn"
          >
            {refreshData.isPending ? '⟳ Refreshing...' : '⟳ Refresh Data'}
          </button>
          <button
            className="refresh-btn"
            onClick={() => refreshMut.mutate()}
            disabled={refreshMut.isPending}
            id="regenerate-insights-btn"
          >
            {refreshMut.isPending ? '⟳ Generating...' : '↺ Regenerate'}
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
