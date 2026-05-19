import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { useExpenses } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import SalesOutcomeCell from '../components/SalesOutcomeCell'
import { baseOptions, baseOptionsNoScale, COLORS, PALETTE } from '../utils/chartConfig'
import { MONTH_CONFIG } from '../utils/monthConfig'
import { useFilter } from '../context/FilterContext'

const FCFA_TO_EUR = 655.97

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

function fmtFcfa(n) {
  return n ? Number(n).toLocaleString() : '—'
}
function fmtEur(n) {
  return n ? `€${Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '—'
}

const EXP_COLS = [
  { key: 'sn',                 label: '#' },
  { key: 'doctor',             label: 'Doctor / Contact' },
  { key: 'hospital',           label: 'Hospital' },
  { key: 'activity_badge',     label: 'Activity' },
  { key: 'products',           label: 'Products' },
  { key: 'amount_fcfa_fmt',    label: 'FCFA' },
  { key: 'amount_eur_fmt',     label: 'Amount €' },
  { key: 'sales_outcome_cell', label: 'Sales Outcome' },
  { key: 'sales_value_fmt',    label: 'Sales Value €' },
  { key: 'visits_fmt',         label: 'Visits' },
  { key: 'responsible',        label: 'Responsible' },
]

function buildRows(rows) {
  return rows.map(r => ({
    ...r,
    activity_badge:     <span className={`act-type-badge ${actBadgeClass(r.activity)}`}>{r.activity}</span>,
    amount_fcfa_fmt:    fmtFcfa(r.amount_fcfa),
    amount_eur_fmt:     fmtEur(r.amount_eur),
    sales_outcome_cell: <SalesOutcomeCell items={r.sales_outcome} />,
    sales_value_fmt:    r.sales_outcome_eur > 0 ? fmtEur(r.sales_outcome_eur) : '—',
    visits_fmt:         r.num_visits > 0 ? r.num_visits : '—',
  }))
}

export default function ExpensesTab() {
  const { data, isLoading, isError } = useExpenses()
  const { activeMonths: filteredMonths } = useFilter()

  if (isLoading) return <div className="loading">⟳ Loading expenses data...</div>
  if (isError) return <div className="error">✕ Failed to load expenses data. Is the backend running?</div>

  const bf  = data.budget_flow || []
  const att = data.activity_type_totals || []
  const ebm = data.expenses_by_month || {}

  // Filter budget_flow rows to selected months
  const bfFiltered = bf.filter(r => filteredMonths.includes(r.month?.toLowerCase().slice(0, 3)))
  const loadedLabels = bfFiltered.map(r => r.month).join(' · ')

  const budgetData = {
    labels: bfFiltered.map(r => r.month),
    datasets: [
      { label: 'Received (FCFA)', data: bfFiltered.map(r => r.received_fcfa), backgroundColor: COLORS.q1A,     borderColor: COLORS.q1,     borderWidth: 1 },
      { label: 'Spent (FCFA)',    data: bfFiltered.map(r => r.spent_fcfa),    backgroundColor: COLORS.dangerA, borderColor: COLORS.danger, borderWidth: 1 },
    ]
  }

  const spendRateData = {
    labels: bfFiltered.map(r => r.month),
    datasets: [{
      label: 'Balance (€)',
      data:  bfFiltered.map(r => r.balance_eur),
      borderColor: bfFiltered.map(r => (r.balance_eur ?? 0) >= 0 ? COLORS.good : COLORS.danger),
      backgroundColor: 'transparent',
      tension: 0.3,
      pointRadius: 6,
    }]
  }

  const actTypeData = {
    labels: att.slice(0, 8).map(r => r.activity),
    datasets: [{
      data:            att.slice(0, 8).map(r => r.amount_fcfa),
      backgroundColor: PALETTE.slice(0, 8),
      borderColor:     'var(--card)',
      borderWidth:     2,
    }]
  }

  // Dynamic list: months with expense data, intersected with active filter
  const monthsWithData = Object.entries(MONTH_CONFIG)
    .filter(([key]) => (ebm[key] || []).length > 0 && filteredMonths.includes(key))

  return (
    <div>
      <SectionLabel tag="EXPENSES" text="BUDGET FLOW" monthColor="exp-s" />
      <div className="full">
        <ChartCard
          title={`Budget Received vs Spent — ${loadedLabels || 'All Months'}`}
          sub="FCFA values"
          height="h250"
        >
          <Bar data={budgetData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag="EXPENSES" text="SPEND RATE & ACTIVITY MIX" monthColor="exp-s" />
      <div className="grid-2">
        <ChartCard title="Closing Balance by Month (€)" sub="Negative = budget overrun" height="h200">
          <Line data={spendRateData} options={baseOptions()} />
        </ChartCard>
        <ChartCard title="Activity Type Distribution (FCFA)" sub="Top 8 activity categories" height="h200">
          <Doughnut data={actTypeData} options={baseOptionsNoScale()} />
        </ChartCard>
      </div>

      {monthsWithData.map(([key, cfg]) => {
        const rows = ebm[key] || []
        const spent = rows.reduce((s, r) => s + (r.amount_fcfa || 0), 0)
        const outcomeTotal = rows.reduce((s, r) => s + (r.sales_outcome_eur || 0), 0)
        const badgeText = `${rows.length} entries · FCFA ${Math.round(spent).toLocaleString()} · €${(spent / FCFA_TO_EUR).toFixed(0)}`
          + (outcomeTotal > 0 ? ` · Outcomes €${outcomeTotal.toFixed(0)}` : '')

          const totalFcfa    = rows.reduce((s, r) => s + (r.amount_fcfa       || 0), 0)
        const totalEur     = rows.reduce((s, r) => s + (r.amount_eur        || 0), 0)
        const totalOutcome = rows.reduce((s, r) => s + (r.sales_outcome_eur || 0), 0)
        const totalVisits  = rows.reduce((s, r) => s + (r.num_visits        || 0), 0)
        const expTotalRow = rows.length > 0 ? {
          sn:                 'TOTAL',
          doctor:             '',
          hospital:           '',
          activity_badge:     '',
          products:           '',
          amount_fcfa_fmt:    fmtFcfa(Math.round(totalFcfa)),
          amount_eur_fmt:     fmtEur(totalEur),
          sales_outcome_cell: '',
          sales_value_fmt:    totalOutcome > 0 ? fmtEur(totalOutcome) : '—',
          visits_fmt:         totalVisits > 0 ? totalVisits : '—',
          responsible:        '',
        } : null

        return (
          <div key={key}>
            <SectionLabel tag="EXPENSES" text={`${cfg.label.toUpperCase()} — ACTIVITY EXPENSES`} monthColor={cfg.sectionCls} />
            <DataTable
              title={`Activity Expenses — ${cfg.label} 2026`}
              badge={{ text: badgeText, variant: cfg.cls }}
              columns={EXP_COLS}
              rows={buildRows(rows)}
              totalRow={expTotalRow}
            />
          </div>
        )
      })}
    </div>
  )
}
