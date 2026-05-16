import { useState } from 'react'
import { Bar } from 'react-chartjs-2'
import SectionLabel from './SectionLabel'
import ChartCard from './ChartCard'
import Badge from './Badge'
import { baseOptions } from '../utils/chartConfig'
import { getMonthAllDates } from '../utils/monthConfig'

const DELEGATE_COLORS = [
  { bg: 'rgba(59,130,246,0.55)',  bd: 'rgba(59,130,246,1)'  },
  { bg: 'rgba(245,158,11,0.55)', bd: 'rgba(245,158,11,1)'  },
  { bg: 'rgba(16,185,129,0.55)', bd: 'rgba(16,185,129,1)'  },
  { bg: 'rgba(168,85,247,0.55)', bd: 'rgba(168,85,247,1)'  },
  { bg: 'rgba(236,72,153,0.55)', bd: 'rgba(236,72,153,1)'  },
  { bg: 'rgba(251,146,60,0.55)', bd: 'rgba(251,146,60,1)'  },
]

function buildDateView(visits, allDates) {
  const byDate = {}
  for (const v of visits) {
    if (!v.date) continue
    if (!byDate[v.date]) byDate[v.date] = []
    byDate[v.date].push(v.doctor)
  }
  return allDates.map(date => ({
    date,
    count: (byDate[date] || []).length,
    doctors: byDate[date] || [],
  }))
}

function buildDoctorView(visits) {
  const byDoc = {}
  for (const v of visits) {
    if (!v.doctor) continue
    if (!byDoc[v.doctor]) byDoc[v.doctor] = { speciality: v.speciality, clinic: v.clinic, dates: [] }
    byDoc[v.doctor].dates.push(v.date)
  }
  return Object.entries(byDoc)
    .map(([doctor, info]) => ({
      doctor,
      speciality: info.speciality,
      clinic: info.clinic,
      count: info.dates.length,
      dates: [...new Set(info.dates)].sort(),
    }))
    .sort((a, b) => b.count - a.count)
}

function shortLabel(str, max = 22) {
  return str && str.length > max ? str.slice(0, max - 1) + '…' : str
}

export default function VisitTrackerSection({ visitTracker = {}, cfg }) {
  const [sortMode, setSortMode] = useState('date')
  const delegates = visitTracker.by_delegate || []
  if (!delegates.length) return null

  const allDates = cfg.monthNum ? getMonthAllDates(cfg.monthNum) : []

  return (
    <>
      <SectionLabel tag={cfg.label.toUpperCase()} text="VISIT TRACKER — FIELD VISITS" monthColor={cfg.sectionCls} />

      <div className="vt-sort-bar">
        <span className="vt-sort-label">Sort by</span>
        <button
          className={`vt-sort-btn${sortMode === 'date' ? ' active' : ''}`}
          onClick={() => setSortMode('date')}
        >
          Date
        </button>
        <button
          className={`vt-sort-btn${sortMode === 'doctor' ? ' active' : ''}`}
          onClick={() => setSortMode('doctor')}
        >
          Most Visited Doctor
        </button>
      </div>

      {delegates.map((del, idx) => {
        const color = DELEGATE_COLORS[idx % DELEGATE_COLORS.length]
        const dateView   = buildDateView(del.visits, allDates)
        const doctorView = buildDoctorView(del.visits)

        let chartData, chartOpts

        if (sortMode === 'date') {
          chartData = {
            labels: dateView.map(r => r.date.slice(5)),
            datasets: [{
              label: 'Visits',
              data: dateView.map(r => r.count),
              backgroundColor: color.bg,
              borderColor: color.bd,
              borderWidth: 1,
              borderRadius: 3,
            }],
          }
          chartOpts = baseOptions({
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  title: items => `Date: 2026-${items[0].label}`,
                  afterBody: items => {
                    const row = dateView[items[0].dataIndex]
                    return row.doctors.map(d => `  · ${d}`)
                  },
                },
              },
            },
            scales: {
              y: { ticks: { stepSize: 1, color: '#64748b' }, grid: { color: 'rgba(26,31,53,0.8)' } },
              x: { ticks: { color: '#64748b', maxRotation: 45 }, grid: { color: 'rgba(26,31,53,0.8)' } },
            },
          })
        } else {
          const top = doctorView.slice(0, 12)
          chartData = {
            labels: top.map(r => shortLabel(r.doctor)),
            datasets: [{
              label: 'Visits',
              data: top.map(r => r.count),
              backgroundColor: color.bg,
              borderColor: color.bd,
              borderWidth: 1,
              borderRadius: 3,
            }],
          }
          chartOpts = baseOptions({
            indexAxis: 'y',
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  title: items => doctorView[items[0].dataIndex]?.doctor || '',
                  label: ctx => {
                    const row = doctorView[ctx.dataIndex]
                    return [`${ctx.parsed.x} visit(s)`, `Dates: ${row.dates.map(d => d.slice(5)).join(', ')}`]
                  },
                },
              },
            },
            scales: {
              x: { ticks: { stepSize: 1, color: '#64748b' }, grid: { color: 'rgba(26,31,53,0.8)' } },
              y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(26,31,53,0.8)' } },
            },
          })
        }

        return (
          <div key={del.mr_id} className="vt-delegate-block">
            <div className="tbl-card">
              <div className="tbl-hdr" style={{ borderLeft: `3px solid ${color.bd}` }}>
                <span>{del.mr}</span>
                <span style={{ display: 'flex', gap: 6 }}>
                  <Badge text={`${del.total_visits} visits`} variant="w" />
                  <Badge text={`${del.unique_doctors} doctors`} variant={cfg.cls} />
                </span>
              </div>

              <div className="vt-chart-wrap">
                <ChartCard
                  title={sortMode === 'date' ? 'Visits per Day' : 'Most Visited Doctors'}
                  sub={sortMode === 'date' ? 'Number of doctors seen each field day' : 'Top doctors by visit frequency · hover for dates'}
                  height="h250"
                  monthColor={cfg.cls}
                >
                  <Bar data={chartData} options={chartOpts} />
                </ChartCard>
              </div>

              <div className="tbl-wrap">
                {sortMode === 'date' ? (
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Visits</th>
                        <th>Doctors Visited</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dateView.map(row => (
                        <tr key={row.date} className={row.count === 0 ? 'vt-empty-day' : ''}>
                          <td className="vt-mono">{row.date}</td>
                          <td>{row.count > 0 ? <Badge text={row.count} variant={cfg.cls} /> : ''}</td>
                          <td className="vt-doctors">{row.doctors.join(' · ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>Doctor</th>
                        <th>Speciality</th>
                        <th>Clinic</th>
                        <th>Visits</th>
                        <th>Dates</th>
                      </tr>
                    </thead>
                    <tbody>
                      {doctorView.map(row => (
                        <tr key={row.doctor}>
                          <td>{row.doctor}</td>
                          <td className="vt-dim">{row.speciality || '—'}</td>
                          <td className="vt-dim">{row.clinic || '—'}</td>
                          <td>
                            <Badge
                              text={row.count}
                              variant={row.count >= 3 ? 'g' : row.count === 2 ? cfg.cls : 'w'}
                            />
                          </td>
                          <td className="vt-mono vt-dates">
                            {row.dates.map(d => d.slice(5)).join(', ')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </>
  )
}
