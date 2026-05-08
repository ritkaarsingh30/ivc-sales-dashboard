/**
 * Full 12-month configuration.
 * - cls   : CSS class suffix used for monthColor props (matches index.css)
 * - color : CSS var for direct style usage
 * - prev  : key of the preceding month (null for January)
 */
export const MONTH_CONFIG = {
  jan: { label: 'January',   short: 'Jan', emoji: '🔵', cls: 'j',  color: 'var(--jan)', sectionCls: 'jan-s', prev: null  },
  feb: { label: 'February',  short: 'Feb', emoji: '🟡', cls: 'f',  color: 'var(--feb)', sectionCls: 'feb-s', prev: 'jan' },
  mar: { label: 'March',     short: 'Mar', emoji: '🟢', cls: 'm',  color: 'var(--mar)', sectionCls: 'mar-s', prev: 'feb' },
  apr: { label: 'April',     short: 'Apr', emoji: '🟣', cls: 'ap', color: 'var(--apr)', sectionCls: 'apr-s', prev: 'mar' },
  may: { label: 'May',       short: 'May', emoji: '🟠', cls: 'my', color: 'var(--may)', sectionCls: 'may-s', prev: 'apr' },
  jun: { label: 'June',      short: 'Jun', emoji: '🔴', cls: 'jn', color: 'var(--jun)', sectionCls: 'jun-s', prev: 'may' },
  jul: { label: 'July',      short: 'Jul', emoji: '⚫', cls: 'jl', color: 'var(--jul)', sectionCls: 'jul-s', prev: 'jun' },
  aug: { label: 'August',    short: 'Aug', emoji: '🩵', cls: 'ag', color: 'var(--aug)', sectionCls: 'aug-s', prev: 'jul' },
  sep: { label: 'September', short: 'Sep', emoji: '🩶', cls: 'sp', color: 'var(--sep)', sectionCls: 'sep-s', prev: 'aug' },
  oct: { label: 'October',   short: 'Oct', emoji: '🟤', cls: 'oc', color: 'var(--oct)', sectionCls: 'oct-s', prev: 'sep' },
  nov: { label: 'November',  short: 'Nov', emoji: '🔷', cls: 'nv', color: 'var(--nov)', sectionCls: 'nov-s', prev: 'oct' },
  dec: { label: 'December',  short: 'Dec', emoji: '❄️', cls: 'dc', color: 'var(--dec)', sectionCls: 'dec-s', prev: 'nov' },
}

export const MONTH_KEYS = Object.keys(MONTH_CONFIG)

// Shared delegate table columns — used by all month tabs
export const DELEGATE_COLS = [
  { key: 'name',           label: 'Delegate' },
  { key: 'territory',      label: 'Territory' },
  { key: 'total_calls',    label: 'Total Calls' },
  { key: 'prescriber',     label: 'Prescriber' },
  { key: 'non_prescriber', label: 'Non-Pres.' },
  { key: 'pharmacy',       label: 'Pharmacy' },
  { key: 'drs_converted',  label: 'Drs Conv.' },
  { key: 'days_worked',    label: 'Days' },
  { key: 'orders_eur',     label: 'Orders (€)' },
  { key: 'ctc_eur',        label: 'CTC (€)' },
  { key: 'ctc_ratio',      label: 'CTC Ratio' },
]

// Shared activity-expense table columns — used by all month tabs
// Row builder must supply: activity_badge, sales_outcome_cell, sales_value_fmt, visits_fmt
export const AE_COLS = [
  { key: 'sn',                 label: '#' },
  { key: 'doctor',             label: 'Doctor/Contact' },
  { key: 'hospital',           label: 'Hospital' },
  { key: 'speciality',         label: 'Speciality' },
  { key: 'activity_badge',     label: 'Activity' },
  { key: 'products',           label: 'Products' },
  { key: 'amount_fcfa',        label: 'FCFA' },
  { key: 'amount_eur',         label: '€' },
  { key: 'sales_outcome_cell', label: 'Sales Outcome' },
  { key: 'sales_value_fmt',    label: 'Sales Value €' },
  { key: 'visits_fmt',         label: 'Visits' },
  { key: 'responsible',        label: 'Responsible' },
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
  const sign  = change >= 0 ? '+' : ''
  return `${arrow} ${sign}${change}%`
}

/**
 * Returns 'up', 'dn', or null for KpiCard changeDir prop.
 */
export function changeDir(change) {
  if (change === null || change === undefined) return null
  return change >= 0 ? 'up' : 'dn'
}
