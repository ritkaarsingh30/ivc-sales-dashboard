import { Bar, Doughnut } from 'react-chartjs-2'
import { useProducts } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import KpiCard from '../components/KpiCard'
import DataTable from '../components/DataTable'
import { baseOptions, baseOptionsNoScale, COLORS, PALETTE } from '../utils/chartConfig'

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

  const kpis = data.q1_kpis || {}
  const trend = data.q1_trend || []
  const avq = data.annual_vs_q1 || []
  const cm = data.category_mix || {}

  const trendData = {
    labels: trend.map(t => t.product),
    datasets: [
      { label: 'January',  data: trend.map(t => t.jan), backgroundColor: COLORS.janA, borderColor: COLORS.jan, borderWidth: 1 },
      { label: 'February', data: trend.map(t => t.feb), backgroundColor: COLORS.febA, borderColor: COLORS.feb, borderWidth: 1 },
      { label: 'March',    data: trend.map(t => t.mar), backgroundColor: COLORS.marA, borderColor: COLORS.mar, borderWidth: 1 },
    ]
  }

  const avqData = {
    labels: avq.map(r => r.product),
    datasets: [
      { label: 'Annual Target', data: avq.map(r => r.annual_target), backgroundColor: 'rgba(148,163,184,0.2)', borderColor: '#94a3b8', borderWidth: 1 },
      { label: 'Q1 Achieved',   data: avq.map(r => r.q1_achieved),   backgroundColor: COLORS.q1A, borderColor: COLORS.q1, borderWidth: 1 },
    ]
  }

  const doughnutData = {
    labels: ['Tablet (Jan)', 'Injectable (Jan)', 'Tablet (Feb)', 'Injectable (Feb)', 'Tablet (Mar)', 'Injectable (Mar)'],
    datasets: [{
      data: [
        cm.jan?.tablet || 0, cm.jan?.injectable || 0,
        cm.feb?.tablet || 0, cm.feb?.injectable || 0,
        cm.mar?.tablet || 0, cm.mar?.injectable || 0,
      ],
      backgroundColor: [COLORS.janS, COLORS.jan, COLORS.febS, COLORS.feb, COLORS.marS, COLORS.mar],
      borderColor: 'var(--card)',
      borderWidth: 2,
    }]
  }

  const tblCols = [
    { key: 'product', label: 'Product' },
    { key: 'jan', label: 'Jan (€)' },
    { key: 'feb', label: 'Feb (€)' },
    { key: 'mar', label: 'Mar (€)' },
    { key: 'total', label: 'Q1 Total (€)' },
  ]
  const tblRows = trend.map(t => ({
    product: t.product,
    jan: t.jan,
    feb: t.feb,
    mar: t.mar,
    total: ((t.jan||0)+(t.feb||0)+(t.mar||0)).toFixed(2),
  }))

  return (
    <div>
      <div className="kpi-grid">
        <KpiCard
          label="Total Units Sold — Q1"
          value={fmtUnits(kpis.total_units)}
          sub="Jan + Feb + Mar combined"
          monthColor="q"
        />
        <KpiCard
          label="Total Sales — Q1"
          value={fmt(kpis.total_sales_eur, 0)}
          sub="Jan + Feb + Mar combined"
          monthColor="q"
        />
        <KpiCard
          label="January Sales"
          value={fmt(kpis.jan_sales, 0)}
          sub={`${fmtUnits(kpis.jan_units)} units`}
          monthColor="j"
        />
        <KpiCard
          label="February Sales"
          value={fmt(kpis.feb_sales, 0)}
          sub={`${fmtUnits(kpis.feb_units)} units`}
          monthColor="f"
        />
        <KpiCard
          label="March Sales"
          value={fmt(kpis.mar_sales, 0)}
          sub={`${fmtUnits(kpis.mar_units)} units`}
          monthColor="m"
        />
      </div>

      <SectionLabel tag="PRODUCTS" text="Q1 PRODUCT TREND" monthColor="prod-s" />
      <div className="full">
        <ChartCard title="All Products — Q1 2026 Revenue Trend (Jan · Feb · Mar)" sub="Side-by-side comparison across all months" height="h340" monthColor="tri">
          <Bar data={trendData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag="PRODUCTS" text="ANNUAL TARGET VS Q1 ACHIEVEMENT" monthColor="prod-s" />
      <div className="grid-2">
        <ChartCard title="Annual Target vs Q1 Achieved (€)" sub="Sorted by Q1 achievement" height="h300">
          <Bar data={avqData} options={baseOptions({ indexAxis: 'y' })} />
        </ChartCard>
        <ChartCard title="Q1 Category Mix — Tablet vs Injectable" sub="By month × category" height="h300">
          <Doughnut data={doughnutData} options={baseOptionsNoScale()} />
        </ChartCard>
      </div>

      <SectionLabel tag="PRODUCTS" text="COMPLETE PRODUCT DATA" monthColor="prod-s" />
      <DataTable
        title="Product Revenue — Q1 2026"
        badge={{ text: 'All Products', variant: 'q' }}
        columns={tblCols}
        rows={tblRows}
      />
    </div>
  )
}
