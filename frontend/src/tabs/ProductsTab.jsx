import { Bar, Doughnut } from 'react-chartjs-2'
import { useProducts } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import KpiCard from '../components/KpiCard'
import DataTable from '../components/DataTable'
import { baseOptions, baseOptionsNoScale, COLORS, monthColor } from '../utils/chartConfig'
import { MONTH_CONFIG, MONTH_KEYS } from '../utils/monthConfig'
import { useFilter } from '../context/FilterContext'

function fmt(n, decimals = 0) {
  if (n === null || n === undefined) return '—'
  return `€${Number(n).toLocaleString(undefined, { maximumFractionDigits: decimals })}`
}
function fmtUnits(n) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString()
}

export default function ProductsTab() {
  const { data, isLoading, isError } = useProducts()
  const { activeMonths: filteredMonths } = useFilter()

  const monthSales = data?.q1_kpis?.month_sales || {}
  const months = MONTH_KEYS.filter(k => k in monthSales && filteredMonths.includes(k))

  if (isLoading) return <div className="loading">⟳ Loading products data...</div>
  if (isError) return <div className="error">✕ Failed to load products data. Is the backend running?</div>

  const kpis  = data.q1_kpis || {}
  const trend = data.q1_trend || []
  const avq   = data.annual_vs_q1 || []
  const cm    = data.category_mix || {}

  const monthUnits = kpis.month_units || {}

  const periodLabel = months.length > 0
    ? `${MONTH_CONFIG[months[0]].short} – ${MONTH_CONFIG[months[months.length - 1]].short} 2026`
    : '2026'

  // ── Bar chart: revenue per product per month ─────────────────
  const trendData = {
    labels: trend.map(t => t.product),
    datasets: months.map(mk => {
      const mc = monthColor(mk)
      return {
        label: MONTH_CONFIG[mk].label,
        data: trend.map(t => t[mk] ?? 0),
        backgroundColor: mc.alpha,
        borderColor: mc.solid,
        borderWidth: 1,
      }
    }),
  }


  // ── Doughnut: category mix per loaded month ───────────────────
  const doughnutLabels = months.flatMap(mk => [
    `Tablet (${MONTH_CONFIG[mk].short})`,
    `Injectable (${MONTH_CONFIG[mk].short})`,
  ])
  const doughnutValues = months.flatMap(mk => [
    cm[mk]?.tablet ?? 0,
    cm[mk]?.injectable ?? 0,
  ])
  const doughnutColors = months.flatMap(mk => {
    const mc = monthColor(mk)
    return [mc.soft, mc.solid]
  })
  const doughnutData = {
    labels: doughnutLabels,
    datasets: [{
      data: doughnutValues,
      backgroundColor: doughnutColors,
      borderColor: 'var(--card)',
      borderWidth: 2,
    }],
  }

  // ── Revenue table: one column per loaded month ────────────────
  const tblCols = [
    { key: 'product', label: 'Product' },
    ...months.map(mk => ({ key: mk, label: `${MONTH_CONFIG[mk].short} (€)` })),
    { key: 'total', label: 'Total (€)' },
  ]
  const tblRows = trend.map(t => {
    const monthVals = Object.fromEntries(months.map(mk => [mk, t[mk] ?? 0]))
    const total = months.reduce((s, mk) => s + (t[mk] || 0), 0).toFixed(2)
    return { product: t.product, ...monthVals, total }
  })

  return (
    <div>
      <div className="kpi-grid">
        <KpiCard
          label={`Total Units Sold — ${periodLabel}`}
          value={fmtUnits(kpis.total_units)}
          sub={`${months.map(mk => MONTH_CONFIG[mk].short).join(' + ')} combined`}
          monthColor="q"
        />
        <KpiCard
          label={`Total Sales — ${periodLabel}`}
          value={fmt(kpis.total_sales_eur, 0)}
          sub={`${months.map(mk => MONTH_CONFIG[mk].short).join(' + ')} combined`}
          monthColor="q"
        />
        {months.map(mk => (
          <KpiCard
            key={mk}
            label={`${MONTH_CONFIG[mk].label} Sales`}
            value={fmt(monthSales[mk], 0)}
            sub={`${fmtUnits(monthUnits[mk])} units`}
            monthColor={MONTH_CONFIG[mk].cls}
          />
        ))}
      </div>

      <SectionLabel tag="PRODUCTS" text="PRODUCT REVENUE TREND" monthColor="prod-s" />
      <div className="full">
        <ChartCard
          title={`All Products — ${periodLabel} Revenue Trend`}
          sub="Side-by-side comparison across all loaded months"
          height="h340"
          monthColor="tri"
        >
          <Bar data={trendData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag="PRODUCTS" text="ANNUAL TARGET VS YTD ACHIEVEMENT" monthColor="prod-s" />
      <div className="full">
        <div className="card avq-card">
          <div className="card-title">Annual Target vs YTD Achieved (€)</div>
          <div className="card-sub">Total sales to date vs full-year annual target</div>
          <div className="avq-list">
            {avq.map(row => {
              const achieved = row.ytd_achieved ?? 0
              const hasTarget = row.annual_target != null && row.annual_target > 0
              const pct = hasTarget ? (achieved / row.annual_target) * 100 : null
              const status = pct === null ? 'warn' : pct >= 80 ? 'good' : pct >= 45 ? 'warn' : 'danger'
              const statusLabel = pct === null ? 'NO TARGET' : pct >= 80 ? 'ON TRACK' : pct >= 45 ? 'IN PROGRESS' : 'BEHIND'
              return (
                <div key={row.product} className="avq-row">
                  <div className="avq-left">
                    <div className="avq-product">{row.product}</div>
                    <div className={`avq-status avq-status-${status}`}>{statusLabel}</div>
                  </div>
                  <div className="avq-center">
                    <div className="avq-bar-row">
                      <div className="avq-track">
                        {pct !== null && (
                          <div
                            className={`avq-fill avq-fill-${status}`}
                            style={{ width: `${Math.min(pct, 100)}%` }}
                          />
                        )}
                        <div className="avq-track-label">
                          <span className="avq-achieved-lbl">€{Math.round(achieved).toLocaleString()} achieved</span>
                        </div>
                      </div>
                      <span className="avq-target-lbl">
                        {hasTarget ? `€${Math.round(row.annual_target).toLocaleString()} target` : '— no target'}
                      </span>
                    </div>
                  </div>
                  <div className={`avq-pct avq-pct-${status}`}>
                    {pct !== null ? `${pct.toFixed(1)}%` : '—'}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <SectionLabel tag="PRODUCTS" text="CATEGORY MIX" monthColor="prod-s" />
      <div className="grid-2">
        <ChartCard
          title={`Category Mix — Tablet vs Injectable (${periodLabel})`}
          sub="By month × category"
          height="h300"
        >
          <Doughnut data={doughnutData} options={baseOptionsNoScale()} />
        </ChartCard>
      </div>

      <SectionLabel tag="PRODUCTS" text="COMPLETE PRODUCT DATA" monthColor="prod-s" />
      <DataTable
        title={`Product Revenue — ${periodLabel}`}
        badge={{ text: 'All Products', variant: 'q' }}
        columns={tblCols}
        rows={tblRows}
      />
    </div>
  )
}
