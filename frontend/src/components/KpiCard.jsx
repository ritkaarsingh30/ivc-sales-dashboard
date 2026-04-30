export default function KpiCard({ label, value, sub, change, changeDir = 'na', monthColor = 'q' }) {
  return (
    <div className={`kpi ${monthColor}`}>
      <div className="kpi-lbl">{label}</div>
      <div className="kpi-val">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
      {change && <div className={`kpi-chg ${changeDir}`}>{change}</div>}
    </div>
  )
}
