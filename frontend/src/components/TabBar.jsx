const TABS = [
  { id: 'ov',   label: '📊 Q1 OVERVIEW',  cls: 'ov'   },
  { id: 'jan',  label: '🔵 JANUARY',       cls: 'jan'  },
  { id: 'feb',  label: '🟡 FEBRUARY',      cls: 'feb'  },
  { id: 'mar',  label: '🟢 MARCH',         cls: 'mar'  },
  { id: 'prod', label: '📦 PRODUCTS',      cls: 'prod' },
  { id: 'del',  label: '👥 DELEGATES',     cls: 'del'  },
  { id: 'exp',  label: '💰 EXPENSES',      cls: 'exp'  },
]

export default function TabBar({ activeTab, onTabChange }) {
  return (
    <div className="tab-bar">
      {TABS.map(t => (
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
