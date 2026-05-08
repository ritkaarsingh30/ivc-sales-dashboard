export default function SalesOutcomeCell({ items }) {
  if (!items || items.length === 0) return <span style={{ color: 'var(--text-muted)' }}>—</span>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      {items.map((item, i) => (
        <span key={i} style={{ fontSize: '11px', whiteSpace: 'nowrap' }}>
          <span style={{ color: 'var(--text)' }}>{item.product_name}</span>
          <span style={{ color: 'var(--text-muted)', margin: '0 3px' }}>×</span>
          <span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{item.qty}</span>
          <span style={{ color: 'var(--text-muted)', marginLeft: '4px', fontSize: '10px' }}>
            {item.eur_value > 0 ? `(€${Number(item.eur_value).toLocaleString(undefined, { maximumFractionDigits: 2 })})` : ''}
          </span>
        </span>
      ))}
    </div>
  )
}
