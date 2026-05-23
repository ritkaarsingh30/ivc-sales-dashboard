const TERMS = [
  {
    term: 'Prescriber',
    definition: 'A healthcare professional who prescribes our medicines.',
    category: 'Segmentation',
  },
  {
    term: 'Non-Prescriber',
    definition: 'A doctor on our list who has not prescribed our medicines.',
    category: 'Segmentation',
  },
]

export default function NomenclatureTab() {
  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '32px 16px' }}>
      <div style={{ marginBottom: 32 }}>
        <div style={{
          fontFamily: 'var(--mono)',
          fontSize: 11,
          color: 'var(--q1)',
          textTransform: 'uppercase',
          letterSpacing: 2,
          marginBottom: 8,
        }}>
          Team Reference
        </div>
        <h2 style={{
          fontFamily: 'var(--head)',
          fontSize: 26,
          fontWeight: 700,
          color: 'var(--text)',
          marginBottom: 6,
        }}>
          Nomenclature
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
          Standard definitions used across all IVC sales reporting and dashboard metrics.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {TERMS.map(({ term, definition, category }) => (
          <div key={term} style={{
            background: 'var(--card)',
            border: '1px solid var(--border2)',
            borderRadius: 10,
            padding: '20px 24px',
            display: 'grid',
            gridTemplateColumns: '220px 1fr',
            gap: '12px 24px',
            alignItems: 'start',
          }}>
            <div>
              <div style={{
                fontFamily: 'var(--mono)',
                fontSize: 10,
                color: 'var(--q1)',
                textTransform: 'uppercase',
                letterSpacing: 1.5,
                marginBottom: 4,
              }}>
                {category}
              </div>
              <div style={{
                fontFamily: 'var(--head)',
                fontSize: 17,
                fontWeight: 700,
                color: 'var(--text)',
              }}>
                {term}
              </div>
            </div>
            <div style={{
              fontSize: 14,
              color: 'var(--text-muted)',
              lineHeight: 1.7,
              paddingTop: 18,
            }}>
              {definition}
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 40,
        padding: '14px 20px',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        fontFamily: 'var(--mono)',
        fontSize: 11,
        color: 'var(--text-dim)',
      }}>
        {TERMS.length} term{TERMS.length !== 1 ? 's' : ''} defined · IVC Sales Dashboard 2026
      </div>
    </div>
  )
}
