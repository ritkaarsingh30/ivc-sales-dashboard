import Badge from './Badge'

function ctcBadgeVariant(ratio) {
  if (ratio === null || ratio === undefined) return 'n'
  if (ratio > 100) return 'd'
  if (ratio > 50) return 'w'
  return 'g'
}

function drsBadgeVariant(drs, monthColor) {
  if (drs === null || drs === undefined) return 'n'
  if (drs > 5) return 'g'
  if (drs > 0) return monthColor
  return 'd'
}

export default function DataTable({ title, badge, borderColor, columns = [], rows = [], totalRow = null }) {
  return (
    <div className="tbl-card">
      <div className="tbl-hdr" style={borderColor ? { borderLeft: `3px solid ${borderColor}` } : {}}>
        <span>{title}</span>
        {badge && <Badge text={badge.text} variant={badge.variant} />}
      </div>
      <div className="tbl-wrap">
        <table>
          <thead>
            <tr>
              {columns.map(col => <th key={col.key}>{col.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map(col => {
                  const val = row[col.key]
                  if (col.key === 'ctc_ratio' && val !== null && val !== undefined) {
                    return <td key={col.key}><Badge text={`${val}%`} variant={ctcBadgeVariant(val)} /></td>
                  }
                  if (col.key === 'drs_converted') {
                    return <td key={col.key}><Badge text={val ?? '—'} variant={drsBadgeVariant(val, 'j')} /></td>
                  }
                  if (col.key === 'pct_listed' && val !== null && val !== undefined) {
                    return <td key={col.key}>{val}%</td>
                  }
                  return <td key={col.key}>{val !== null && val !== undefined ? val : '—'}</td>
                })}
              </tr>
            ))}
            {totalRow && (
              <tr className="total-row">
                {columns.map(col => {
                  const val = totalRow[col.key]
                  if (col.key === 'ctc_ratio' && val !== null && val !== undefined) {
                    return <td key={col.key}><Badge text={`${val}%`} variant={ctcBadgeVariant(val)} /></td>
                  }
                  return <td key={col.key}><b>{val !== null && val !== undefined ? val : '—'}</b></td>
                })}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
