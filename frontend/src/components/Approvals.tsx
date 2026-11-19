import { useState } from "react";
import { CheckCircle2, ClipboardCheck, Clock3, FileCheck2, LockKeyhole, ShieldAlert, ShieldCheck } from "lucide-react";

type Locale = "en" | "es";
type ApprovalFilter = "pending" | "approved" | "rejected";

const copy = {
  en: {
    eyebrow:"OPERATIONS · GOVERNANCE", title:"Approval queue", intro:"Review and authorize analysis jobs before the Local Engine is allowed to execute them.", preview:"PREVIEW · BACKEND NOT CONNECTED",
    pending:"Pending", approved:"Approved", rejected:"Rejected", inbox:"Approval inbox", records:"Records: unavailable",
    emptyTitle:"No approval records available", emptyPending:"The Local Engine has not supplied a pending approval queue. When connected, requests requiring your authorization will appear here.", emptyApproved:"No approved requests are available in this workspace view.", emptyRejected:"No rejected requests are available in this workspace view.",
    noDecision:"Approval decisions are unavailable in preview", policy:"Approval policy", policyIntro:"Explicit human authorization is required before a governed job can proceed.",
    review:"Review the request", reviewText:"Inspect the requested skill, market scope, parameters, output and supporting evidence.",
    risk:"Assess the risk", riskText:"Confirm the request respects skill permissions and does not attempt account mutation or order placement.",
    record:"Record the decision", recordText:"Persist the decision with reviewer identity, timestamp and rationale.",
    boundary:"Execution boundary", boundaryText:"Approval only authorizes an eligible job to proceed to its governed execution stage. It does not place trades, submit exchange orders or bypass runtime controls.",
    audit:"Decision audit trail", auditEmpty:"No approval decisions recorded", auditText:"Decision history will appear after the Local Engine provides persisted approval records.",
    unavailable:"Backend connection required", unavailableText:"This interface is not connected to the Local Engine. No request can be approved, rejected or executed from this preview.",
    pendingHelp:"Requests awaiting explicit authorization", approvedHelp:"Previously authorized requests", rejectedHelp:"Requests declined by a reviewer"
  },
  es: {
    eyebrow:"OPERACIONES · GOBERNANZA", title:"Cola de aprobaciones", intro:"Revisa y autoriza los trabajos de análisis antes de permitir que Local Engine los ejecute.", preview:"VISTA PREVIA · BACKEND NO CONECTADO",
    pending:"Pendientes", approved:"Aprobadas", rejected:"Rechazadas", inbox:"Bandeja de aprobaciones", records:"Registros: no disponibles",
    emptyTitle:"No hay registros de aprobación disponibles", emptyPending:"Local Engine todavía no ha proporcionado una cola de aprobaciones pendientes. Al conectarse, aquí aparecerán las solicitudes que requieran tu autorización.", emptyApproved:"No hay solicitudes aprobadas disponibles en esta vista.", emptyRejected:"No hay solicitudes rechazadas disponibles en esta vista.",
    noDecision:"Las decisiones no están disponibles en la vista previa", policy:"Política de aprobación", policyIntro:"La autorización humana explícita es obligatoria antes de que un trabajo gobernado pueda continuar.",
    review:"Revisar la solicitud", reviewText:"Inspecciona la skill solicitada, el alcance de mercado, los parámetros, la salida y la evidencia.",
    risk:"Evaluar el riesgo", riskText:"Confirma que la solicitud respete los permisos de la skill y no intente modificar cuentas ni colocar órdenes.",
    record:"Registrar la decisión", recordText:"Persiste la decisión con la identidad del revisor, fecha y hora, y justificación.",
    boundary:"Límite de ejecución", boundaryText:"La aprobación solo autoriza que un trabajo elegible pase a su etapa de ejecución gobernada. No opera, no envía órdenes al exchange ni omite controles del runtime.",
    audit:"Registro de auditoría", auditEmpty:"No hay decisiones de aprobación registradas", auditText:"El historial aparecerá cuando Local Engine proporcione registros de aprobación persistidos.",
    unavailable:"Se requiere conexión con el backend", unavailableText:"Esta interfaz no está conectada a Local Engine. Desde esta vista previa no se puede aprobar, rechazar ni ejecutar ninguna solicitud.",
    pendingHelp:"Solicitudes que esperan autorización explícita", approvedHelp:"Solicitudes autorizadas anteriormente", rejectedHelp:"Solicitudes rechazadas por un revisor"
  }
};

export default function Approvals({ locale }: { locale: Locale }) {
  const t = copy[locale];
  const [filter, setFilter] = useState<ApprovalFilter>("pending");
  const help = { pending:t.pendingHelp, approved:t.approvedHelp, rejected:t.rejectedHelp };
  const empty = { pending:t.emptyPending, approved:t.emptyApproved, rejected:t.emptyRejected };
  return <div className="approvals-workspace">
    <section className="approvals-intro"><div><span className="section-kicker">{t.eyebrow}</span><h2>{t.title}</h2><p>{t.intro}</p></div><span className="approvals-preview">{t.preview}</span></section>
    <section className="approvals-summary-grid">
      {(["pending","approved","rejected"] as ApprovalFilter[]).map((key) => <article className="panel approvals-summary-card" key={key}><span>{t[key]}</span><strong>—</strong><small>{help[key]}</small></article>)}
    </section>
    <section className="panel approvals-inbox">
      <div className="panel-heading"><div><span className="section-kicker">01 · REVIEW WORKFLOW</span><h2>{t.inbox}</h2></div><span className="approvals-record-count">{t.records}</span></div>
      <div className="approvals-filter-tabs" role="tablist" aria-label={t.inbox}>
        {(["pending","approved","rejected"] as ApprovalFilter[]).map((key) => <button key={key} type="button" role="tab" aria-selected={filter===key} className={filter===key ? "active" : ""} onClick={() => setFilter(key)}>{t[key]}</button>)}
      </div>
      <div className="approvals-empty-state"><span className="approvals-empty-icon"><ClipboardCheck size={25}/></span><b>{t.emptyTitle}</b><p>{empty[filter]}</p><small>{help[filter]}</small></div>
      <div className="approvals-disabled-actions"><span><LockKeyhole size={15}/>{t.noDecision}</span><div><button disabled><CheckCircle2 size={14}/>{t.approved}</button><button disabled><ShieldAlert size={14}/>{t.rejected}</button></div></div>
    </section>
    <div className="approvals-lower-grid">
      <section className="panel approvals-policy"><div className="panel-heading"><div><span className="section-kicker">02 · GOVERNANCE</span><h2>{t.policy}</h2></div><ShieldCheck size={19}/></div><p className="approvals-panel-intro">{t.policyIntro}</p>
        <div className="approvals-policy-list"><article><span>01</span><div><b>{t.review}</b><p>{t.reviewText}</p></div></article><article><span>02</span><div><b>{t.risk}</b><p>{t.riskText}</p></div></article><article><span>03</span><div><b>{t.record}</b><p>{t.recordText}</p></div></article></div>
        <div className="approvals-boundary"><LockKeyhole size={16}/><div><b>{t.boundary}</b><p>{t.boundaryText}</p></div></div>
      </section>
      <section className="panel approvals-audit"><div className="panel-heading"><div><span className="section-kicker">03 · TRACEABILITY</span><h2>{t.audit}</h2></div><FileCheck2 size={19}/></div>
        <div className="approvals-audit-empty"><Clock3 size={22}/><b>{t.auditEmpty}</b><p>{t.auditText}</p></div>
        <div className="approvals-connection-note"><span className="engine-pulse"/><span><b>{t.unavailable}</b><small>{t.unavailableText}</small></span></div>
      </section>
    </div>
  </div>;
}
