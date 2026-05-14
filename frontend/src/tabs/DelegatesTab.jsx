import { Bar, Line } from 'react-chartjs-2'
import { useDelegates } from '../hooks/useDashboard'
import KpiCard from '../components/KpiCard'
import SectionLabel from '../components/SectionLabel'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import { baseOptions, COLORS, monthColor } from '../utils/chartConfig'
import { MONTH_CONFIG, MONTH_KEYS } from '../utils/monthConfig'

/* ── helpers ─────────────────────────────────────────────── */
const fmtEur = n => (n != null && n !== 0) ? `€${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—'
const fmtPct = n => n != null ? `${n}%` : '—'

function ctcVariant(r) {
  if (r == null) return 'n'
  if (r <= 25)  return 'g'
  if (r <= 60)  return 'w'
  return 'd'
}
function ctcColor(r) {
  if (r == null) return COLORS.neutral
  if (r <= 25)  return COLORS.good
  if (r <= 60)  return COLORS.warn
  return COLORS.danger
}

const DEL_COLORS = [
  { solid: 'rgba(59,130,246,1)',  soft: 'rgba(59,130,246,0.55)'  },
  { solid: 'rgba(245,158,11,1)', soft: 'rgba(245,158,11,0.55)' },
  { solid: 'rgba(16,185,129,1)', soft: 'rgba(16,185,129,0.55)' },
  { solid: 'rgba(168,85,247,1)', soft: 'rgba(168,85,247,0.55)' },
  { solid: 'rgba(236,72,153,1)', soft: 'rgba(236,72,153,0.55)' },
  { solid: 'rgba(251,146,60,1)', soft: 'rgba(251,146,60,0.55)' },
]

/* ── Scorecard card ──────────────────────────────────────── */
function DelegateScorecard({ d, color }) {
  const q = d.q1
  const utilPct = q.days_utilization ?? 0
  const ctcRatio = q.ctc_ratio
  const variant = ctcVariant(ctcRatio)

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: '10px', padding: '18px 20px',
      borderTop: `3px solid ${color.solid}`,
      display: 'flex', flexDirection: 'column', gap: '12px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '15px', fontWeight: 700, color: color.solid, letterSpacing: '0.5px' }}>
            {d.display_name}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
            {d.territory}
          </div>
        </div>
        <Badge text={`CTC ${fmtPct(ctcRatio)}`} variant={variant} />
      </div>

      {/* Activity row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '8px' }}>
        {[
          ['Q1 Calls',   q.calls],
          ['Drs Conv.',  q.drs_converted],
          ['Conv. Rate', fmtPct(q.conversion_pct)],
        ].map(([lbl, val]) => (
          <div key={lbl} style={{ background: 'var(--bg)', borderRadius: '6px', padding: '8px 10px' }}>
            <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: '4px' }}>{lbl}</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '16px', fontWeight: 600, color: 'var(--text)' }}>{val ?? '—'}</div>
          </div>
        ))}
      </div>

      {/* Financial row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: '8px' }}>
        {[
          ['Q1 Orders', fmtEur(q.orders_eur), q.orders_eur > 0 ? COLORS.good : 'var(--text)'],
          ['Q1 CTC',    fmtEur(q.ctc_eur),    ctcColor(ctcRatio)],
        ].map(([lbl, val, clr]) => (
          <div key={lbl} style={{ background: 'var(--bg)', borderRadius: '6px', padding: '8px 10px' }}>
            <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: '4px' }}>{lbl}</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '15px', fontWeight: 600, color: clr }}>{val}</div>
          </div>
        ))}
      </div>

      {/* Days & Tour coverage row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: '8px' }}>
        {[
          ['Days Worked', `${q.days_worked} / ${q.days_target}`],
          ['Tour Coverage', fmtPct(q.tour_coverage_pct)],
        ].map(([lbl, val]) => (
          <div key={lbl} style={{ background: 'var(--bg)', borderRadius: '6px', padding: '8px 10px' }}>
            <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: '4px' }}>{lbl}</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>{val ?? '—'}</div>
          </div>
        ))}
      </div>

      {/* Days utilization bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: 'var(--text-muted)', marginBottom: '4px' }}>
          <span>DAYS UTILIZATION</span>
          <span style={{ fontFamily: 'var(--mono)', color: utilPct >= 90 ? COLORS.good : utilPct >= 70 ? COLORS.warn : COLORS.danger }}>
            {fmtPct(utilPct)}
          </span>
        </div>
        <div style={{ height: '5px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: '3px',
            width: `${Math.min(utilPct, 100)}%`,
            background: utilPct >= 90 ? COLORS.good : utilPct >= 70 ? COLORS.warn : COLORS.danger,
            transition: 'width 0.4s ease',
          }} />
        </div>
      </div>
    </div>
  )
}

/* ── Main tab ────────────────────────────────────────────── */
export default function DelegatesTab() {
  const { data, isLoading, isError } = useDelegates()
  if (isLoading) return <div className="loading">⟳ Loading delegates data...</div>
  if (isError)   return <div className="error">✕ Failed to load delegates data. Is the backend running?</div>

  const dls  = data.delegates    || []
  const summ = data.q1_summary   || {}
  const ctcR = data.ctc_ratios   || []

  // Derive loaded months in calendar order from the first delegate's months object
  const months = MONTH_KEYS.filter(k => dls[0]?.months && k in dls[0].months)
  const periodLabel = months.length > 0
    ? `${MONTH_CONFIG[months[0]].short} – ${MONTH_CONFIG[months[months.length - 1]].short} 2026`
    : '2026'
  const monthDotLabel = months.map(k => MONTH_CONFIG[k].short).join(' · ')

  const names = dls.map(d => d.short_name || d.display_name)

  /* ── Calls trend: one bar dataset per month ── */
  const callsTrendData = {
    labels: names,
    datasets: months.map(mk => {
      const mc = monthColor(mk)
      return {
        label: MONTH_CONFIG[mk].label,
        data: dls.map(d => d.months[mk]?.calls || 0),
        backgroundColor: mc.alpha,
        borderColor: mc.solid,
        borderWidth: 1,
        borderRadius: 3,
      }
    }),
  }

  /* ── Drs Converted: line per delegate across all months ── */
  const drsData = {
    labels: months.map(k => MONTH_CONFIG[k].label),
    datasets: dls.map((d, i) => ({
      label: d.display_name,
      data: months.map(k => d.months[k]?.drs_converted || 0),
      borderColor: DEL_COLORS[i % DEL_COLORS.length].solid,
      backgroundColor: 'transparent',
      tension: 0.35,
      pointRadius: 5,
      pointHoverRadius: 7,
    })),
  }

  /* ── Orders vs CTC (grouped horizontal bar) — the KEY chart ── */
  const roiData = {
    labels: names,
    datasets: [
      {
        label: 'Q1 Orders (€)',
        data: dls.map(d => d.q1.orders_eur || 0),
        backgroundColor: 'rgba(34,197,94,0.6)',
        borderColor:     'rgba(34,197,94,1)',
        borderWidth: 1, borderRadius: 3,
      },
      {
        label: 'Q1 CTC (€)',
        data: dls.map(d => d.q1.ctc_eur || 0),
        backgroundColor: 'rgba(239,68,68,0.55)',
        borderColor:     'rgba(239,68,68,0.9)',
        borderWidth: 1, borderRadius: 3,
      },
    ],
  }

  /* ── CTC Ratio: one dataset per loaded month ── */
  const ctcMonths = ctcR.length > 0
    ? MONTH_KEYS.filter(k => k in ctcR[0] && ctcR[0][k] !== undefined)
    : months
  const ctcChartData = {
    labels: ctcR.map(r => r.mr),
    datasets: ctcMonths.map(mk => ({
      label: `${MONTH_CONFIG[mk].short} CTC %`,
      data: ctcR.map(r => r[mk] ?? null),
      backgroundColor: ctcR.map(r => ctcColor(r[mk]) + '99'),
      borderColor: ctcR.map(r => ctcColor(r[mk])),
      borderWidth: 1.5,
      borderRadius: 3,
    })),
  }

  const ctcChartOptions = {
    ...baseOptions(),
    plugins: {
      ...baseOptions().plugins,
      annotation: {
        annotations: {
          target: {
            type: 'line', yMin: 25, yMax: 25,
            borderColor: COLORS.danger, borderWidth: 2, borderDash: [6,4],
            label: { content: '25% Target', display: true, color: COLORS.danger, font: { size: 10 } },
          },
        },
      },
    },
  }

  /* ── Days Worked vs Target ── */
  const daysData = {
    labels: names,
    datasets: [
      { label: 'Q1 Days Target', data: dls.map(d => d.q1.days_target), backgroundColor: 'rgba(148,163,184,0.25)', borderColor: '#94a3b8', borderWidth: 1, borderRadius: 3 },
      { label: 'Q1 Days Worked', data: dls.map(d => d.q1.days_worked), backgroundColor: COLORS.q1A,               borderColor: COLORS.q1,  borderWidth: 1, borderRadius: 3 },
    ],
  }

  /* ── Master Q1 table ── */
  const tblCols = [
    { key: 'name',        label: 'Delegate' },
    { key: 'territory',   label: 'Territory' },
    { key: 'calls',       label: 'Q1 Calls' },
    { key: 'prescriber',  label: 'Prescriber' },
    { key: 'pharmacy',    label: 'Pharmacy' },
    { key: 'drs',         label: 'Drs Conv.' },
    { key: 'conv_pct',    label: 'Conv. %' },
    { key: 'orders',      label: 'Orders (€)' },
    { key: 'ctc',         label: 'CTC (€)' },
    { key: 'ctc_ratio',   label: 'CTC Ratio' },
    { key: 'days',        label: 'Days W/T' },
    { key: 'tour_cov',    label: 'Tour Cov.' },
  ]

  const tblRows = dls.map(d => {
    const q = d.q1
    return {
      name:       d.display_name,
      territory:  d.territory,
      calls:      q.calls,
      prescriber: q.prescriber,
      pharmacy:   q.pharmacy,
      drs:        q.drs_converted,
      conv_pct:   fmtPct(q.conversion_pct),
      orders:     fmtEur(q.orders_eur),
      ctc:        fmtEur(q.ctc_eur),
      ctc_ratio:  <Badge text={fmtPct(q.ctc_ratio)} variant={ctcVariant(q.ctc_ratio)} />,
      days:       `${q.days_worked} / ${q.days_target}`,
      tour_cov:   fmtPct(q.tour_coverage_pct),
    }
  })

  const overallUtil = summ.total_days_target > 0
    ? `${Math.round(summ.total_days_worked / summ.total_days_target * 100)}% utilization`
    : ''

  return (
    <div>
      {/* ── Summary KPIs ── */}
      <SectionLabel tag="DELEGATES" text="FIELD FORCE SUMMARY" monthColor="del-s" />
      <div className="kpi-grid">
        <KpiCard label={`Total Calls — ${periodLabel}`}    value={(summ.total_calls ?? 0).toLocaleString()}       monthColor="q" />
        <KpiCard label="Prescriber Calls"                  value={(summ.total_prescriber ?? 0).toLocaleString()}   monthColor="q" />
        <KpiCard label="Pharmacy Calls"                    value={(summ.total_pharmacy ?? 0).toLocaleString()}     monthColor="q" />
        <KpiCard label={`Drs Converted — ${periodLabel}`} value={summ.total_drs ?? 0}                             monthColor={summ.total_drs > 0 ? 'g' : 'd'} />
        <KpiCard label={`Total Orders — ${periodLabel}`}  value={fmtEur(summ.total_orders_eur)}                   monthColor="g" />
        <KpiCard label={`Total CTC — ${periodLabel}`}     value={fmtEur(summ.total_ctc_eur)}                      monthColor="d" />
        <KpiCard
          label="Overall CTC Ratio"
          value={fmtPct(summ.overall_ctc_ratio)}
          sub="Target ≤ 25% — all far above"
          monthColor={ctcVariant(summ.overall_ctc_ratio)}
        />
        <KpiCard
          label="Days Utilization"
          value={overallUtil}
          sub={`${summ.total_days_worked ?? 0} / ${summ.total_days_target ?? 0} days`}
          monthColor="q"
        />
      </div>

      {/* ── Per-Delegate Scorecards ── */}
      <SectionLabel tag="DELEGATES" text={`DELEGATE SCORECARDS — ${periodLabel}`} monthColor="del-s" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        {dls.map((d, i) => (
          <DelegateScorecard key={d.id} d={d} color={DEL_COLORS[i % DEL_COLORS.length]} />
        ))}
      </div>

      {/* ── Calls + Drs Converted ── */}
      <SectionLabel tag="DELEGATES" text="ACTIVITY ANALYSIS" monthColor="del-s" />
      <div className="grid-2">
        <ChartCard title={`Total Calls by Delegate — ${monthDotLabel}`} sub="Call volume trend across all loaded months" height="h300">
          <Bar data={callsTrendData} options={baseOptions()} />
        </ChartCard>
        <ChartCard title="Doctors Converted — Monthly Trend" sub={`Conversion performance per delegate (${periodLabel})`} height="h300">
          <Line data={drsData} options={baseOptions()} />
        </ChartCard>
      </div>

      {/* ── ROI Analysis ── */}
      <SectionLabel tag="DELEGATES" text="CTC vs ORDERS — ROI ANALYSIS" monthColor="del-s" />
      <div className="grid-2">
        <ChartCard
          title={`Orders vs CTC Investment per Delegate — ${periodLabel}`}
          sub="Green = orders generated · Red = CTC cost · Bar above red = profitable"
          height="h300"
        >
          <Bar data={roiData} options={baseOptions()} />
        </ChartCard>
        <ChartCard
          title={`⚠️ CTC Ratio by Month — ${monthDotLabel}`}
          sub="CTC ÷ Orders × 100 — target ≤ 25% · months with no order data show null"
          height="h300"
        >
          <Bar data={ctcChartData} options={ctcChartOptions} />
        </ChartCard>
      </div>

      {/* ── Days Utilization ── */}
      <SectionLabel tag="DELEGATES" text="DAYS WORKED vs TARGET" monthColor="del-s" />
      <div className="full">
        <ChartCard title={`Days Worked vs Target per Delegate — ${periodLabel}`} sub="Purple = days worked · Grey = target" height="h250">
          <Bar data={daysData} options={baseOptions()} />
        </ChartCard>
      </div>

      {/* ── Q1 Master Table ── */}
      <SectionLabel tag="DELEGATES" text="YTD MASTER SCORECARD" monthColor="del-s" />
      <DataTable
        title={`Delegate Performance — ${periodLabel}`}
        badge={{ text: `${dls.length} delegates · CTC target ≤ 25%`, variant: 'q' }}
        columns={tblCols}
        rows={tblRows}
      />
    </div>
  )
}
