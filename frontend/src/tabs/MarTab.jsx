import { Bar } from 'react-chartjs-2'
import { useMonth } from '../hooks/useDashboard'
import KpiCard from '../components/KpiCard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import SalesOutcomeCell from '../components/SalesOutcomeCell'
import TourPlanSection from '../components/TourPlanSection'
import VisitTrackerSection from '../components/VisitTrackerSection'
import { baseOptions, COLORS, buildCallChartData, buildCallChartOptions } from '../utils/chartConfig'
import { MONTH_CONFIG, DELEGATE_COLS, AE_COLS, calcChange, fmtChange, changeDir } from '../utils/monthConfig'

const CFG = MONTH_CONFIG.mar
const PREV = MONTH_CONFIG[CFG.prev]

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

function ctcColor(ratio) {
  if (ratio === null || ratio === undefined) return COLORS.neutral
  if (ratio > 100) return COLORS.danger
  if (ratio > 50) return COLORS.warn
  return COLORS.good
}

export default function MarTab() {
  const { data, isLoading, isError } = useMonth('mar')
  const { data: prevData } = useMonth(CFG.prev)

  if (isLoading) return <div className="loading">⟳ Loading {CFG.label} data...</div>
  if (isError) return <div className="error">✕ Failed to load {CFG.label} data. Is the backend running?</div>

  const k  = data.kpis || {}
  const pk = prevData?.kpis || {}
  const cb = data.call_breakdown || {}
  const tva = data.target_vs_achieved || []
  const ps  = data.product_sales || []
  const dt  = data.delegate_table || []
  const ae  = data.activity_expenses || []
  const ds  = data.distributor_sales || []
  const tp  = data.tour_plan || {}
  const vt  = data.visit_tracker || {}

  const chgSales  = calcChange(k.total_sales_eur,      pk.total_sales_eur)
  const chgTab    = calcChange(k.tablet_sales_eur,     pk.tablet_sales_eur)
  const chgInj    = calcChange(k.injectable_sales_eur, pk.injectable_sales_eur)
  const chgVisits = calcChange(k.total_visits,          pk.total_visits)
  const chgPres   = calcChange(k.prescriber_calls,      pk.prescriber_calls)
  const chgPharm  = calcChange(k.pharmacy_calls,        pk.pharmacy_calls)

  const tvaData = {
    labels: tva.map(r => r.product),
    datasets: [
      { label: 'Target',   data: tva.map(r => r.target),   backgroundColor: 'rgba(16,185,129,0.2)', borderColor: COLORS.mar, borderWidth: 1 },
      { label: 'Achieved', data: tva.map(r => r.achieved),  backgroundColor: COLORS.marA,           borderColor: COLORS.mar, borderWidth: 1 },
    ],
  }

  const psData = {
    labels: ps.map(r => r.product),
    datasets: [{
      label: 'Sales (€)',
      data: ps.map(r => r.sales_eur),
      backgroundColor: COLORS.marA,
      borderColor: COLORS.mar,
      borderWidth: 1,
    }],
  }

  const ctcData = {
    labels: dt.map(r => r.name?.split(' ').pop() || r.name),
    datasets: [{
      label: 'CTC Ratio (%)',
      data: dt.map(r => r.ctc_ratio),
      backgroundColor: dt.map(r => ctcColor(r.ctc_ratio) + '99'),
      borderColor: dt.map(r => ctcColor(r.ctc_ratio)),
      borderWidth: 2,
    }],
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
            label: { content: '25% Target', enabled: true, color: COLORS.danger, font: { size: 10 } },
          },
        },
      },
    },
  }

  const aeRows = ae.map(r => ({
    ...r,
    activity_badge:      <span className={`act-type-badge ${actBadgeClass(r.activity)}`}>{r.activity}</span>,
    sales_outcome_cell:  <SalesOutcomeCell items={r.sales_outcome} />,
    sales_value_fmt:     r.sales_outcome_eur > 0 ? `€${Number(r.sales_outcome_eur).toLocaleString()}` : '—',
    visits_fmt:          r.num_visits > 0 ? r.num_visits : '—',
  }))

  const dsCols = [
    { key: 'distributor', label: 'Distributor' },
    { key: 'sales_eur', label: 'Sales (€)' },
    { key: 'closing_stock_eur', label: 'Closing Stock (€)' },
    { key: 'share_pct_badge', label: 'Share %' },
  ]
  const dsRows = ds.map(r => ({ ...r, share_pct_badge: <Badge text={`${r.share_pct}%`} variant={CFG.cls} /> }))

  const isOverrun = (k.closing_balance_eur || 0) < 0

  return (
    <div>
      <SectionLabel tag={CFG.label.toUpperCase()} text="KPI SUMMARY" monthColor={CFG.sectionCls} />
      <div className="kpi-grid">
        <KpiCard label="Total Sales"       value={`€${(k.total_sales_eur||0).toLocaleString()}`}
          change={fmtChange(chgSales)}  changeDir={changeDir(chgSales)} monthColor={CFG.cls} />
        <KpiCard label="Sales Target"
          value={k.total_target_eur != null ? `€${(k.total_target_eur||0).toLocaleString()}` : '—'}
          sub={k.achievement_pct != null ? `${k.achievement_pct}% achieved` : 'No target set'}
          monthColor={k.achievement_pct >= 100 ? 'g' : CFG.cls} />
        <KpiCard label="Tablet Sales"      value={`€${(k.tablet_sales_eur||0).toLocaleString()}`}
          sub={`${((k.tablet_sales_eur||0)/(k.total_sales_eur||1)*100).toFixed(1)}% of total`}
          change={fmtChange(chgTab)} changeDir={changeDir(chgTab)} monthColor={CFG.cls} />
        <KpiCard label="Injectable Sales"  value={`€${(k.injectable_sales_eur||0).toLocaleString()}`}
          sub={`${((k.injectable_sales_eur||0)/(k.total_sales_eur||1)*100).toFixed(1)}% of total`}
          change={fmtChange(chgInj)} changeDir={changeDir(chgInj)} monthColor={CFG.cls} />
        <KpiCard label="Total Visits"      value={k.total_visits ?? '—'}
          change={fmtChange(chgVisits)} changeDir={changeDir(chgVisits)} monthColor={CFG.cls} />
        <KpiCard label="Prescriber Calls"  value={k.prescriber_calls ?? '—'}
          change={fmtChange(chgPres)} changeDir={changeDir(chgPres)} monthColor={CFG.cls} />
        <KpiCard label="Pharmacy Calls"    value={k.pharmacy_calls ?? '—'}
          change={fmtChange(chgPharm)} changeDir={changeDir(chgPharm)} monthColor={CFG.cls} />
        <KpiCard label="Drs Converted"     value={k.drs_converted ?? 0} monthColor="d" />
        <KpiCard label={isOverrun ? 'Budget Overrun ⚠️' : 'Closing Balance'}
          value={`€${(k.closing_balance_eur||0).toLocaleString()}`}
          sub={`FCFA ${(k.closing_balance_fcfa||0).toLocaleString()}`}
          monthColor={isOverrun ? 'd' : CFG.cls} />
        <KpiCard label="Activity Spent"    value={`€${(k.activity_spent_eur||0).toLocaleString()}`}
          sub={`FCFA ${(k.activity_spent_fcfa||0).toLocaleString()}`} monthColor={CFG.cls} />
      </div>

      <SectionLabel tag={CFG.label.toUpperCase()} text="TARGET VS ACHIEVED" monthColor={CFG.sectionCls} />
      <div className="full">
        <ChartCard title={`Product-wise Target vs Achieved Units — ${CFG.label}`}
          sub={`vs ${PREV.label}`} height="h300" monthColor={CFG.cls}>
          <Bar data={tvaData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag={CFG.label.toUpperCase()} text="SALES & CALL BREAKDOWN" monthColor={CFG.sectionCls} />
      <div className="grid-2">
        <ChartCard title={`Product Sales Value (€) — ${CFG.label}`} height="h300" monthColor={CFG.cls}>
          <Bar data={psData} options={baseOptions({ indexAxis: 'y', plugins: { legend: { display: false } } })} />
        </ChartCard>
        <ChartCard title={`Delegate Call Breakdown — ${CFG.label}`} sub="Prescriber · Non-Prescriber · Pharmacy" height="h300" monthColor={CFG.cls}>
          <Bar data={buildCallChartData(cb)} options={buildCallChartOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag={CFG.label.toUpperCase()} text="DELEGATE PERFORMANCE TABLE" monthColor={CFG.sectionCls} />
      <DataTable title={`${CFG.label} — Delegate KPIs`}
        badge={{ text: `${dt.length} Active`, variant: CFG.cls }}
        borderColor={CFG.color} columns={DELEGATE_COLS} rows={dt} />

      <SectionLabel tag={CFG.label.toUpperCase()} text="CTC RATIO ANALYSIS" monthColor={CFG.sectionCls} />
      <div className="full">
        <ChartCard title={`⚠️ CTC Ratio by Delegate — ${CFG.label}`}
          sub="Red dashed = 25% target" height="h250" monthColor={CFG.cls}>
          <Bar data={ctcData} options={ctcOptions} />
        </ChartCard>
      </div>

      <SectionLabel tag={CFG.label.toUpperCase()} text="ACTIVITY EXPENSE DETAILS" monthColor={CFG.sectionCls} />
      <DataTable title={`Activity Expenses — ${CFG.label} 2026`}
        badge={{ text: `${isOverrun ? '⚠️ OVERRUN · ' : ''}FCFA ${(k.activity_spent_fcfa||0).toLocaleString()} | €${(k.activity_spent_eur||0).toLocaleString()}`, variant: isOverrun ? 'd' : CFG.cls }}
        borderColor={CFG.color} columns={AE_COLS} rows={aeRows} />

      <SectionLabel tag={CFG.label.toUpperCase()} text="DISTRIBUTOR-WISE SALES" monthColor={CFG.sectionCls} />
      <DataTable title={`Sales by Distributor — ${CFG.label} 2026`} borderColor={CFG.color} columns={dsCols} rows={dsRows} />

      <TourPlanSection tourPlan={tp} cfg={CFG} />
      <VisitTrackerSection visitTracker={vt} cfg={CFG} />
    </div>
  )
}
