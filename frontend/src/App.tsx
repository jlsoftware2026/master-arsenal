import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileText,
  LayoutDashboard,
  LineChart,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  WalletCards,
  Waves,
  Zap,
} from "lucide-react";

type Metric = {
  label: string;
  value: string;
  detail: string;
  tone?: "positive" | "warning" | "neutral";
  icon: typeof Activity;
};

const metrics: Metric[] = [
  { label: "Market status", value: "Monitoring", detail: "Binance Spot · Public data", tone: "positive", icon: Waves },
  { label: "Active jobs", value: "02", detail: "1 running · 1 queued", tone: "neutral", icon: Zap },
  { label: "Pending approvals", value: "01", detail: "Requires your attention", tone: "warning", icon: ShieldCheck },
  { label: "Reports generated", value: "18", detail: "This workspace · Demo data", tone: "neutral", icon: FileText },
  { label: "Available skills", value: "04", detail: "Trading Intelligence", tone: "positive", icon: Sparkles },
];

const activities = [
  { title: "Market closing report", subtitle: "Binance Spot · BTCUSDT / ETHUSDT", time: "Today, 08:15", status: "Completed", tone: "success", icon: FileText },
  { title: "Intraday market snapshot", subtitle: "Binance Spot · 1h interval", time: "Today, 07:42", status: "Awaiting approval", tone: "warning", icon: Activity },
  { title: "Opening market analysis", subtitle: "Binance Spot · Previous session", time: "Yesterday, 17:05", status: "Completed", tone: "success", icon: LineChart },
];

const navigation = [
  { label: "Workspace", items: [{ label: "Dashboard", icon: LayoutDashboard, active: true }, { label: "Market intelligence", icon: LineChart }, { label: "Skills management", icon: Sparkles }] },
  { label: "Execution", items: [{ label: "Job center", icon: BriefcaseBusiness }, { label: "Approvals", icon: ShieldCheck }, { label: "Execution history", icon: Clock3 }] },
  { label: "Library", items: [{ label: "Reports", icon: BookOpen }] },
];

function StatusPill({ children, tone }: { children: React.ReactNode; tone: string }) {
  return <span className={`status-pill status-${tone}`}><span className="status-dot" />{children}</span>;
}

function MetricCard({ metric }: { metric: Metric }) {
  const Icon = metric.icon;
  return (
    <article className="metric-card">
      <div className="metric-topline">
        <span>{metric.label}</span>
        <span className={`metric-icon metric-icon-${metric.tone ?? "neutral"}`}><Icon size={16} /></span>
      </div>
      <strong className="metric-value">{metric.value}</strong>
      <span className="metric-detail">{metric.detail}</span>
    </article>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="MASTER ARSENAL home">
          <span className="brand-mark">M</span>
          <span className="brand-name">MASTER <b>ARSENAL</b><small>TRADING INTELLIGENCE</small></span>
        </a>

        <div className="workspace-switcher">
          <span className="workspace-avatar">T</span>
          <span><strong>Trading workspace</strong><small>Personal environment</small></span>
          <ChevronDown size={15} />
        </div>

        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map((group) => (
            <div className="nav-group" key={group.label}>
              <p className="nav-label">{group.label}</p>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <a className={`nav-link ${item.active ? "active" : ""}`} href="#" key={item.label}>
                    <Icon size={17} strokeWidth={1.8} />
                    <span>{item.label}</span>
                    {item.label === "Approvals" && <i className="nav-count">1</i>}
                  </a>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <a className="nav-link" href="#"><CircleHelp size={17} /><span>Help & support</span></a>
          <a className="nav-link" href="#"><Settings2 size={17} /><span>Settings</span></a>
          <div className="engine-status"><span className="engine-pulse" /><span><b>Local engine</b><small>Interface preview · Not connected</small></span></div>
          <div className="profile-row"><div className="profile-avatar">S</div><span><b>Sensei</b><small>Administrator</small></span><ChevronDown size={15} /></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-separator">/</span><strong>Dashboard</strong></div>
          <div className="topbar-actions">
            <span className="environment-tag"><span /> DEMO ENVIRONMENT</span>
            <button className="icon-button" aria-label="Search"><Search size={18} /></button>
            <button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><i /></button>
            <button className="user-menu"><span className="profile-avatar small">S</span><ChevronDown size={14} /></button>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">THURSDAY, NOVEMBER 19, 2026</p>
              <h1>Good morning, Sensei<span>.</span></h1>
              <p className="page-subtitle">Your Trading Intelligence command center.</p>
            </div>
            <button className="primary-button"><Sparkles size={16} /> New market analysis</button>
          </section>

          <section className="section-block">
            <div className="section-heading">
              <div><span className="section-kicker">AT A GLANCE</span><h2>Workspace overview</h2></div>
              <span className="updated-label"><span className="live-dot" /> Preview data · Not live</span>
            </div>
            <div className="metrics-grid">{metrics.map((metric) => <MetricCard metric={metric} key={metric.label} />)}</div>
          </section>

          <section className="content-grid">
            <article className="panel market-panel">
              <div className="panel-heading">
                <div><span className="section-kicker">MARKET PULSE</span><h2>Market intelligence</h2></div>
                <button className="text-button">View workspace <ArrowUpRight size={15} /></button>
              </div>
              <div className="market-summary">
                <div className="market-summary-copy"><span className="asset-label">CORE WATCHLIST</span><strong>BTC <small>/ USDT</small></strong><span className="market-note">Market data will appear when the engine is connected.</span></div>
                <div className="market-placeholder"><div className="chart-grid"><span /><span /><span /><span /></div><div className="chart-line"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div><div className="chart-caption">LIVE MARKET CHART · NOT CONNECTED</div></div>
              </div>
              <div className="watchlist-row"><span><b>BTCUSDT</b><small>Bitcoin</small></span><strong>—</strong><StatusPill tone="neutral">No live feed</StatusPill></div>
              <div className="watchlist-row"><span><b>ETHUSDT</b><small>Ethereum</small></span><strong>—</strong><StatusPill tone="neutral">No live feed</StatusPill></div>
            </article>

            <article className="panel skills-panel">
              <div className="panel-heading"><div><span className="section-kicker">CAPABILITIES</span><h2>Trading skills</h2></div><span className="skill-total">04</span></div>
              <div className="skill-item"><span className="skill-icon"><ArrowUpRight size={17} /></span><span><b>Opening analysis</b><small>Previous completed session</small></span><StatusPill tone="success">Ready</StatusPill></div>
              <div className="skill-item"><span className="skill-icon"><ArrowDownRight size={17} /></span><span><b>Closing analysis</b><small>Session just closed</small></span><StatusPill tone="success">Ready</StatusPill></div>
              <div className="skill-item"><span className="skill-icon"><Activity size={17} /></span><span><b>Intraday analysis</b><small>Current market snapshot</small></span><StatusPill tone="success">Ready</StatusPill></div>
              <div className="skill-item"><span className="skill-icon"><CheckCircle2 size={17} /></span><span><b>Skills audit</b><small>Independent quality review</small></span><StatusPill tone="success">Ready</StatusPill></div>
              <button className="secondary-button">Explore skills <ArrowUpRight size={15} /></button>
            </article>
          </section>

          <section className="panel activity-panel">
            <div className="panel-heading">
              <div><span className="section-kicker">WORKSPACE ACTIVITY</span><h2>Recent jobs & reports</h2></div>
              <button className="text-button">View all activity <ArrowUpRight size={15} /></button>
            </div>
            <div className="activity-table-wrap">
              <table className="activity-table">
                <thead><tr><th>Job</th><th>Created</th><th>Type</th><th>Status</th><th aria-label="Actions" /></tr></thead>
                <tbody>{activities.map((activity) => {
                  const Icon = activity.icon;
                  return <tr key={activity.title}><td><div className="job-name"><span className="job-icon"><Icon size={16} /></span><span><b>{activity.title}</b><small>{activity.subtitle}</small></span></div></td><td>{activity.time}</td><td><span className="type-label">Market report</span></td><td><StatusPill tone={activity.tone}>{activity.status}</StatusPill></td><td><button className="row-action" aria-label={`Open ${activity.title}`}><ArrowUpRight size={16} /></button></td></tr>;
                })}</tbody>
              </table>
            </div>
          </section>
          <footer className="page-footer"><span>MASTER ARSENAL <b>v0.1.0</b></span><span>Trading Intelligence · Front-End foundation</span></footer>
        </div>
      </main>
    </div>
  );
}
