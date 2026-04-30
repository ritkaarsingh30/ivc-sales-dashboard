export default function SectionLabel({ tag, text, monthColor = 'ov-s' }) {
  return (
    <div className={`sec-label ${monthColor}`}>
      <span className="tag">{tag}</span>
      {text}
    </div>
  )
}
