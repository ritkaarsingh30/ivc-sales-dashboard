export default function Badge({ text, variant = 'n' }) {
  return <span className={`badge ${variant}`}>{text}</span>
}
