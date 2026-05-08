import { useState } from 'react'
import TabBar from './components/TabBar'
import OverviewTab from './tabs/OverviewTab'
import MonthTab from './tabs/MonthTab'
import ProductsTab from './tabs/ProductsTab'
import DelegatesTab from './tabs/DelegatesTab'
import ExpensesTab from './tabs/ExpensesTab'
import { useAvailableMonths } from './hooks/useDashboard'

export default function App() {
  const [activeTab, setActiveTab] = useState('ov')
  const { data: availableMonths = [] } = useAvailableMonths()

  const staticPanels = {
    ov:   <OverviewTab />,
    prod: <ProductsTab />,
    del:  <DelegatesTab />,
    exp:  <ExpensesTab />,
  }

  const allPanelKeys = [
    'ov',
    ...availableMonths,
    'prod', 'del', 'exp',
  ]

  return (
    <div className="wrapper">
      <header>
        <div className="hdr-left">
          <div className="hdr-badge">
            <span></span>
            IVC · IVORY COAST · CM: JITENDRA MISHRA
          </div>
          <h1>IVC Deep Analysis<br />Dashboard 2026</h1>
          <div className="hdr-sub">
            Ivory Coast &nbsp;·&nbsp; 2026 &nbsp;·&nbsp; Live Data<br />
            Sales · Visits · Expenses · Products · Delegates · Tour Plans
          </div>
        </div>
        <div className="hdr-right">
          <div className="hdr-month-dots">
            {availableMonths.map(m => (
              <div key={m} className={`month-dot ${m}`}>
                <i></i> {m.toUpperCase()} 2026
              </div>
            ))}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
            Sales Target · {availableMonths.map(m => m.charAt(0).toUpperCase() + m.slice(1)).join('–')} 2026<br />
            <span style={{ color: 'var(--q1)' }}>FastAPI + React · Live from IVC Data</span>
          </div>
        </div>
      </header>

      <TabBar activeTab={activeTab} onTabChange={setActiveTab} availableMonths={availableMonths} />

      {allPanelKeys.map(key => (
        <div key={key} className={`panel${activeTab === key ? ' active' : ''}`}>
          {activeTab === key
            ? (staticPanels[key] || <MonthTab month={key} />)
            : null}
        </div>
      ))}
    </div>
  )
}
