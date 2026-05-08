import { MONTH_CONFIG } from '../utils/monthConfig'

const STATIC_TABS_AFTER = [
  { id: 'prod', label: '📦 PRODUCTS',  cls: 'prod' },
  { id: 'del',  label: '👥 DELEGATES', cls: 'del'  },
  { id: 'exp',  label: '💰 EXPENSES',  cls: 'exp'  },
]

export default function TabBar({ activeTab, onTabChange, availableMonths = [] }) {
  const monthTabs = availableMonths.map(m => {
    const cfg = MONTH_CONFIG[m] || {}
    return {
      id:    m,
      label: `${cfg.emoji || '📅'} ${(cfg.label || m).toUpperCase()}`,
      cls:   m,
    }
  })

  const tabs = [
    { id: 'ov', label: '📊 OVERVIEW', cls: 'ov' },
    ...monthTabs,
    ...STATIC_TABS_AFTER,
  ]

  return (
    <div className="tab-bar">
      {tabs.map(t => (
        <button
          key={t.id}
          className={`tab ${t.cls}${activeTab === t.id ? ' active' : ''}`}
          onClick={() => onTabChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
