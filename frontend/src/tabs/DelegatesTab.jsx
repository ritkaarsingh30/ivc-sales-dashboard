import { Bar, Line } from 'react-chartjs-2'
import { useDelegates } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import { baseOptions, COLORS } from '../utils/chartConfig'

function ctcColor(ratio) {
  if (ratio === null || ratio === undefined) return COLORS.neutral
  if (ratio > 100) return COLORS.danger
  if (ratio > 50) return COLORS.warn
  return COLORS.good
}

export default function DelegatesTab() {
  const { data, isLoading, isError } = useDelegates()
  if (isLoading) return <div className="loading">⟳ Loading delegates data...</div>
  if (isError) return <div className="error">✕ Failed to load delegates data. Is the backend running?</div>

  const vc = data.visit_counts || []
  const orders = data.orders || []
  const apd = data.avg_per_day || []
  const ctc = data.ctc_ratios || []

  // Visit counts grouped bar
  const vcData = {
    labels: vc.map(r => r.mr),
    datasets: [
      { label: 'January',  data: vc.map(r => r.jan || 0), backgroundColor: COLORS.janA, borderColor: COLORS.jan, borderWidth: 1 },
      { label: 'February', data: vc.map(r => r.feb || 0), backgroundColor: COLORS.febA, borderColor: COLORS.feb, borderWidth: 1 },
      { label: 'March',    data: vc.map(r => r.mar || 0), backgroundColor: COLORS.marA, borderColor: COLORS.mar, borderWidth: 1 },
    ]
  }

  // Orders bar
  const ordData = {
    labels: orders.map(r => r.mr),
    datasets: [
      { label: 'Jan (€)', data: orders.map(r => r.jan_eur || 0), backgroundColor: COLORS.janA },
      { label: 'Mar (€)', data: orders.map(r => r.mar_eur || 0), backgroundColor: COLORS.marA },
    ]
  }

  // Avg calls/day line
  const monthLabels = apd.map(r => r.month)
  const delegateNames = vc.length > 0
    ? Object.keys(apd[0] || {}).filter(k => k !== 'month' && k !== 'overall')
    : []

  const delegateColors = [COLORS.jan, COLORS.feb, COLORS.mar, COLORS.q1, COLORS.pink, COLORS.sky]
  const apdDatasets = [
    { label: 'Overall', data: apd.map(r => r.overall), borderColor: COLORS.neutral, backgroundColor: 'transparent', borderDash: [4,2], tension: 0.3 },
    ...delegateNames.map((name, i) => ({
      label: name.toUpperCase(),
      data: apd.map(r => r[name]),
      borderColor: delegateColors[i % delegateColors.length],
      backgroundColor: 'transparent',
      tension: 0.3,
    }))
  ]

  const apdData = { labels: monthLabels, datasets: apdDatasets }

  // CTC ratio bar
  const ctcLabels = ctc.map(r => r.mr)
  const ctcJan = ctc.map(r => r.jan)
  const ctcFeb = ctc.map(r => r.feb)
  const ctcMar = ctc.map(r => r.mar)

  const ctcData = {
    labels: ctcLabels,
    datasets: [
      { label: 'January CTC %',  data: ctcJan, backgroundColor: ctcJan.map(v => ctcColor(v) + '99'), borderColor: ctcJan.map(v => ctcColor(v)), borderWidth: 1 },
      { label: 'February CTC %', data: ctcFeb, backgroundColor: ctcFeb.map(v => ctcColor(v) + '55'), borderColor: ctcFeb.map(v => ctcColor(v)), borderWidth: 1 },
      { label: 'March CTC %',    data: ctcMar, backgroundColor: ctcMar.map(v => ctcColor(v) + '99'), borderColor: ctcMar.map(v => ctcColor(v)), borderWidth: 1 },
    ]
  }

  const ctcOptions = {
    ...baseOptions(),
    plugins: {
      ...baseOptions().plugins,
      annotation: {
        annotations: {
          target: {
            type: 'line',
            yMin: 25, yMax: 25,
            borderColor: COLORS.danger,
            borderWidth: 2, borderDash: [6, 4],
          }
        }
      }
    }
  }

  const delCols = [
    { key: 'fullname', label: 'Delegate' },
    { key: 'jan', label: 'Jan Visits' },
    { key: 'feb', label: 'Feb Visits' },
    { key: 'mar', label: 'Mar Visits' },
    { key: 'total', label: 'Q1 Total' },
  ]
  const delRows = vc.map(r => ({
    fullname: r.fullname || r.mr,
    jan: r.jan || 0,
    feb: r.feb || 0,
    mar: r.mar || 0,
    total: ((r.jan||0)+(r.feb||0)+(r.mar||0)),
  }))

  return (
    <div>
      <SectionLabel tag="DELEGATES" text="VISIT COUNTS — CROSS-MONTH" monthColor="del-s" />
      <div className="full">
        <ChartCard title="Visit Counts by Delegate — Q1 2026" sub="Jan · Feb · Mar grouped bars" height="h300">
          <Bar data={vcData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag="DELEGATES" text="ORDERS & AVG CALLS PER DAY" monthColor="del-s" />
      <div className="grid-2">
        <ChartCard title="Monthly Orders by Delegate (€)" height="h300">
          <Bar data={ordData} options={baseOptions()} />
        </ChartCard>
        <ChartCard title="Avg Calls per Day — Monthly Trend" sub="Solid = individual MRs · Dashed = overall" height="h300">
          <Line data={apdData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag="DELEGATES" text="CTC RATIOS — ALL MONTHS" monthColor="del-s" />
      <div className="full">
        <ChartCard title="⚠️ CTC Ratio by Delegate — Q1 2026" sub="Target max 25% — all delegates far above" height="h250">
          <Bar data={ctcData} options={ctcOptions} />
        </ChartCard>
      </div>

      <SectionLabel tag="DELEGATES" text="CROSS-MONTH VISIT SUMMARY" monthColor="del-s" />
      <DataTable
        title="Delegate Visit Summary — Q1 2026"
        badge={{ text: 'Cross-Month', variant: 'q' }}
        columns={delCols}
        rows={delRows}
      />
    </div>
  )
}
