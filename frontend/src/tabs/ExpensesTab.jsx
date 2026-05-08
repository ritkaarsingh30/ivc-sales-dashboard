import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { useExpenses } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import { baseOptions, baseOptionsNoScale, COLORS, PALETTE } from '../utils/chartConfig'

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

function SalesOutcomeCell({ items }) {
  if (!items || items.length === 0) return <span style={{ color: 'var(--text-muted)' }}>—</span>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      {items.map((item, i) => (
        <span key={i} style={{ fontSize: '11px', whiteSpace: 'nowrap' }}>
          <span style={{ color: 'var(--text)' }}>{item.product_name}</span>
          <span style={{ color: 'var(--text-muted)', margin: '0 3px' }}>×</span>
          <span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{item.qty}</span>
          <span style={{ color: 'var(--text-muted)', marginLeft: '4px', fontSize: '10px' }}>
            ({fmtEur(item.eur_value)})
          </span>
        </span>
      ))}
    </div>
  )
}

const EXP_COLS = [
  { key: 'sn',             label: '#' },
  { key: 'doctor',         label: 'Doctor / Contact' },
  { key: 'hospital',       label: 'Hospital' },
  { key: 'activity_badge', label: 'Activity' },
  { key: 'products',       label: 'Products' },
  { key: 'amount_fcfa_fmt',label: 'FCFA' },
  { key: 'amount_eur_fmt', label: 'Amount €' },
  { key: 'sales_outcome_cell', label: 'Sales Outcome' },
  { key: 'sales_value_fmt',label: 'Sales Value €' },
  { key: 'visits_fmt',     label: 'Visits' },
  { key: 'responsible',    label: 'Responsible' },
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

const MONTH_CFG = [
  { key: 'jan', label: 'January',  sectionColor: 'jan-s', badgeVariant: 'j' },
  { key: 'feb', label: 'February', sectionColor: 'feb-s', badgeVariant: 'f' },
  { key: 'mar', label: 'March',    sectionColor: 'mar-s', badgeVariant: 'm' },
]

export default function ExpensesTab() {
  const { data, isLoading, isError } = useExpenses()
  if (isLoading) return <div className="loading">⟳ Loading expenses data...</div>
  if (isError) return <div className="error">✕ Failed to load expenses data. Is the backend running?</div>

  const bf  = data.budget_flow || []
  const att = data.activity_type_totals || []
  const ebm = data.expenses_by_month || {}

  const budgetData = {
    labels: bf.map(r => r.month),
    datasets: [
      { label: 'Received (FCFA)', data: bf.map(r => r.received_fcfa), backgroundColor: COLORS.q1A,     borderColor: COLORS.q1,     borderWidth: 1 },
      { label: 'Spent (FCFA)',    data: bf.map(r => r.spent_fcfa),    backgroundColor: COLORS.dangerA, borderColor: COLORS.danger, borderWidth: 1 },
    ]
  }

  const spendRateData = {
    labels: bf.map(r => r.month),
    datasets: [{
      label: 'Balance (€)',
      data:  bf.map(r => r.balance_eur),
      borderColor: bf.map(r => (r.balance_eur ?? 0) >= 0 ? COLORS.good : COLORS.danger),
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

  const totalSpent = bf.reduce((s, r) => s + (r.spent_fcfa || 0), 0)

  return (
    <div>
      <SectionLabel tag="EXPENSES" text="Q1 BUDGET FLOW" monthColor="exp-s" />
      <div className="full">
        <ChartCard title="Budget Received vs Spent — January · February · March" sub="FCFA values — larger deficit visible in March" height="h250">
          <Bar data={budgetData} options={baseOptions()} />
        </ChartCard>
      </div>

      <SectionLabel tag="EXPENSES" text="SPEND RATE & ACTIVITY MIX" monthColor="exp-s" />
      <div className="grid-2">
        <ChartCard title="Closing Balance by Month (€)" sub="Negative = budget overrun" height="h200">
          <Line data={spendRateData} options={baseOptions()} />
        </ChartCard>
        <ChartCard title="Activity Type Distribution (FCFA)" sub="Top 8 activity categories Q1" height="h200">
          <Doughnut data={actTypeData} options={baseOptionsNoScale()} />
        </ChartCard>
      </div>

      {MONTH_CFG.map(({ key, label, sectionColor, badgeVariant }) => {
        const rows = ebm[key] || []
        if (rows.length === 0) return null
        const spent = rows.reduce((s, r) => s + (r.amount_fcfa || 0), 0)
        const outcomeTotal = rows.reduce((s, r) => s + (r.sales_outcome_eur || 0), 0)
        const badgeText = `${rows.length} entries · FCFA ${Math.round(spent).toLocaleString()} · €${(spent / FCFA_TO_EUR).toFixed(0)}`
          + (outcomeTotal > 0 ? ` · Outcomes €${outcomeTotal.toFixed(0)}` : '')

        return (
          <div key={key}>
            <SectionLabel tag="EXPENSES" text={`${label.toUpperCase()} — ACTIVITY EXPENSES`} monthColor={sectionColor} />
            <DataTable
              title={`Activity Expenses — ${label} 2026`}
              badge={{ text: badgeText, variant: badgeVariant }}
              columns={EXP_COLS}
              rows={buildRows(rows)}
            />
          </div>
        )
      })}
    </div>
  )
}
