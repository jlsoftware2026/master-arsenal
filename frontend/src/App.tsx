import { useEffect, useState } from "react";
import type { ReactNode } from "react";
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
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Waves,
  X,
  Zap,
} from "lucide-react";
import { formatCompactNumber } from "./lib/formatters.js";

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
  { label: "Reports generated", value: formatCompactNumber(18), detail: "This workspace · Demo data", tone: "neutral", icon: FileText },
  { label: "Available skills", value: "04", detail: "Trading Intelligence", tone: "positive", icon: Sparkles },
];

const activities = [
  { title: "Market closing report", subtitle: "Binance Spot · BTCUSDT / ETHUSDT", time: "Today, 08:15", status: "Completed", tone: "success", icon: FileText },
  { title: "Intraday market snapshot", subtitle: "Binance Spot · 1h interval", time: "Today, 07:42", status: "Awaiting approval", tone: "warning", icon: Activity },
  { title: "Opening market analysis", subtitle: "Binance Spot · Previous session", time: "Yesterday, 17:05", status: "Completed", tone: "success", icon: LineChart },
];

const navigation = [
  { id: "workspace", label: "Workspace", items: [{ id: "dashboard", label: "Dashboard", icon: LayoutDashboard, description: "Your command center for market intelligence, skills and workspace activity." }] },
  { id: "market", label: "Market Intelligence", items: [
    { id: "opening-analysis", label: "Opening Analysis", icon: ArrowUpRight, description: "Review the previous completed market session and prepare the opening outlook." },
    { id: "closing-analysis", label: "Closing Analysis", icon: ArrowDownRight, description: "Assess the completed session, key movements and closing conditions." },
    { id: "intraday-analysis", label: "Intraday Analysis", icon: Activity, description: "Inspect current market conditions and intraday developments." },
  ] },
  { id: "skills", label: "Skills Management", items: [
    { id: "skills-overview", label: "Skills Overview", icon: Sparkles, description: "Review the four Trading Intelligence skills and their availability." },
    { id: "skills-audit", label: "Skills Audit", icon: ShieldCheck, description: "Review skill integrity, evidence and validation results." },
  ] },
  { id: "operations", label: "Operations", items: [
    { id: "job-center", label: "Job Center", icon: BriefcaseBusiness, description: "Create, inspect and monitor analysis jobs." },
    { id: "approvals", label: "Approvals", icon: CheckCircle2, description: "Review jobs that require explicit approval before execution." },
    { id: "execution-history", label: "Execution History", icon: Clock3, description: "Inspect previous job runs and their outcomes." },
  ] },
  { id: "reports", label: "Reports", items: [
    { id: "report-library", label: "Report Library", icon: BookOpen, description: "Browse and open reports generated in this workspace." },
  ] },
  { id: "settings", label: "Settings", items: [
    { id: "general-settings", label: "General", icon: Settings2, description: "Manage general application and workspace settings." },
    { id: "preferences", label: "Preferences", icon: Settings2, description: "Configure display and personal preferences." },
  ] },
];

function StatusPill({ children, tone }: { children: ReactNode; tone: string }) {
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

function LocalDateTime() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const intervalId = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(intervalId);
  }, []);

  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const date = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone,
  }).format(now);
  const time = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone,
  }).format(now);
  const zoneLabel = new Intl.DateTimeFormat(undefined, {
    timeZone,
    timeZoneName: "short",
  }).formatToParts(now).find((part) => part.type === "timeZoneName")?.value;

  return (
    <div className="local-datetime" aria-label={`Local time: ${date}, ${time}, ${timeZone}`}>
      <span className="local-date">{date.toUpperCase()}</span>
      <span className="datetime-separator" aria-hidden="true">|</span>
      <time className="local-time">{time}</time>
      <span className="timezone-label">{timeZone.replaceAll("_", " ")} · {zoneLabel}</span>
    </div>
  );
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activePage, setActivePage] = useState("dashboard");
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    workspace: true,
    market: true,
    skills: true,
    operations: true,
    reports: true,
    settings: true,
  });
  const currentPage = navigation.flatMap((group) => group.items).find((item) => item.id === activePage) ?? navigation[0].items[0];

  const toggleNavigation = () => {
    if (window.matchMedia("(max-width: 760px)").matches) {
      setMobileMenuOpen((open) => !open);
    } else {
      setSidebarCollapsed((collapsed) => !collapsed);
    }
  };

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${mobileMenuOpen ? "mobile-menu-open" : ""}`}>
      <button
        className="sidebar-backdrop"
        aria-label="Close navigation menu"
        tabIndex={mobileMenuOpen ? 0 : -1}
        onClick={() => setMobileMenuOpen(false)}
      />
      <aside className={`sidebar ${mobileMenuOpen ? "mobile-open" : ""}`}>
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
          {navigation.map((group) => {
            const expanded = expandedGroups[group.id];
            return (
              <div className="nav-group" key={group.id}>
                <button
                  className="nav-group-toggle"
                  type="button"
                  aria-expanded={expanded}
                  onClick={() => setExpandedGroups((current) => ({ ...current, [group.id]: !current[group.id] }))}
                >
                  <span className="nav-label">{group.label}</span>
                  <ChevronDown className={expanded ? "group-chevron expanded" : "group-chevron"} size={14} />
                </button>
                {expanded && <div className="nav-group-items">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    return (
                      <button
                        className={`nav-link ${activePage === item.id ? "active" : ""}`}
                        type="button"
                        key={item.id}
                        aria-current={activePage === item.id ? "page" : undefined}
                        onClick={() => {
                          setActivePage(item.id);
                          setMobileMenuOpen(false);
                        }}
                      >
                        <Icon size={17} strokeWidth={1.8} />
                        <span>{item.label}</span>
                        {item.id === "approvals" && <i className="nav-count">1</i>}
                      </button>
                    );
                  })}
                </div>}
              </div>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <a className="nav-link" href="#"><CircleHelp size={17} /><span>Help & support</span></a>
          <div className="engine-status"><span className="engine-pulse" /><span><b>Local engine</b><small>Interface preview · Not connected</small></span></div>
          <div className="profile-row"><div className="profile-avatar">A</div><span><b>Administrator</b><small>Workspace owner</small></span><ChevronDown size={15} /></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="menu-toggle icon-button" onClick={toggleNavigation} aria-label={mobileMenuOpen ? "Close navigation" : "Toggle navigation"} aria-expanded={mobileMenuOpen}>
            {mobileMenuOpen ? <X size={19} /> : <Menu size={19} />}
          </button>
          <div className="breadcrumbs"><span>MASTER ARSENAL</span><span className="crumb-separator">/</span><strong>{currentPage.label}</strong></div>
          <div className="topbar-actions">
            <span className="environment-tag"><span /> DEMO ENVIRONMENT</span>
            <button className="icon-button" aria-label="Search"><Search size={18} /></button>
            <button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><i /></button>
            <button className="user-menu"><span className="profile-avatar small">A</span><ChevronDown size={14} /></button>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <LocalDateTime />
              <h1>{activePage === "dashboard" ? <>Good morning<span>.</span></> : <>{currentPage.label}<span>.</span></>}</h1>
              <p className="page-subtitle">{activePage === "dashboard" ? "Your Trading Intelligence command center." : currentPage.description}</p>
            </div>
            {activePage === "dashboard" && <button className="primary-button" onClick={() => setActivePage("intraday-analysis")}><Sparkles size={16} /> New market analysis</button>}
          </section>

          {activePage === "dashboard" ? <>
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
          </> : <section className="module-placeholder">
            <article className="panel module-placeholder-panel">
              <span className="section-kicker">MODULE WORKSPACE</span>
              <h2>{currentPage.label}</h2>
              <p>{currentPage.description}</p>
              <div className="module-placeholder-note">
                <span className="engine-pulse" />
                <span><b>Interface foundation</b><small>This section is scaffolded. Its workflow and live data connection will be implemented in the next development steps.</small></span>
              </div>
            </article>
          </section>}
          <footer className="page-footer"><span>MASTER ARSENAL <b>v0.1.0</b></span><span>Trading Intelligence · Front-End foundation</span></footer>
        </div>
      </main>
    </div>
  );
}
