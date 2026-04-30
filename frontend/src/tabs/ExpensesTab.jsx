import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { useExpenses } from '../hooks/useDashboard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import { baseOptions, baseOptionsNoScale, COLORS, PALETTE } from '../utils/chartConfig'

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

export default function ExpensesTab() {
  const { data, isLoading, isError } = useExpenses()
  if (isLoading) return <div className="loading">⟳ Loading expenses data...</div>
  if (isError) return <div className="error">✕ Failed to load expenses data. Is the backend running?</div>

  const bf = data.budget_flow || []
  const att = data.activity_type_totals || []
  const all = data.all_expenses || []

  const budgetData = {
    labels: bf.map(r => r.month),
    datasets: [
      { label: 'Received (FCFA)', data: bf.map(r => r.received_fcfa), backgroundColor: COLORS.q1A, borderColor: COLORS.q1, borderWidth: 1 },
      { label: 'Spent (FCFA)',    data: bf.map(r => r.spent_fcfa),    backgroundColor: COLORS.dangerA, borderColor: COLORS.danger, borderWidth: 1 },
    ]
  }

  const spendRateData = {
    labels: bf.map(r => r.month),
    datasets: [
      { label: 'Balance (€)', data: bf.map(r => r.balance_eur), borderColor: bf.map(r => r.balance_eur >= 0 ? COLORS.good : COLORS.danger), backgroundColor: 'transparent', tension: 0.3, pointRadius: 6 },
    ]
  }

  const actTypeData = {
    labels: att.slice(0, 8).map(r => r.activity),
    datasets: [{
      data: att.slice(0, 8).map(r => r.amount_fcfa),
      backgroundColor: PALETTE.slice(0, 8),
      borderColor: 'var(--card)',
      borderWidth: 2,
    }]
  }

  const expCols = [
    { key: 'month', label: 'Month' },
    { key: 'sn', label: '#' },
    { key: 'doctor', label: 'Doctor/Contact' },
    { key: 'hospital', label: 'Hospital' },
    { key: 'activity_badge', label: 'Activity' },
    { key: 'products', label: 'Products' },
    { key: 'amount_fcfa', label: 'FCFA' },
    { key: 'amount_eur', label: '€' },
    { key: 'responsible', label: 'Responsible' },
  ]

  const expRows = all.map(r => ({
    ...r,
    activity_badge: <span className={`act-type-badge ${actBadgeClass(r.activity)}`}>{r.activity}</span>
  }))

  const totalSpent = bf.reduce((s, r) => s + (r.spent_fcfa || 0), 0)
  const totalReceived = bf.reduce((s, r) => s + (r.received_fcfa || 0), 0)

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

      <SectionLabel tag="EXPENSES" text="ALL ACTIVITY EXPENSES — Q1" monthColor="exp-s" />
      <DataTable
        title="Complete Activity Expenses — Q1 2026"
        badge={{ text: `Total FCFA ${totalSpent.toLocaleString()} | €${(totalSpent/655.97).toFixed(0)}`, variant: 'w' }}
        columns={expCols}
        rows={expRows}
      />
    </div>
  )
}
