import { useState } from 'react'
import TabBar from './components/TabBar'
import OverviewTab from './tabs/OverviewTab'
import JanTab from './tabs/JanTab'
import FebTab from './tabs/FebTab'
import MarTab from './tabs/MarTab'
import ProductsTab from './tabs/ProductsTab'
import DelegatesTab from './tabs/DelegatesTab'
import ExpensesTab from './tabs/ExpensesTab'

export default function App() {
  const [activeTab, setActiveTab] = useState('ov')

  const panels = {
    ov: <OverviewTab />,
    jan: <JanTab />,
    feb: <FebTab />,
    mar: <MarTab />,
    prod: <ProductsTab />,
    del: <DelegatesTab />,
    exp: <ExpensesTab />,
  }

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
            Ivory Coast &nbsp;·&nbsp; Q1 2026 &nbsp;·&nbsp; Live Data<br />
            Sales · Visits · Expenses · Products · Delegates · Tour Plans
          </div>
        </div>
        <div className="hdr-right">
          <div className="hdr-month-dots">
            <div className="month-dot jan"><i></i> JAN 2026</div>
            <div className="month-dot feb"><i></i> FEB 2026</div>
            <div className="month-dot mar"><i></i> MAR 2026</div>
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
            Q1 Sales Target · Jan–Mar 2026<br />
            <span style={{ color: 'var(--q1)' }}>FastAPI + React · Live from IVC Data</span>
          </div>
        </div>
      </header>

      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />

      {Object.entries(panels).map(([key, content]) => (
        <div key={key} className={`panel${activeTab === key ? ' active' : ''}`}>
          {activeTab === key ? content : null}
        </div>
      ))}
    </div>
  )
}
