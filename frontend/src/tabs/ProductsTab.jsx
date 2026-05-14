import { Bar, Doughnut } from 'react-chartjs-2'
import { useProducts } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import KpiCard from '../components/KpiCard'
import DataTable from '../components/DataTable'
import { baseOptions, baseOptionsNoScale, COLORS, monthColor } from '../utils/chartConfig'
import { MONTH_CONFIG, MONTH_KEYS } from '../utils/monthConfig'

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
  if (isLoading) return <div className="loading">⟳ Loading products data...</div>
  if (isError) return <div className="error">✕ Failed to load products data. Is the backend running?</div>

  const kpis  = data.q1_kpis || {}
  const trend = data.q1_trend || []
  const avq   = data.annual_vs_q1 || []
  const cm    = data.category_mix || {}

  // Derive loaded months in calendar order from month_sales keys
  const monthSales = kpis.month_sales || {}
  const monthUnits = kpis.month_units || {}
  const months = MONTH_KEYS.filter(k => k in monthSales)
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

  // ── Annual target vs YTD achieved ────────────────────────────
  const avqData = {
    labels: avq.map(r => r.product),
    datasets: [
      { label: 'Annual Target', data: avq.map(r => r.annual_target), backgroundColor: 'rgba(148,163,184,0.2)', borderColor: '#94a3b8', borderWidth: 1 },
      { label: 'YTD Achieved',  data: avq.map(r => r.q1_achieved),   backgroundColor: COLORS.q1A, borderColor: COLORS.q1, borderWidth: 1 },
    ],
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
      <div className="grid-2">
        <ChartCard title="Annual Target vs YTD Achieved (€)" sub="Sorted by YTD achievement" height="h300">
          <Bar data={avqData} options={baseOptions({ indexAxis: 'y' })} />
        </ChartCard>
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
