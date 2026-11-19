import { useMemo, useState } from "react";
import { BriefcaseBusiness, CheckCircle2, ChevronRight, FileText, LockKeyhole, RotateCcw, ShieldCheck } from "lucide-react";

type Locale = "en" | "es";
type SkillId = "opening" | "closing" | "intraday" | "audit";

const copy = {
  en: {
    eyebrow:"OPERATIONS · JOB REQUEST", title:"Create an analysis job", intro:"Configure a request, review its parameters and prepare it for the governed execution workflow.",
    skill:"Analysis skill", market:"Market", assets:"Assets / symbols", interval:"Primary interval", window:"Analysis window", output:"Output format", notes:"Instructions / context",
    opening:"Opening Analysis", closing:"Closing Analysis", intraday:"Intraday Analysis", audit:"Skills Audit",
    spot:"Binance Spot", futures:"Binance Futures", session:"Current session", four:"Last 4 hours", twelve:"Last 12 hours", day:"Last 24 hours", previous:"Previous completed session",
    pdf:"PDF report", json:"Structured JSON evidence", both:"PDF + JSON evidence", placeholder:"Add optional context for the analysis request…",
    review:"Request review", request:"Request summary", status:"Draft · Not submitted", selected:"Selected skill", scope:"Request scope", destination:"Output destination", governance:"Execution governance",
    rule1:"No job is submitted from this preview.", rule2:"Local Engine integration is required to validate inputs and create a real job.", rule3:"Any required approval must be granted before execution.",
    save:"Mark draft ready", reset:"Reset form", ready:"Draft prepared locally", unavailable:"Submission unavailable", pending:"Backend connection required",
    assetsHint:"Separate multiple symbols with commas. Symbols are not validated until the engine is connected.",
    noExecution:"No execution, approval or report record has been created."
  },
  es: {
    eyebrow:"OPERACIONES · SOLICITUD DE TRABAJO", title:"Crear un trabajo de análisis", intro:"Configura una solicitud, revisa sus parámetros y prepárala para el flujo de ejecución gobernado.",
    skill:"Skill de análisis", market:"Mercado", assets:"Activos / símbolos", interval:"Intervalo principal", window:"Ventana de análisis", output:"Formato de salida", notes:"Instrucciones / contexto",
    opening:"Análisis de apertura", closing:"Análisis de cierre", intraday:"Análisis intradía", audit:"Auditoría de skills",
    spot:"Binance Spot", futures:"Binance Futures", session:"Sesión actual", four:"Últimas 4 horas", twelve:"Últimas 12 horas", day:"Últimas 24 horas", previous:"Sesión completada anterior",
    pdf:"Informe PDF", json:"Evidencia JSON estructurada", both:"PDF + evidencia JSON", placeholder:"Agrega contexto opcional para la solicitud de análisis…",
    review:"Revisar solicitud", request:"Resumen de la solicitud", status:"Borrador · No enviado", selected:"Skill seleccionada", scope:"Alcance", destination:"Destino de salida", governance:"Gobernanza de ejecución",
    rule1:"Este entorno de vista previa no envía trabajos.", rule2:"Se requiere integrar Local Engine para validar los datos y crear un trabajo real.", rule3:"Cualquier aprobación requerida debe concederse antes de la ejecución.",
    save:"Marcar borrador como listo", reset:"Restablecer formulario", ready:"Borrador preparado localmente", unavailable:"Envío no disponible", pending:"Se requiere conexión con el backend",
    assetsHint:"Separa varios símbolos con comas. Los símbolos no se validan hasta conectar el motor.",
    noExecution:"No se ha creado ninguna ejecución, aprobación ni registro de informe."
  }
};

export default function JobCenter({ locale }: { locale: Locale }) {
  const t = copy[locale];
  const [skill, setSkill] = useState<SkillId>("opening");
  const [market, setMarket] = useState("spot");
  const [assets, setAssets] = useState("BTCUSDT, ETHUSDT");
  const [interval, setInterval] = useState("1h");
  const [window, setWindow] = useState("previous");
  const [output, setOutput] = useState("both");
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState(false);
  const skillNames: Record<SkillId, string> = { opening:t.opening, closing:t.closing, intraday:t.intraday, audit:t.audit };
  const assetList = useMemo(() => assets.split(",").map((item) => item.trim()).filter(Boolean), [assets]);
  const windowLabels: Record<string, string> = { previous:t.previous, session:t.session, "4h":t.four, "12h":t.twelve, "24h":t.day };

  const reset = () => { setSkill("opening"); setMarket("spot"); setAssets("BTCUSDT, ETHUSDT"); setInterval("1h"); setWindow("previous"); setOutput("both"); setNotes(""); setSaved(false); };
  const save = () => setSaved(true);

  return <div className="job-center-workspace">
    <section className="job-center-intro">
      <div><span className="section-kicker">{t.eyebrow}</span><h2>{t.title}</h2><p>{t.intro}</p></div>
      <span className="job-preview-state"><span/> {t.status}</span>
    </section>
    <div className="job-center-grid">
      <section className="panel job-request-panel">
        <div className="panel-heading"><div><span className="section-kicker">01 · CONFIGURATION</span><h2>{t.review}</h2></div><BriefcaseBusiness size={19}/></div>
        <div className="job-form-grid">
          <label className="job-field job-field-wide"><span>{t.skill}</span><select value={skill} onChange={e => {setSkill(e.target.value as SkillId);setSaved(false);}}><option value="opening">{t.opening}</option><option value="closing">{t.closing}</option><option value="intraday">{t.intraday}</option><option value="audit">{t.audit}</option></select></label>
          <label className="job-field"><span>{t.market}</span><select value={market} onChange={e => {setMarket(e.target.value);setSaved(false);}}><option value="spot">{t.spot}</option><option value="futures">{t.futures}</option></select></label>
          <label className="job-field"><span>{t.interval}</span><select value={interval} onChange={e => {setInterval(e.target.value);setSaved(false);}}><option>1m</option><option>5m</option><option>15m</option><option>1h</option><option>4h</option><option>1d</option></select></label>
          <label className="job-field job-field-wide"><span>{t.assets}</span><input value={assets} onChange={e => {setAssets(e.target.value);setSaved(false);}}/><small>{t.assetsHint}</small></label>
          <label className="job-field"><span>{t.window}</span><select value={window} onChange={e => {setWindow(e.target.value);setSaved(false);}}><option value="previous">{t.previous}</option><option value="session">{t.session}</option><option value="4h">{t.four}</option><option value="12h">{t.twelve}</option><option value="24h">{t.day}</option></select></label>
          <label className="job-field"><span>{t.output}</span><select value={output} onChange={e => {setOutput(e.target.value);setSaved(false);}}><option value="pdf">{t.pdf}</option><option value="json">{t.json}</option><option value="both">{t.both}</option></select></label>
          <label className="job-field job-field-wide"><span>{t.notes}</span><textarea value={notes} onChange={e => {setNotes(e.target.value);setSaved(false);}} placeholder={t.placeholder} rows={4}/></label>
        </div>
        <div className="job-form-actions"><button type="button" className="secondary-button" onClick={reset}><RotateCcw size={15}/>{t.reset}</button><button type="button" className="primary-button" onClick={save}><CheckCircle2 size={15}/>{t.save}</button></div>
        {saved && <p className="job-saved-notice"><CheckCircle2 size={15}/>{t.ready}</p>}
      </section>
      <aside className="job-request-side">
        <section className="panel job-summary-panel">
          <div className="panel-heading"><div><span className="section-kicker">02 · REVIEW</span><h2>{t.request}</h2></div><FileText size={18}/></div>
          <div className="job-summary-status"><span className="job-status-dot"/><b>{t.status}</b></div>
          <dl><div><dt>{t.selected}</dt><dd>{skillNames[skill]}</dd></div><div><dt>{t.market}</dt><dd>{market === "spot" ? t.spot : t.futures}</dd></div><div><dt>{t.scope}</dt><dd>{assetList.length ? assetList.join(", ") : "—"}</dd></div><div><dt>{t.interval}</dt><dd>{interval}</dd></div><div><dt>{t.window}</dt><dd>{windowLabels[window]}</dd></div><div><dt>{t.destination}</dt><dd>{output === "pdf" ? t.pdf : output === "json" ? t.json : t.both}</dd></div></dl>
        </section>
        <section className="panel job-governance-panel">
          <div className="panel-heading"><div><span className="section-kicker">03 · GOVERNANCE</span><h2>{t.governance}</h2></div><ShieldCheck size={18}/></div>
          <p><LockKeyhole size={15}/>{t.rule1}</p><p><LockKeyhole size={15}/>{t.rule2}</p><p><LockKeyhole size={15}/>{t.rule3}</p>
          <button type="button" className="job-submit-disabled" disabled><LockKeyhole size={15}/>{t.unavailable}<ChevronRight size={15}/></button>
          <small>{t.pending}</small>
        </section>
      </aside>
    </div>
    <div className="job-center-footnote"><ShieldCheck size={15}/>{t.noExecution}</div>
  </div>;
}
