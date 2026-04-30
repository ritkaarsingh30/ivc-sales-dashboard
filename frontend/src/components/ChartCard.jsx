export default function ChartCard({ title, sub, height = 'h250', monthColor = '', children }) {
  return (
    <div className={`card ${monthColor}`}>
      <div className="card-title">{title}</div>
      {sub && <div className="card-sub">{sub}</div>}
      <div className={`chart-${height}`}>
        {children}
      </div>
    </div>
  )
}
