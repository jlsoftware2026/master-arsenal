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
  CalendarDays,
  CandlestickChart,
  Gauge,
  Newspaper,
  Target,
  TrendingUp,
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


type OpeningTab = "overview" | "technical" | "derivatives" | "macro" | "scenarios" | "report";

const openingTabs: { id: OpeningTab; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "technical", label: "Technical", icon: CandlestickChart },
  { id: "derivatives", label: "Derivatives", icon: Gauge },
  { id: "macro", label: "Macro & News", icon: Newspaper },
  { id: "scenarios", label: "Scenarios", icon: Target },
  { id: "report", label: "Report", icon: FileText },
];

function DataPending({ label = "Awaiting market data" }: { label?: string }) {
  return <span className="data-pending"><span />{label}</span>;
}

function OpeningAnalysis() {
  const [activeTab, setActiveTab] = useState<OpeningTab>("overview");
  const [selectedMarket, setSelectedMarket] = useState("Binance Spot");
  const [selectedAsset, setSelectedAsset] = useState("BTCUSDT");

  return (
    <div className="opening-workspace">
      <section className="opening-commandbar">
        <div className="opening-context">
          <span className="section-kicker">PREVIOUS COMPLETED SESSION</span>
          <div className="opening-session-title"><CalendarDays size={17} /><strong>Opening preparation</strong><span className="session-separator">/</span><span>Session reference pending</span></div>
        </div>
        <div className="opening-filters">
          <label><span>MARKET</span><select value={selectedMarket} onChange={(event) => setSelectedMarket(event.target.value)}><option>Binance Spot</option><option>Binance Futures</option></select></label>
          <label><span>REFERENCE ASSET</span><select value={selectedAsset} onChange={(event) => setSelectedAsset(event.target.value)}><option>BTCUSDT</option><option>ETHUSDT</option><option>BNBUSDT</option><option>SOLUSDT</option></select></label>
        </div>
      </section>

      <div className="opening-tabs" role="tablist" aria-label="Opening analysis sections">
        {openingTabs.map((tab) => {
          const Icon = tab.icon;
          return <button key={tab.id} type="button" role="tab" aria-selected={activeTab === tab.id} className={activeTab === tab.id ? "opening-tab active" : "opening-tab"} onClick={() => setActiveTab(tab.id)}><Icon size={15} /><span>{tab.label}</span></button>;
        })}
      </div>

      {activeTab === "overview" && <>
        <section className="opening-status-grid">
          <article className="opening-stat-card"><span>REFERENCE SESSION</span><strong>—</strong><small>Previous completed session</small></article>
          <article className="opening-stat-card"><span>MARKET SCOPE</span><strong>{selectedMarket}</strong><small>{selectedAsset} · Reference asset</small></article>
          <article className="opening-stat-card"><span>DATA AVAILABILITY</span><strong className="pending-value">Not connected</strong><small>Market feed unavailable in preview</small></article>
          <article className="opening-stat-card"><span>ANALYSIS STATUS</span><strong className="pending-value">Not generated</strong><small>Waiting for MALE integration</small></article>
        </section>

        <section className="opening-overview-grid">
          <article className="panel opening-session-panel">
            <div className="panel-heading"><div><span className="section-kicker">SESSION STRUCTURE</span><h2>Previous session snapshot</h2></div><DataPending label="No session data" /></div>
            <div className="session-chart-placeholder">
              <div className="session-chart-y"><span>—</span><span>—</span><span>—</span><span>—</span></div>
              <div className="session-chart-grid"><i /><i /><i /><i /></div>
              <div className="session-chart-empty"><CandlestickChart size={25} /><b>Market structure will appear here</b><small>OHLC candles, session range and key levels</small></div>
              <div className="session-chart-x"><span>SESSION OPEN</span><span>SESSION CLOSE</span></div>
            </div>
            <div className="session-legend"><span><i className="legend-candle up" /> Bullish candle</span><span><i className="legend-candle down" /> Bearish candle</span><span><i className="legend-line" /> Key levels</span></div>
          </article>

          <article className="panel opening-brief-panel">
            <div className="panel-heading"><div><span className="section-kicker">OPENING BRIEF</span><h2>Market conditions</h2></div><span className="brief-icon"><Activity size={17} /></span></div>
            <div className="brief-empty-state"><span className="brief-empty-icon"><TrendingUp size={19} /></span><b>Opening assessment pending</b><p>The previous session trend, volatility, volume profile and market bias will be summarized here after data becomes available.</p></div>
            <div className="brief-checklist">
              <div><span>Session direction</span><DataPending label="Pending" /></div>
              <div><span>Volatility regime</span><DataPending label="Pending" /></div>
              <div><span>Key support & resistance</span><DataPending label="Pending" /></div>
              <div><span>Opening bias</span><DataPending label="Pending" /></div>
            </div>
          </article>
        </section>

        <section className="opening-lower-grid">
          <article className="panel">
            <div className="panel-heading"><div><span className="section-kicker">TECHNICAL LANDSCAPE</span><h2>Indicator matrix</h2></div><button className="text-button" onClick={() => setActiveTab("technical")}>View technicals <ArrowUpRight size={14} /></button></div>
            <div className="indicator-matrix">
              {["EMA 20 / 50 / 200", "RSI 14", "MACD 12 / 26 / 9", "ATR 14", "Bollinger Bands", "Volume profile"].map((name) => <div key={name}><span>{name}</span><DataPending label="—" /></div>)}
            </div>
          </article>
          <article className="panel">
            <div className="panel-heading"><div><span className="section-kicker">DERIVATIVES & SENTIMENT</span><h2>Positioning signals</h2></div><button className="text-button" onClick={() => setActiveTab("derivatives")}>View signals <ArrowUpRight size={14} /></button></div>
            <div className="signal-list">
              {["Funding rate", "Open interest", "Liquidations", "Long / short positioning"].map((name) => <div key={name}><span>{name}</span><DataPending label="—" /></div>)}
            </div>
          </article>
        </section>
      </>}

      {activeTab === "technical" && <section className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">TECHNICAL ANALYSIS</span><h2>Trend, momentum & volatility</h2></div><DataPending /></div><p className="opening-detail-copy">Technical readings will be calculated from the selected market and reference session. No indicator values are simulated in this preview.</p><div className="technical-cards">{["EMA 20", "EMA 50", "EMA 200", "RSI 14", "MACD", "ATR 14", "Bollinger Bands", "Volume profile"].map((name) => <div className="technical-card" key={name}><span>{name}</span><strong>—</strong><small>Awaiting data</small></div>)}</div></section>}

      {activeTab === "derivatives" && <section className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">DERIVATIVES & SENTIMENT</span><h2>Market positioning</h2></div><DataPending /></div><p className="opening-detail-copy">Derivatives metrics provide context on leverage and positioning. Values and interpretations will remain unavailable until a verified provider is connected.</p><div className="technical-cards">{["Funding rate", "Open interest", "Open interest change", "Liquidation volume", "Long / short ratio", "Basis"].map((name) => <div className="technical-card" key={name}><span>{name}</span><strong>—</strong><small>Awaiting data</small></div>)}</div></section>}

      {activeTab === "macro" && <section className="opening-detail-panel opening-dual-panels"><article className="panel"><div className="panel-heading"><div><span className="section-kicker">MACROECONOMIC CALENDAR</span><h2>Upcoming events</h2></div><DataPending /></div><div className="opening-empty-block"><CalendarDays size={23} /><b>No calendar connected</b><small>Verified macro events and release times will appear here.</small></div></article><article className="panel"><div className="panel-heading"><div><span className="section-kicker">NEWS FLOW</span><h2>Market headlines</h2></div><DataPending /></div><div className="opening-empty-block"><Newspaper size={23} /><b>No news provider connected</b><small>Headlines, timestamps, sources and relevance assessments will appear here.</small></div></article></section>}

      {activeTab === "scenarios" && <section className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">SCENARIO FRAMEWORK</span><h2>Opening market scenarios</h2></div><DataPending label="Not assessed" /></div><p className="opening-detail-copy">Scenarios will be derived from verified market evidence, with explicit triggers, invalidation conditions and risk factors. No probabilities are assigned in this visual preview.</p><div className="scenario-cards"><article><span className="scenario-symbol bullish">↗</span><b>Bullish scenario</b><small>Triggers and confirmation criteria pending.</small><DataPending label="Not assessed" /></article><article><span className="scenario-symbol neutral">→</span><b>Neutral scenario</b><small>Range conditions and balance levels pending.</small><DataPending label="Not assessed" /></article><article><span className="scenario-symbol bearish">↘</span><b>Bearish scenario</b><small>Breakdown triggers and invalidation pending.</small><DataPending label="Not assessed" /></article></div></section>}

      {activeTab === "report" && <section className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">ANALYSIS OUTPUT</span><h2>Opening analysis report</h2></div><DataPending label="Not generated" /></div><div className="report-preview"><FileText size={27} /><div><b>Report preview unavailable</b><small>The report will be assembled after the opening workflow has completed and its evidence has been validated.</small></div></div><div className="report-sections">{["Executive summary", "Market structure & technicals", "Derivatives & sentiment", "Macro context & news", "Scenarios, risks & invalidation", "Sources & evidence"].map((name, index) => <div key={name}><span>{String(index + 1).padStart(2, "0")}</span>{name}<DataPending label="Pending" /></div>)}</div></section>}
    </div>
  );
}


type ClosingTab = "overview" | "session" | "technical" | "derivatives" | "macro" | "scenarios" | "report";
const closingTabs: { id: ClosingTab; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "session", label: "Session Review", icon: CandlestickChart },
  { id: "technical", label: "Technical", icon: LineChart },
  { id: "derivatives", label: "Derivatives", icon: Gauge },
  { id: "macro", label: "Macro & News", icon: Newspaper },
  { id: "scenarios", label: "Outlook", icon: Target },
  { id: "report", label: "Report", icon: FileText },
];

function ClosingAnalysis() {
  const [tab, setTab] = useState<ClosingTab>("overview");
  const [market, setMarket] = useState("Binance Spot");
  const [asset, setAsset] = useState("BTCUSDT");
  const pendingMetrics = ["Session open / close", "High / low", "Net change", "Total volume", "Volatility", "Market breadth"];
  return <div className="market-workspace closing-workspace">
    <section className="opening-commandbar">
      <div className="opening-context"><span className="section-kicker">COMPLETED MARKET SESSION</span><div className="opening-session-title"><CalendarDays size={17}/><strong>Closing review</strong><span className="session-separator">/</span><span>Session date pending</span></div></div>
      <div className="opening-filters">
        <label><span>MARKET</span><select value={market} onChange={e=>setMarket(e.target.value)}><option>Binance Spot</option><option>Binance Futures</option></select></label>
        <label><span>REFERENCE ASSET</span><select value={asset} onChange={e=>setAsset(e.target.value)}><option>BTCUSDT</option><option>ETHUSDT</option><option>BNBUSDT</option><option>SOLUSDT</option></select></label>
      </div>
    </section>
    <div className="opening-tabs" role="tablist" aria-label="Closing analysis sections">{closingTabs.map(t=>{const I=t.icon;return <button key={t.id} role="tab" aria-selected={tab===t.id} className={tab===t.id?"opening-tab active":"opening-tab"} onClick={()=>setTab(t.id)}><I size={15}/><span>{t.label}</span></button>;})}</div>
    {tab==="overview" && <>
      <div className="opening-status-grid">{[{l:"SESSION RESULT",v:"Not assessed",d:"Final session direction"},{l:"MARKET SCOPE",v:market,d:asset+" · Reference asset"},{l:"DATA COMPLETENESS",v:"Not connected",d:"No verified session feed"},{l:"CLOSING REPORT",v:"Not generated",d:"Awaiting session evidence"}].map(x=><article className="opening-stat-card" key={x.l}><span>{x.l}</span><strong className="pending-value">{x.v}</strong><small>{x.d}</small></article>)}</div>
      <div className="opening-overview-grid">
        <article className="panel"><div className="panel-heading"><div><span className="section-kicker">SESSION PERFORMANCE</span><h2>Full-session price action</h2></div><DataPending label="No session data"/></div><div className="session-chart-placeholder closing-chart"><div className="session-chart-y"><span>HIGH —</span><span>—</span><span>—</span><span>LOW —</span></div><div className="session-chart-grid"><i/><i/><i/><i/></div><div className="session-chart-empty"><CandlestickChart size={25}/><b>Completed session chart unavailable</b><small>OHLC, VWAP, range and closing location</small></div><div className="session-chart-x"><span>SESSION OPEN</span><span>SESSION CLOSE</span></div></div><div className="session-legend"><span><i className="legend-candle up"/> Advancing</span><span><i className="legend-candle down"/> Declining</span><span><i className="legend-line"/> VWAP / levels</span></div></article>
        <article className="panel"><div className="panel-heading"><div><span className="section-kicker">CLOSING ASSESSMENT</span><h2>Session conclusions</h2></div><span className="brief-icon"><CheckCircle2 size={17}/></span></div><div className="brief-empty-state"><span className="brief-empty-icon"><TrendingUp size={19}/></span><b>Session evaluation pending</b><p>Closing strength, trend persistence, participation and late-session activity will be assessed from verified data.</p></div><div className="brief-checklist">{["Session direction","Close location in daily range","Volume confirmation","Volatility expansion / contraction","Key levels reclaimed or lost"].map(x=><div key={x}><span>{x}</span><DataPending label="Pending"/></div>)}</div></article>
      </div>
      <article className="panel"><div className="panel-heading"><div><span className="section-kicker">SESSION STATISTICS</span><h2>Performance summary</h2></div><DataPending/></div><div className="indicator-matrix closing-stat-matrix">{pendingMetrics.map(x=><div key={x}><span>{x}</span><DataPending label="—"/></div>)}</div></article>
    </>}
    {tab==="session" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">SESSION REVIEW</span><h2>Price action & market participation</h2></div><DataPending/></div><p className="opening-detail-copy">The review will compare opening range, intraday extremes, VWAP interaction, volume distribution and closing location. No session statistics are fabricated in this preview.</p><div className="technical-cards">{["Opening range","Session high","Session low","Closing price","VWAP","Volume profile","Range expansion","Close location"].map(x=><div className="technical-card" key={x}><span>{x}</span><strong>—</strong><small>Awaiting session data</small></div>)}</div></article>}
    {tab==="technical" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">TECHNICAL REVIEW</span><h2>Trend, momentum & volatility at close</h2></div><DataPending/></div><p className="opening-detail-copy">Indicator readings will be evaluated at the session close, including direction, slope, divergence and regime changes.</p><div className="technical-cards">{["EMA 20 / 50 / 200","RSI 14","MACD","ATR 14","Bollinger Bands","ADX / trend strength","VWAP deviation","Volume profile"].map(x=><div className="technical-card" key={x}><span>{x}</span><strong>—</strong><small>Awaiting data</small></div>)}</div></article>}
    {tab==="derivatives" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">DERIVATIVES CLOSE</span><h2>Leverage & positioning changes</h2></div><DataPending/></div><p className="opening-detail-copy">End-of-session derivatives context will distinguish price movement supported by position build-up from movement driven by position closure.</p><div className="technical-cards">{["Funding rate","Open interest change","Liquidation totals","Long / short ratio","Perpetual basis","OI vs. price divergence"].map(x=><div className="technical-card" key={x}><span>{x}</span><strong>—</strong><small>Awaiting provider data</small></div>)}</div></article>}
    {tab==="macro" && <div className="opening-dual-panels"><article className="panel"><div className="panel-heading"><div><span className="section-kicker">MACRO CONTEXT</span><h2>Events affecting the session</h2></div><DataPending/></div><div className="opening-empty-block"><CalendarDays size={23}/><b>Calendar not connected</b><small>Only verified releases and timestamps will be included.</small></div></article><article className="panel"><div className="panel-heading"><div><span className="section-kicker">NEWS & CATALYSTS</span><h2>Session headline review</h2></div><DataPending/></div><div className="opening-empty-block"><Newspaper size={23}/><b>News feed not connected</b><small>Source, publication time and market relevance will be retained.</small></div></article></div>}
    {tab==="scenarios" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">FORWARD-LOOKING CLOSE</span><h2>Carry-forward market outlook</h2></div><DataPending label="Not assessed"/></div><p className="opening-detail-copy">Closing evidence will define levels and conditions to monitor in the next session. These are conditional scenarios, not predictions.</p><div className="scenario-cards">{[{n:"Bullish continuation",d:"Acceptance above closing resistance and follow-through."},{n:"Range / consolidation",d:"Balance around value with no confirmed directional break."},{n:"Bearish continuation",d:"Acceptance below support and downside follow-through."}].map((x,i)=><article key={x.n}><span className={`scenario-symbol ${i===0?"bullish":i===1?"neutral":"bearish"}`}>{i===0?"↗":i===1?"→":"↘"}</span><b>{x.n}</b><small>{x.d}</small><DataPending label="Not assessed"/></article>)}</div></article>}
    {tab==="report" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">CLOSING OUTPUT</span><h2>Closing analysis report</h2></div><DataPending label="Not generated"/></div><div className="report-preview"><FileText size={27}/><div><b>Report preview unavailable</b><small>The report will summarize the completed session, evidence, conclusions and next-session watchlist.</small></div></div><div className="report-sections">{["Executive session summary","Price action & session statistics","Technical and derivatives review","Macro events & news catalysts","Closing conclusions & risks","Next-session levels & scenarios","Sources and evidence"].map((x,i)=><div key={x}><span>{String(i+1).padStart(2,"0")}</span>{x}<DataPending label="Pending"/></div>)}</div></article>}
  </div>;
}

type IntradayTab = "overview" | "price" | "momentum" | "derivatives" | "events" | "scenarios" | "report";
const intradayTabs: {id:IntradayTab;label:string;icon:typeof Activity}[] = [
  {id:"overview",label:"Overview",icon:LayoutDashboard},{id:"price",label:"Price Action",icon:CandlestickChart},{id:"momentum",label:"Momentum",icon:Gauge},{id:"derivatives",label:"Derivatives",icon:Waves},{id:"events",label:"Events & News",icon:Newspaper},{id:"scenarios",label:"Scenarios",icon:Target},{id:"report",label:"Snapshot",icon:FileText}
];
function IntradayAnalysis() {
  const [tab,setTab]=useState<IntradayTab>("overview");
  const [market,setMarket]=useState("Binance Spot");
  const [asset,setAsset]=useState("BTCUSDT");
  const [interval,setInterval]=useState("15m");
  const [window,setWindow]=useState("Current session");
  return <div className="market-workspace intraday-workspace">
    <section className="opening-commandbar"><div className="opening-context"><span className="section-kicker">LIVE SESSION MONITOR</span><div className="opening-session-title"><Activity size={17}/><strong>Intraday market monitor</strong><span className="session-separator">/</span><span>Live feed not connected</span></div></div><div className="opening-filters intraday-filters">
      <label><span>MARKET</span><select value={market} onChange={e=>setMarket(e.target.value)}><option>Binance Spot</option><option>Binance Futures</option></select></label>
      <label><span>ASSET</span><select value={asset} onChange={e=>setAsset(e.target.value)}><option>BTCUSDT</option><option>ETHUSDT</option><option>BNBUSDT</option><option>SOLUSDT</option></select></label>
      <label><span>INTERVAL</span><select value={interval} onChange={e=>setInterval(e.target.value)}>{["1m","5m","15m","1h","4h"].map(x=><option key={x}>{x}</option>)}</select></label>
      <label><span>TIME WINDOW</span><select value={window} onChange={e=>setWindow(e.target.value)}><option>Current session</option><option>Last 4 hours</option><option>Last 12 hours</option><option>Last 24 hours</option></select></label>
    </div></section>
    <div className="intraday-feed-warning"><span className="feed-warning-dot"/><div><b>PREVIEW MODE · NO LIVE MARKET DATA</b><small>Controls are visual only. Market values, timestamps and signals remain unavailable until MALE and its approved data providers are connected.</small></div></div>
    <div className="opening-tabs" role="tablist" aria-label="Intraday analysis sections">{intradayTabs.map(t=>{const I=t.icon;return <button key={t.id} role="tab" aria-selected={tab===t.id} className={tab===t.id?"opening-tab active":"opening-tab"} onClick={()=>setTab(t.id)}><I size={15}/><span>{t.label}</span></button>;})}</div>
    {tab==="overview" && <>
      <div className="opening-status-grid">{[{l:"LAST PRICE",v:"—",d:asset+" · "+market},{l:"SESSION CHANGE",v:"—",d:"Change from session open"},{l:"SESSION VOLUME",v:"—",d:"Accumulated base / quote volume"},{l:"MONITOR STATUS",v:"Offline",d:"No live provider connected"}].map(x=><article className="opening-stat-card" key={x.l}><span>{x.l}</span><strong className="pending-value">{x.v==="—"?x.v:x.v}</strong><small>{x.d}</small></article>)}</div>
      <div className="opening-overview-grid"><article className="panel"><div className="panel-heading"><div><span className="section-kicker">INTRADAY PRICE CHART</span><h2>{asset} · {interval}</h2></div><DataPending label="Feed offline"/></div><div className="session-chart-placeholder intraday-chart"><div className="session-chart-y"><span>—</span><span>—</span><span>—</span><span>—</span></div><div className="session-chart-grid"><i/><i/><i/><i/></div><div className="session-chart-empty"><Activity size={25}/><b>Waiting for intraday feed</b><small>Price, VWAP, session levels and volume</small></div><div className="session-chart-x"><span>SESSION START</span><span>NOW</span></div></div></article>
      <article className="panel"><div className="panel-heading"><div><span className="section-kicker">MARKET PULSE</span><h2>Current conditions</h2></div><span className="brief-icon"><Waves size={17}/></span></div><div className="brief-empty-state"><span className="brief-empty-icon"><Gauge size={19}/></span><b>Live assessment unavailable</b><p>Trend state, volatility, momentum and volume participation will update only from timestamped market observations.</p></div><div className="brief-checklist">{["Short-term trend","Momentum state","Volatility regime","Volume confirmation","Support / resistance proximity"].map(x=><div key={x}><span>{x}</span><DataPending label="Pending"/></div>)}</div></article></div>
      <div className="opening-lower-grid"><article className="panel"><div className="panel-heading"><div><span className="section-kicker">MOMENTUM BOARD</span><h2>Intraday indicators</h2></div><button className="text-button" onClick={()=>setTab("momentum")}>View momentum <ArrowUpRight size={14}/></button></div><div className="indicator-matrix">{["RSI 14","MACD histogram","EMA alignment","VWAP deviation","ATR / range","Relative volume"].map(x=><div key={x}><span>{x}</span><DataPending label="—"/></div>)}</div></article><article className="panel"><div className="panel-heading"><div><span className="section-kicker">DERIVATIVES TAPE</span><h2>Positioning activity</h2></div><button className="text-button" onClick={()=>setTab("derivatives")}>View derivatives <ArrowUpRight size={14}/></button></div><div className="signal-list">{["Funding rate","Open interest change","Liquidations","Long / short ratio"].map(x=><div key={x}><span>{x}</span><DataPending label="—"/></div>)}</div></article></div>
    </>}
    {tab==="price" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">PRICE ACTION</span><h2>Intraday structure & key levels</h2></div><DataPending/></div><p className="opening-detail-copy">Track price swings, VWAP, opening range, session high / low, volume nodes and support / resistance. Chart interval: {interval}; window: {window}.</p><div className="technical-cards">{["Last price","Session open","Session high","Session low","VWAP","Opening range","Volume profile","Key levels"].map(x=><div className="technical-card" key={x}><span>{x}</span><strong>—</strong><small>Awaiting live feed</small></div>)}</div></article>}
    {tab==="momentum" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">MOMENTUM & VOLATILITY</span><h2>Short-term market condition</h2></div><DataPending/></div><p className="opening-detail-copy">Indicator values will be calculated for the selected interval and displayed with observation timestamps to avoid stale readings being mistaken for current conditions.</p><div className="technical-cards">{["RSI 14","MACD","EMA 9 / 20","EMA 50","ATR 14","Bollinger width","ADX","Relative volume"].map(x=><div className="technical-card" key={x}><span>{x}</span><strong>—</strong><small>Awaiting live feed</small></div>)}</div></article>}
    {tab==="derivatives" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">DERIVATIVES TAPE</span><h2>Leverage and liquidation activity</h2></div><DataPending/></div><p className="opening-detail-copy">Intraday changes in open interest, funding and liquidations will be time-aligned with price action. No positioning inference is shown without provider evidence.</p><div className="technical-cards">{["Funding rate","Open interest","OI change","Liquidation buys","Liquidation sells","Long / short ratio"].map(x=><div className="technical-card" key={x}><span>{x}</span><strong>—</strong><small>Awaiting provider data</small></div>)}</div></article>}
    {tab==="events" && <div className="opening-dual-panels"><article className="panel"><div className="panel-heading"><div><span className="section-kicker">EVENT TRACKER</span><h2>Upcoming catalysts</h2></div><DataPending/></div><div className="opening-empty-block"><CalendarDays size={23}/><b>Event calendar unavailable</b><small>Event times will be shown with timezone and source.</small></div></article><article className="panel"><div className="panel-heading"><div><span className="section-kicker">NEWS MONITOR</span><h2>Latest market developments</h2></div><DataPending/></div><div className="opening-empty-block"><Newspaper size={23}/><b>News feed unavailable</b><small>Headlines will include publication time, source and relevance.</small></div></article></div>}
    {tab==="scenarios" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">INTRADAY SCENARIOS</span><h2>Conditional setups & invalidation</h2></div><DataPending label="Not assessed"/></div><p className="opening-detail-copy">Intraday scenarios will be conditional on confirmed levels, price acceptance and volume / momentum evidence. No trade execution or automatic order placement is part of this interface.</p><div className="scenario-cards">{[{n:"Upside continuation",d:"Acceptance above intraday resistance with confirming participation."},{n:"Range rotation",d:"Price remains within established value and session balance."},{n:"Downside continuation",d:"Acceptance below support with confirming momentum."}].map((x,i)=><article key={x.n}><span className={`scenario-symbol ${i===0?"bullish":i===1?"neutral":"bearish"}`}>{i===0?"↗":i===1?"→":"↘"}</span><b>{x.n}</b><small>{x.d}</small><DataPending label="Not assessed"/></article>)}</div></article>}
    {tab==="report" && <article className="panel opening-detail-panel"><div className="panel-heading"><div><span className="section-kicker">INTRADAY SNAPSHOT</span><h2>Market monitoring report</h2></div><DataPending label="Not generated"/></div><div className="report-preview"><FileText size={27}/><div><b>Snapshot unavailable</b><small>A timestamped snapshot will capture market state, indicator readings, derivatives, catalysts and scenario changes.</small></div></div><div className="report-sections">{["Snapshot timestamp & data freshness","Price action & session levels","Momentum and volatility","Derivatives positioning","Events and news","Scenarios and invalidation","Sources and evidence"].map((x,i)=><div key={x}><span>{String(i+1).padStart(2,"0")}</span>{x}<DataPending label="Pending"/></div>)}</div></article>}
  </div>;
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

          {activePage === "opening-analysis" ? <OpeningAnalysis /> : activePage === "closing-analysis" ? <ClosingAnalysis /> : activePage === "intraday-analysis" ? <IntradayAnalysis /> : activePage === "dashboard" ? <>
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
