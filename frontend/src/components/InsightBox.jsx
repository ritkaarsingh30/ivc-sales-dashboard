export default function InsightBox({ type = 'j', icon, title, text, loading = false }) {
  if (loading) {
    return <div className="insight-skeleton" />
  }
  // Map API type names to CSS class suffix
  const typeMap = { danger: 'd', good: 'g', warn: 'w', info: 'j' }
  const cls = typeMap[type] || type
  return (
    <div className={`insight ${cls}`}>
      <div className="insight-icon">{icon}</div>
      <div>
        <div className="insight-lbl">{title}</div>
        <div className="insight-txt">{text}</div>
      </div>
    </div>
  )
}
