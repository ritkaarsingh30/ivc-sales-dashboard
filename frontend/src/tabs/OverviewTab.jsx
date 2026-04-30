import { Bar } from 'react-chartjs-2'
import { useOverview, useInsights, useRefreshInsights, useRefreshData } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import InsightBox from '../components/InsightBox'
import ChartCard from '../components/ChartCard'
import { baseOptions, COLORS } from '../utils/chartConfig'

function fmt(n) { return n !== null && n !== undefined ? `€${Number(n).toLocaleString()}` : '—' }
function fmtPct(n) { return n !== null && n !== undefined ? `${n}%` : '—' }

function MonthCol({ data, label, colorCls, emoji }) {
  const d = data || {}
  const pctColor = d.achievement !== null && d.achievement !== undefined
    ? (d.achievement >= 80 ? 'var(--good)' : d.achievement >= 60 ? 'var(--warn)' : 'var(--danger)')
    : 'var(--text-muted)'

  return (
    <div className="month-col">
      <div className={`month-col-hdr ${colorCls}`}>{emoji} {label} 2026</div>
      <div className="month-col-body">
        <div className="stat-row"><span className="stat-lbl">Sales</span><span className="stat-val" style={{color:`var(--${colorCls === 'j' ? 'jan' : colorCls === 'f' ? 'feb' : 'mar'})`}}>{fmt(d.sales)}</span></div>
        <div className="stat-row"><span className="stat-lbl">Projection</span><span className="stat-val" style={{color:'var(--text-muted)'}}>{fmt(d.projection)}</span></div>
        <div className="stat-row"><span className="stat-lbl">Achievement</span><span className="stat-val" style={{color:pctColor}}>{fmtPct(d.achievement)}</span></div>
        <div className="stat-row"><span className="stat-lbl">Total Visits</span><span className="stat-val" style={{color:`var(--${colorCls === 'j' ? 'jan' : colorCls === 'f' ? 'feb' : 'mar'})`}}>{d.visits ?? '—'}</span></div>
        <div className="stat-row"><span className="stat-lbl">Prescriber Calls</span><span className="stat-val">{d.prescriber_calls ?? '—'}</span></div>
        <div className="stat-row"><span className="stat-lbl">Pharmacy Calls</span><span className="stat-val">{d.pharmacy_calls ?? '—'}</span></div>
        <div className="stat-row"><span className="stat-lbl">Drs Converted</span><span className="stat-val" style={{color: d.drs_converted > 0 ? 'var(--good)' : 'var(--danger)'}}>{d.drs_converted ?? 0}{d.drs_converted > 0 ? ' ⭐' : ''}</span></div>
        <div className="stat-row"><span className="stat-lbl">Avg Visits/Day</span><span className="stat-val">{d.avg_visits_day ?? '—'}</span></div>
        <div className="stat-row"><span className="stat-lbl">Activity Spent</span><span className="stat-val">{d.activity_spent_eur !== null && d.activity_spent_eur !== undefined ? `€${d.activity_spent_eur.toLocaleString()} (FCFA ${(d.activity_spent_fcfa/1000).toFixed(0)}K)` : '—'}</span></div>
        <div className="stat-row"><span className="stat-lbl">Closing Balance</span><span className="stat-val" style={{color: d.closing_balance_eur >= 0 ? 'var(--good)' : 'var(--danger)'}}>
          {d.closing_balance_eur !== null && d.closing_balance_eur !== undefined ? `€${d.closing_balance_eur.toLocaleString()}` : '—'}
          {d.closing_balance_eur < 0 ? ' ⚠️' : ''}
        </span></div>
        <div className="stat-row"><span className="stat-lbl">Active Delegates</span><span className="stat-val">{d.active_delegates ?? '—'}</span></div>
        <div className="stat-row"><span className="stat-lbl">Top Product</span><span className="stat-val">{d.top_product ?? '—'}</span></div>
      </div>
    </div>
  )
}

export default function OverviewTab() {
  const { data: ov, isLoading, isError } = useOverview()
  const { data: insightsData, isLoading: insightsLoading } = useInsights()
  const refreshMut = useRefreshInsights()
  const refreshData = useRefreshData()

  if (isLoading) return <div className="loading">⟳ Loading Q1 overview data...</div>
  if (isError) return <div className="error">✕ Failed to load overview. Is the backend running?</div>

  const mc = ov.month_comparison || []
  const jan = mc[0] || {}
  const feb = mc[1] || {}
  const mar = mc[2] || {}
  const trend = ov.all_products_trend || []

  // All products grouped bar chart
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

  return (
    <div>
      <SectionLabel tag="Q1 2026" text="MONTH-WISE DEEP COMPARISON" monthColor="ov-s" />
      <div className="month-trio">
        <MonthCol data={jan} label="JANUARY" colorCls="j" emoji="🔵" />
        <MonthCol data={feb} label="FEBRUARY" colorCls="f" emoji="🟡" />
        <MonthCol data={mar} label="MARCH" colorCls="m" emoji="🟢" />
      </div>

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
