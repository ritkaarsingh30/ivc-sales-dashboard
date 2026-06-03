/**
 * Full 12-month configuration.
 * - cls   : CSS class suffix used for monthColor props (matches index.css)
 * - color : CSS var for direct style usage
 * - prev  : key of the preceding month (null for January)
 */
export const MONTH_CONFIG = {
  jan: { label: 'January', short: 'Jan', emoji: '🔵', cls: 'j', color: 'var(--jan)', sectionCls: 'jan-s', prev: null, monthNum: 1 },
  feb: { label: 'February', short: 'Feb', emoji: '🟡', cls: 'f', color: 'var(--feb)', sectionCls: 'feb-s', prev: 'jan', monthNum: 2 },
  mar: { label: 'March', short: 'Mar', emoji: '🟢', cls: 'm', color: 'var(--mar)', sectionCls: 'mar-s', prev: 'feb', monthNum: 3 },
  apr: { label: 'April', short: 'Apr', emoji: '🟣', cls: 'ap', color: 'var(--apr)', sectionCls: 'apr-s', prev: 'mar', monthNum: 4 },
  may: { label: 'May', short: 'May', emoji: '🟠', cls: 'my', color: 'var(--may)', sectionCls: 'may-s', prev: 'apr', monthNum: 5 },
  jun: { label: 'June', short: 'Jun', emoji: '🔴', cls: 'jn', color: 'var(--jun)', sectionCls: 'jun-s', prev: 'may', monthNum: 6 },
  jul: { label: 'July', short: 'Jul', emoji: '⚫', cls: 'jl', color: 'var(--jul)', sectionCls: 'jul-s', prev: 'jun', monthNum: 7 },
  aug: { label: 'August', short: 'Aug', emoji: '🩵', cls: 'ag', color: 'var(--aug)', sectionCls: 'aug-s', prev: 'jul', monthNum: 8 },
  sep: { label: 'September', short: 'Sep', emoji: '🩶', cls: 'sp', color: 'var(--sep)', sectionCls: 'sep-s', prev: 'aug', monthNum: 9 },
  oct: { label: 'October', short: 'Oct', emoji: '🟤', cls: 'oc', color: 'var(--oct)', sectionCls: 'oct-s', prev: 'sep', monthNum: 10 },
  nov: { label: 'November', short: 'Nov', emoji: '🔷', cls: 'nv', color: 'var(--nov)', sectionCls: 'nov-s', prev: 'oct', monthNum: 11 },
  dec: { label: 'December', short: 'Dec', emoji: '❄️', cls: 'dc', color: 'var(--dec)', sectionCls: 'dec-s', prev: 'nov', monthNum: 12 },
}

/**
 * Returns all calendar dates for a given month as YYYY-MM-DD strings.
 * Works for any year; uses JS Date to derive days-in-month correctly.
 */
export function getMonthAllDates(monthNum, year = 2026) {
  const daysInMonth = new Date(year, monthNum, 0).getDate()
  const mm = String(monthNum).padStart(2, '0')
  return Array.from({ length: daysInMonth }, (_, i) => {
    const dd = String(i + 1).padStart(2, '0')
    return `${year}-${mm}-${dd}`
  })
}

export const MONTH_KEYS = Object.keys(MONTH_CONFIG)

// Shared delegate table columns — used by all month tabs
export const DELEGATE_COLS = [
  { key: 'name', label: 'Delegate' },
  { key: 'territory', label: 'Territory' },
  { key: 'total_calls', label: 'Total Calls' },
  { key: 'dr_in_list', label: 'Dr in List' },
  { key: 'listed_covered', label: 'Listed Cov.' },
  { key: 'pct_listed', label: '% List Cov.' },
  { key: 'prescriber', label: 'Prescriber' },
  { key: 'non_prescriber', label: 'Non-Pres.' },
  { key: 'pharmacy', label: 'Pharmacy' },
  { key: 'drs_converted', label: 'Drs Conv.' },
  { key: 'days_worked', label: 'Days' },
  { key: 'avg_per_day', label: 'Avg Calls/Day' },
  { key: 'orders_eur', label: 'Sales (€)' },
  { key: 'ctc_eur', label: 'CTC (€)' },
  { key: 'ctc_ratio', label: 'CTC Ratio' },
]

// Shared activity-expense table columns — used by all month tabs
// Row builder must supply: activity_badge, sales_outcome_cell, sales_value_fmt, visits_fmt
export const AE_COLS = [
  { key: 'sn', label: '#' },
  { key: 'doctor', label: 'Doctor/Contact' },
  { key: 'hospital', label: 'Hospital' },
  { key: 'speciality', label: 'Speciality' },
  { key: 'activity_badge', label: 'Activity' },
  { key: 'products', label: 'Products' },
  { key: 'amount_fcfa', label: 'FCFA' },
  { key: 'amount_eur', label: '€' },
  { key: 'sales_outcome_cell', label: 'Sales Outcome' },
  { key: 'sales_value_fmt', label: 'Sales Value €' },
  { key: 'visits_fmt', label: 'Visits' },
  { key: 'responsible', label: 'Responsible' },
]

/**
 * Calculate a percentage change between current and previous values.
 * Returns null if either value is null/undefined/zero.
 */
export function calcChange(curr, prev) {
  if (curr === null || curr === undefined) return null
  if (!prev || prev === 0) return null
  const pct = ((curr - prev) / Math.abs(prev)) * 100
  return parseFloat(pct.toFixed(1))
}

/**
 * Format a change value as a display string with arrow and sign.
 * e.g. 3.2 → "▲ +3.2%"   -15.0 → "▼ -15.0%"
 * Returns null if change is null.
 */
export function fmtChange(change) {
  if (change === null || change === undefined || isNaN(change)) return null
  const arrow = change >= 0 ? '▲' : '▼'
  const sign = change >= 0 ? '+' : ''
  return `${arrow} ${sign}${change}%`
}

/**
 * Returns 'up', 'dn', or null for KpiCard changeDir prop.
 */
export function changeDir(change) {
  if (change === null || change === undefined) return null
  return change >= 0 ? 'up' : 'dn'
}
