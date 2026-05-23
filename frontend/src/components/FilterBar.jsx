import { useState, useRef, useEffect } from 'react'
import { useFilter } from '../context/FilterContext'
import { MONTH_CONFIG } from '../utils/monthConfig'

const PRESETS = [
  { label: 'Q1', months: ['jan', 'feb', 'mar'] },
  { label: 'Q2', months: ['apr', 'may', 'jun'] },
  { label: 'Q3', months: ['jul', 'aug', 'sep'] },
  { label: 'Q4', months: ['oct', 'nov', 'dec'] },
]

function IconFilter() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="8" y1="12" x2="16" y2="12" />
      <line x1="11" y1="18" x2="13" y2="18" />
    </svg>
  )
}

function IconChevron({ open }) {
  return (
    <svg
      width="10" height="10" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
      style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

export default function FilterBar() {
  const { availableMonths, activeMonths, isFiltered, isMonthSelected, toggleMonth, setPreset, clearFilter } = useFilter()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function onDown(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  if (!availableMonths.length) return null

  const visiblePresets = PRESETS.filter(p => p.months.some(m => availableMonths.includes(m)))

  const isPresetActive = (preset) => {
    const available = preset.months.filter(m => availableMonths.includes(m))
    return isFiltered && activeMonths.length === available.length && available.every(m => isMonthSelected(m))
  }

  const isAllActive = !isFiltered

  return (
    <div className="filter-bar" ref={ref}>
      <div className="filter-bar-inner">

        {/* Trigger button */}
        <button
          className={`fb-trigger${open ? ' open' : ''}${isFiltered ? ' active' : ''}`}
          onClick={() => setOpen(o => !o)}
        >
          <IconFilter />
          <span>Filters</span>
          {isFiltered && (
            <span className="fb-count">{activeMonths.length}</span>
          )}
          <IconChevron open={open} />
        </button>

        {/* Active filter chips (or "all" hint) */}
        <div className="fb-chips">
          {isFiltered
            ? activeMonths.map(mk => {
                const cfg = MONTH_CONFIG[mk] || {}
                return (
                  <span key={mk} className={`fb-chip ${cfg.cls}`}>
                    {cfg.short}
                    <button className="fb-chip-x" onClick={() => toggleMonth(mk)} aria-label={`Remove ${cfg.label}`}>
                      ✕
                    </button>
                  </span>
                )
              })
            : (
              <span className="fb-all-hint">
                Showing all {availableMonths.length} month{availableMonths.length !== 1 ? 's' : ''}&nbsp;·&nbsp;
                {availableMonths.map(m => MONTH_CONFIG[m]?.short || m).join(' · ')}
              </span>
            )
          }
        </div>

        {/* Clear button */}
        {isFiltered && (
          <button className="fb-clear" onClick={clearFilter}>
            Clear all
          </button>
        )}
      </div>

      {/* ── Dropdown panel ── */}
      {open && (
        <div className="fb-dropdown">

          {/* Month grid */}
          <div className="fbd-section">
            <div className="fbd-label">SELECT MONTHS</div>
            <div className="fbd-month-grid">
              {availableMonths.map(mk => {
                const cfg = MONTH_CONFIG[mk] || {}
                const sel = isMonthSelected(mk)
                return (
                  <button
                    key={mk}
                    className={`fbd-month${sel ? ` sel ${cfg.cls}` : ''}`}
                    onClick={() => toggleMonth(mk)}
                  >
                    <span className="fbd-month-short">{cfg.short}</span>
                    <span className="fbd-month-label">{cfg.label}</span>
                    {sel && <span className="fbd-tick">✓</span>}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Presets */}
          <div className="fbd-section">
            <div className="fbd-label">QUICK PRESETS</div>
            <div className="fbd-presets">
              <button
                className={`fbd-preset${isAllActive ? ' sel' : ''}`}
                onClick={() => { clearFilter(); setOpen(false) }}
              >
                All Months
              </button>
              {visiblePresets.map(p => {
                const available = p.months.filter(m => availableMonths.includes(m))
                const active = isPresetActive(p)
                return (
                  <button
                    key={p.label}
                    className={`fbd-preset${active ? ' sel' : ''}`}
                    onClick={() => { setPreset(available); setOpen(false) }}
                  >
                    {p.label}
                    <span className="fbd-preset-sub">{available.map(m => MONTH_CONFIG[m]?.short).join('·')}</span>
                  </button>
                )
              })}
              {availableMonths.length > 1 && (
                <button
                  className={`fbd-preset${isFiltered && activeMonths.length === 1 && isMonthSelected(availableMonths[availableMonths.length - 1]) ? ' sel' : ''}`}
                  onClick={() => { setPreset([availableMonths[availableMonths.length - 1]]); setOpen(false) }}
                >
                  Latest
                  <span className="fbd-preset-sub">{MONTH_CONFIG[availableMonths[availableMonths.length - 1]]?.short}</span>
                </button>
              )}
            </div>
          </div>

          <div className="fbd-footer">
            <span className="fbd-footer-info">
              {activeMonths.length} of {availableMonths.length} months selected
            </span>
            <button className="fbd-done" onClick={() => setOpen(false)}>Done</button>
          </div>
        </div>
      )}
    </div>
  )
}
