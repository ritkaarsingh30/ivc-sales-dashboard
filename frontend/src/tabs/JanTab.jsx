import { Bar } from 'react-chartjs-2'
import { useMonth } from '../hooks/useDashboard'
import KpiCard from '../components/KpiCard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import { baseOptions, COLORS } from '../utils/chartConfig'
import { MONTH_CONFIG, calcChange, fmtChange, changeDir } from '../utils/monthConfig'

const CFG = MONTH_CONFIG.jan

function actBadgeClass(act) {
  const a = (act || '').toUpperCase()
  if (a.includes('COMMISSION')) return 'act-commission'
  if (a.includes('MOTIVATION')) return 'act-motivation'
  if (a.includes('PETIT')) return 'act-petit'
  if (a.includes('GARD')) return 'act-gard'
  if (a.includes('SAMPLE')) return 'act-sample'
  if (a.includes('PARTNERSHIP')) return 'act-partnership'
  return 'act-other'
}

export default function JanTab() {
  const { data, isLoading, isError } = useMonth('jan')
  if (isLoading) return <div className="loading">⟳ Loading {CFG.label} data...</div>
  if (isError) return <div className="error">✕ Failed to load {CFG.label} data. Is the backend running?</div>

  const k = data.kpis || {}
  const cb = data.call_breakdown || {}
  const tva = data.target_vs_achieved || []
  const ps = data.product_sales || []
  const dt = data.delegate_table || []
  const ae = data.activity_expenses || []
  const ds = data.distributor_sales || []

  const tvaData = {
    labels: tva.map(r => r.product),
    datasets: [
      { label: 'Target',   data: tva.map(r => r.target),   backgroundColor: 'rgba(59,130,246,0.2)', borderColor: COLORS.jan, borderWidth: 1 },
      { label: 'Achieved', data: tva.map(r => r.achieved),  backgroundColor: COLORS.janA, borderColor: COLORS.jan, borderWidth: 1 },
    ]
  }

  const psData = {
    labels: ps.map(r => r.product),
    datasets: [{
      label: 'Sales (€)',
      data: ps.map(r => r.sales_eur),
      backgroundColor: COLORS.janA,
      borderColor: COLORS.jan,
      borderWidth: 1,
    }]
  }

  const callData = {
    labels: cb.labels || [],
    datasets: [
      { label: 'Prescriber',     data: cb.prescriber || [],     backgroundColor: COLORS.q1A },
      { label: 'Non-Prescriber', data: cb.non_prescriber || [], backgroundColor: COLORS.janA },
      { label: 'Pharmacy',       data: cb.pharmacy || [],        backgroundColor: 'rgba(34,197,94,0.5)' },
    ]
  }

  const delCols = [
    { key: 'name', label: 'Delegate' }, { key: 'territory', label: 'Territory' },
    { key: 'total_calls', label: 'Total Calls' }, { key: 'prescriber', label: 'Prescriber' },
    { key: 'non_prescriber', label: 'Non-Pres.' }, { key: 'pharmacy', label: 'Pharmacy' },
    { key: 'days_worked', label: 'Days' }, { key: 'avg_per_day', label: 'Avg/Day' },
    { key: 'orders_eur', label: 'Orders (€)' }, { key: 'ctc_eur', label: 'CTC (€)' },
    { key: 'ctc_ratio', label: 'CTC Ratio' }, { key: 'drs_converted', label: 'Drs Conv.' },
  ]

  const aeCols = [
    { key: 'sn', label: '#' }, { key: 'doctor', label: 'Doctor/Contact' },
    { key: 'hospital', label: 'Hospital' }, { key: 'speciality', label: 'Speciality' },
    { key: 'activity_badge', label: 'Activity' }, { key: 'products', label: 'Products' },
    { key: 'amount_fcfa', label: 'FCFA' }, { key: 'amount_eur', label: '€' },
    { key: 'responsible', label: 'Responsible' },
  ]

  const aeRows = ae.map(r => ({
    ...r,
    activity_badge: <span className={`act-type-badge ${actBadgeClass(r.activity)}`}>{r.activity}</span>
  }))

  const dsCols = [
    { key: 'distributor', label: 'Distributor' },
    { key: 'sales_eur', label: 'Sales (€)' },
    { key: 'closing_stock_eur', label: 'Closing Stock (€)' },
    { key: 'share_pct_badge', label: 'Share %' },
  ]
  const dsRows = ds.map(r => ({ ...r, share_pct_badge: <Badge text={`${r.share_pct}%`} variant={CFG.cls} /> }))

  return (
    <div>
      <SectionLabel tag={CFG.label.toUpperCase()} text="KPI SUMMARY" monthColor={CFG.sectionCls} />
      <div className="kpi-grid">
        <KpiCard label="Total Sales"       value={`€${(k.total_sales_eur||0).toLocaleString()}`} monthColor={CFG.cls} />
        <KpiCard label="Tablet Sales"      value={`€${(k.tablet_sales_eur||0).toLocaleString()}`}
          sub={`${((k.tablet_sales_eur||0)/(k.total_sales_eur||1)*100).toFixed(1)}% of total`} monthColor={CFG.cls} />
        <KpiCard label="Injectable Sales"  value={`€${(k.injectable_sales_eur||0).toLocaleString()}`}
          sub={`${((k.injectable_sales_eur||0)/(k.total_sales_eur||1)*100).toFixed(1)}% of total`} monthColor={CFG.cls} />
        <KpiCard label="Total Visits"      value={k.total_visits ?? '—'} sub={`${dt.length} delegates`} monthColor={CFG.cls} />
        <KpiCard label="Prescriber Calls"  value={k.prescriber_calls ?? '—'} monthColor={CFG.cls} />
        <KpiCard label="Pharmacy Calls"    value={k.pharmacy_calls ?? '—'} monthColor={CFG.cls} />
        <KpiCard label="Drs Converted"     value={k.drs_converted ?? 0} monthColor="d" />
        <KpiCard label="Avg Visits/Day"    value={k.avg_visits_day ?? '—'} monthColor={CFG.cls} />
        <KpiCard label="Activity Spent"    value={`€${(k.activity_spent_eur||0).toLocaleString()}`}
          sub={`FCFA ${(k.activity_spent_fcfa||0).toLocaleString()}`} monthColor={CFG.cls} />
        <KpiCard label="Closing Balance"   value={`€${(k.closing_balance_eur||0).toLocaleString()}`}
          sub={`FCFA ${(k.closing_balance_fcfa||0).toLocaleString()}`}
          monthColor={(k.closing_balance_eur||0) < 0 ? 'd' : CFG.cls} />
      </div>

      <SectionLabel tag={CFG.label.toUpperCase()} text="TARGET VS ACHIEVED — PRODUCT WISE" monthColor={CFG.sectionCls} />
      <div className="full">
        <ChartCard title={`Product-wise Target vs Achieved Units — ${CFG.label}`} sub="Blue = Target · Filled = Achieved" height="h300" monthColor={CFG.cls}>
          <Bar data={tvaData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag={CFG.label.toUpperCase()} text="SALES & DELEGATE BREAKDOWN" monthColor={CFG.sectionCls} />
      <div className="grid-2">
        <ChartCard title={`Product Sales Value (€) — ${CFG.label}`} sub="Top products by revenue" height="h300" monthColor={CFG.cls}>
          <Bar data={psData} options={baseOptions({ indexAxis: 'y', plugins: { legend: { display: false } } })} />
        </ChartCard>
        <ChartCard title={`Delegate Performance — ${CFG.label}`} sub="Calls, pharmacy visits by delegate" height="h300" monthColor={CFG.cls}>
          <Bar data={callData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag={CFG.label.toUpperCase()} text="DELEGATE PERFORMANCE TABLE" monthColor={CFG.sectionCls} />
      <DataTable title={`${CFG.label} — Delegate KPIs`} badge={{ text: `${dt.length} Active`, variant: CFG.cls }}
        borderColor={CFG.color} columns={delCols} rows={dt} />

      <SectionLabel tag={CFG.label.toUpperCase()} text="ACTIVITY EXPENSE DETAILS" monthColor={CFG.sectionCls} />
      <DataTable title={`Activity Expenses — ${CFG.label} 2026`}
        badge={{ text: `FCFA ${(k.activity_spent_fcfa||0).toLocaleString()} | €${(k.activity_spent_eur||0).toLocaleString()}`, variant: CFG.cls }}
        borderColor={CFG.color} columns={aeCols} rows={aeRows} />

      <SectionLabel tag={CFG.label.toUpperCase()} text="DISTRIBUTOR-WISE SALES" monthColor={CFG.sectionCls} />
      <DataTable title={`Sales by Distributor — ${CFG.label} 2026`} borderColor={CFG.color} columns={dsCols} rows={dsRows} />
    </div>
  )
}
