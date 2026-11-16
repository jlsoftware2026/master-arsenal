"""PDF composers for completed UTC market-day opening and closing reports."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from .charts import MarketChart
from .pdf import data_table, key_value_table, paragraph, report_styles, section_heading, write_pdf_atomic
from .qa import inspect_pdf_artifact

REQUIRED_SYMBOLS = ("BTCUSDT", "ETHUSDT")


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must include a UTC timezone")
    return parsed.astimezone(timezone.utc)


def _local_time(value: Any) -> str:
    if not isinstance(value, str):
        return "No suministrado"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return "Marca de tiempo no válida"
        return parsed.astimezone(ZoneInfo("America/Santo_Domingo")).isoformat()
    except ValueError:
        return "Marca de tiempo no válida"


def _label(value: Any) -> str:
    if isinstance(value, bool):
        return "Sí" if value else "No"
    labels = {
        "unavailable": "No disponible", "not_integrated": "No integrado",
        "not_available": "No disponible", "not_implemented": "No implementado",
        "not_applicable": "No aplica", "not_automated": "No automatizado",
        "complete": "Completo", "partial": "Parcial", "ok": "Correcto",
        "not_verified": "No verificado", "previous_local_calendar_day": "Día calendario local anterior",
        "explicit_local_cutoff": "Hora de corte local explícita",
        "execution_time_local_default": "Hora local de ejecución",
        "completed_historical_local_day": "Día local histórico completado",
        "Binance public REST API": "API REST pública de Binance",
        "spot": "Spot", "usdm": "Futuros USDⓈ-M",
    }
    return labels.get(str(value), str(value) if value is not None else "No suministrado")


def _text(value: Any) -> str:
    if value is None:
        return "No suministrado"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(_text(item) for item in value) if value else "Ninguno suministrado"
    return str(value)


def _validate(report: dict[str, Any]):
    if not isinstance(report, dict):
        raise ValueError("Report input must be an object")
    required = {"session_start_utc", "session_end_utc", "generated_at_utc", "symbols",
                "report_timezone", "report_date_local", "requested_report_date_local", "cutoff_resolution", "window_start_local", "cutoff_local", "window_semantics", "is_partial"}
    missing = required - set(report)
    if missing:
        raise ValueError(f"Missing required report fields: {sorted(missing)}")
    start = _utc(report["session_start_utc"], "session_start_utc")
    end = _utc(report["session_end_utc"], "session_end_utc")
    generated = _utc(report["generated_at_utc"], "generated_at_utc")
    if report["report_timezone"] != "America/Santo_Domingo":
        raise ValueError("Report timezone must be America/Santo_Domingo")
    if report["window_semantics"] != "[start, cutoff)" or not isinstance(report["is_partial"], bool):
        raise ValueError("Report must declare half-open window semantics and a boolean partial-day status")
    try:
        requested_date = date.fromisoformat(report["requested_report_date_local"])
    except (TypeError, ValueError) as exc:
        raise ValueError("requested_report_date_local must be YYYY-MM-DD") from exc
    if requested_date.isoformat() != report["requested_report_date_local"]:
        raise ValueError("requested_report_date_local must be canonical YYYY-MM-DD")
    try:
        local_start = datetime.fromisoformat(report["window_start_local"])
        local_end = datetime.fromisoformat(report["cutoff_local"])
        report_date = datetime.fromisoformat(report["report_date_local"]).date()
    except (TypeError, ValueError) as exc:
        raise ValueError("Local report date and window timestamps must be valid ISO-8601 values") from exc
    if local_start.tzinfo is None or local_end.tzinfo is None:
        raise ValueError("Local report window timestamps must include their UTC offsets")
    if local_start.astimezone(timezone.utc) != start or local_end.astimezone(timezone.utc) != end:
        raise ValueError("Local and UTC report window boundaries do not match")
    expected_local_start = start.astimezone(ZoneInfo("America/Santo_Domingo"))
    expected_local_end = end.astimezone(ZoneInfo("America/Santo_Domingo"))
    if (local_start.replace(tzinfo=None) != expected_local_start.replace(tzinfo=None)
            or local_start.utcoffset() != expected_local_start.utcoffset()
            or local_end.replace(tzinfo=None) != expected_local_end.replace(tzinfo=None)
            or local_end.utcoffset() != expected_local_end.utcoffset()):
        raise ValueError("Local timestamps do not match the IANA America/Santo_Domingo rules")
    if local_start.date() != report_date or local_start.time().isoformat() != "00:00:00":
        raise ValueError("Local report start must be midnight on report_date_local")
    if report.get("is_partial") is True:
        if local_end.date() != report_date:
            raise ValueError("Partial local report cutoff must remain on report_date_local")
    elif local_end.date() != report_date + timedelta(days=1) or local_end.time().isoformat() != "00:00:00":
        raise ValueError("Completed local report must end at the next local midnight")
    if end <= start:
        raise ValueError("Report window cutoff must be later than its start")
    if generated < end:
        raise ValueError("generated_at_utc cannot precede the report cutoff")
    symbols = report["symbols"]
    if not isinstance(symbols, dict):
        raise ValueError("symbols must be an object keyed by symbol")
    absent = [symbol for symbol in REQUIRED_SYMBOLS if symbol not in symbols]
    if absent:
        raise ValueError(f"Mandatory symbols missing: {', '.join(absent)}")
    for symbol in REQUIRED_SYMBOLS:
        item = symbols[symbol]
        if not isinstance(item, dict):
            raise ValueError(f"{symbol} report data must be an object")
        candles = item.get("candles", [])
        if not isinstance(candles, list):
            raise ValueError(f"{symbol}.candles must be a list")
        previous = None
        for index, candle in enumerate(candles):
            if not isinstance(candle, dict):
                raise ValueError(f"{symbol}.candles[{index}] must be an object")
            opened = _utc(candle.get("open_time"), f"{symbol}.candles[{index}].open_time")
            closed = _utc(candle.get("close_time"), f"{symbol}.candles[{index}].close_time")
            if opened < start or opened >= end or closed < opened or closed >= end:
                raise ValueError(f"{symbol}.candles[{index}] is outside the report window")
            if previous is not None and opened <= previous:
                raise ValueError(f"{symbol} candles must be strictly ordered and unique")
            previous = opened
    return start, end, generated


def _indicator_rows(indicators: Any) -> list[list[str]]:
    indicators = indicators if isinstance(indicators, dict) else {}
    definitions = (
        ("ema_20", "EMA 20"), ("ema_50", "EMA 50"), ("ema_200", "EMA 200"),
        ("rsi_14", "RSI 14"), ("macd", "MACD"), ("atr_14", "ATR 14"),
        ("bollinger_20", "Bollinger 20"), ("volume_sma_20", "SMA 20 del volumen"),
    )
    return [[label, _text(indicators.get(key))] for key, label in definitions]


def _ticker_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return "No suministrado"
    if value.get("status") != "ok":
        return f"No disponible: {value.get('error', 'Sin detalle del endpoint')}"
    data = value.get("data")
    if not isinstance(data, dict):
        return "Datos del ticker no disponibles"
    keys = ("lastPrice", "priceChangePercent", "highPrice", "lowPrice", "volume", "quoteVolume")
    return "; ".join(f"{key}: {data[key]}" for key in keys if key in data) or "No se suministraron los campos seleccionados del ticker"


def _derivatives_summary(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "No suministrado"
    rows = []
    display_keys = ("lastFundingRate", "markPrice", "indexPrice", "openInterest",
                    "sumOpenInterest", "longShortRatio", "basis")
    for name, result in value.items():
        if not isinstance(result, dict):
            rows.append(f"{name}: unavailable")
            continue
        status = result.get("status", "no verificada")
        data = result.get("data")
        if isinstance(data, list):
            data = data[-1] if data else None
        selected = []
        if isinstance(data, dict):
            selected = [f"{key}={data[key]}" for key in display_keys if key in data]
        suffix = ", ".join(selected) if selected else "último valor no disponible"
        rows.append(f"{name}: {status} ({suffix})")
    return "; ".join(rows)

def _source_rows(items: Any) -> list[list[str]]:
    if not isinstance(items, list):
        return []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append([
            _text(item.get("title", "Fuente sin título")),
            _text(item.get("publisher", item.get("source", "No suministrado"))),
            _text(item.get("published_at_utc", "No suministrado")),
            _text(item.get("url", "URL no suministrada")),
            _text(item.get("summary") or item.get("relevance", "No se suministró resumen ni nota de relevancia")),
        ])
    return rows


def _build_session_pdf(report: dict[str, Any], output_directory: Path | str, kind: str) -> Path:
    start, end, generated = _validate(report)
    requested_date = date.fromisoformat(report["requested_report_date_local"])
    if kind not in {"opening", "closing"}:
        raise ValueError("kind must be 'opening' or 'closing'")
    if kind == "opening":
        if report.get("is_partial") is True:
            raise ValueError("Opening reports must use the previous completed local calendar day")
        if report["report_date_local"] != (requested_date - timedelta(days=1)).isoformat():
            raise ValueError("Opening report must use the previous Dominican local calendar day")
        if report["cutoff_resolution"] != "previous_local_calendar_day":
            raise ValueError("Opening report must declare previous-local-day cutoff resolution")
    else:
        if report["report_date_local"] != requested_date.isoformat():
            raise ValueError("Closing report date must match requested_report_date_local")
        if report["cutoff_resolution"] not in {
            "explicit_local_cutoff", "execution_time_local_default", "completed_historical_local_day"
        }:
            raise ValueError("Closing report has an invalid cutoff-resolution method")
    date_text = report["report_date_local"]
    filename = ("apertura-mercado_" if kind == "opening" else "cierre-mercado_") + date_text + ".pdf"
    title = "Informe de apertura del mercado" if kind == "opening" else "Informe de cierre del mercado"
    styles = report_styles()
    story = [
        Paragraph(title, styles["title"]),
        Paragraph("Análisis del día calendario local America/Santo_Domingo para BTCUSDT y ETHUSDT", styles["subtitle"]),
        key_value_table([
            ("Ventana de análisis local", f"{report['window_start_local']} to {report['cutoff_local']} ({report['report_timezone']})"),
            ("Ventana de evidencia UTC", f"{start.isoformat().replace('+00:00', 'Z')} to {end.isoformat().replace('+00:00', 'Z')} (cutoff exclusive)"),
            ("Límite de la última vela cerrada (UTC)", report.get("data_cutoff_utc", "No suministrado")),
            ("Se excluyó el intervalo final incompleto", _label((report.get("indicator_methodology") or {}).get("partial_final_interval_excluded", False))),
            ("Estado de la ventana", "DÍA LOCAL PARCIAL" if report.get("is_partial") else "DÍA LOCAL COMPLETO"),
            ("Fecha de solicitud local", report.get("requested_report_date_local", report.get("report_date_local"))),
            ("Resolución de la hora de corte", _label(report.get("cutoff_resolution"))),
            ("Generado en UTC", generated.isoformat().replace("+00:00", "Z")),
            ("Fuente principal", _label(report.get("source", "No especificado"))),
            ("Mercado", _label(report.get("market", "No especificado"))),
            ("Intervalo", report.get("interval", "Not specified")),
            ("Estado de los datos", _label(report.get("data_status", "No certificado de forma independiente"))),
            ("Análisis de la cuenta Binance", _label(report.get("binance_account_data_status", "unavailable"))),
            ("Cobertura del mercado bursátil estadounidense", _label(report.get("us_equity_market_data_status", "not_integrated"))),
            ("Horario de la sesión bursátil estadounidense", _label(report.get("us_equity_session_state", "not_available"))),
            ("Comparación del pronóstico de apertura", _label(report.get("opening_forecast_scorecard_status", "not_available"))),
            ("Horario de activación", _label(report.get("activation_timing_status", "not_automated"))),
            ("Perspectiva del informe", "Día calendario dominicano anterior a la próxima sesión estadounidense" if kind == "opening"
             else ("Acumulado del día calendario dominicano hasta la hora de corte indicada" if report.get("is_partial")
                   else "Día calendario dominicano completado")),
        ], styles),
        Spacer(1, 4 * mm),
        section_heading("Resumen ejecutivo", styles),
        paragraph(report.get("executive_summary", "No se suministró un resumen ejecutivo."), styles["body"]),
    ]
    for symbol in REQUIRED_SYMBOLS:
        item = report["symbols"][symbol]
        story.extend([
            section_heading(symbol, styles),
            key_value_table([
                ("Velas de la sesión", item.get("candle_count", len(item.get("candles", [])))),
                ("Primera apertura local", _local_time(item.get("first_open_time_utc"))),
                ("Primera apertura UTC", item.get("first_open_time_utc", "No suministrado")),
                ("Último cierre local", _local_time(item.get("last_close_time_utc"))),
                ("Último cierre UTC", item.get("last_close_time_utc", "No suministrado")),
                ("Variación del precio", _text(item.get("performance"))),
                ("Ticker de 24 horas", _ticker_summary(item.get("ticker_24h"))),
                ("Velas de calentamiento de indicadores", (item.get("indicator_history") or {}).get("candle_count", "No suministrado")),
                ("Paginación de velas", "completa" if (item.get("pagination") or {}).get("complete") else "no verificada"),
                ("Contexto de derivados", _derivatives_summary(item.get("derivatives"))),
            ], styles),
            data_table(["Indicador técnico", "Valor"], _indicator_rows(item.get("indicators")), styles,
                       widths=[45*mm, 120*mm]),
        ])
        issues = item.get("validation") or []
        if issues:
            issue_rows = [[
                str(issue.get("code", "desconocido")),
                str(issue.get("severity", "advertencia")),
                str(issue.get("message", "")),
            ] for issue in issues if isinstance(issue, dict)]
            if issue_rows:
                story.extend([
                    section_heading(f"{symbol}: problemas de validación de datos", styles),
                    data_table(["Incidencia", "Severidad", "Detalles"], issue_rows, styles,
                               widths=[28*mm, 22*mm, 115*mm]),
                ])
        else:
            story.append(paragraph(
                f"{symbol}: Validación de datos: no se suministraron incidencias; esto no demuestra que los datos en vivo estén completos.",
                styles["small"],
            ))
        candles = item.get("candles") or []
        if candles:
            labels = [datetime.fromisoformat(str(c.get("open_time", "")).replace("Z", "+00:00")).astimezone(ZoneInfo("America/Santo_Domingo")).strftime("%H:%M") for c in candles]
            closes = [c["close"] for c in candles]
            volumes = [c["volume"] for c in candles]
            story.extend([
                MarketChart(f"{symbol}: precio de cierre — solo sesión", closes, labels, "line"),
                Spacer(1, 2 * mm),
                MarketChart(f"{symbol}: volumen del activo base — solo sesión", volumes, labels, "bar"),
            ])
    for heading, key in (
        ("Estructura del mercado e interpretación técnica", "technical_analysis"),
        ("Escenario alcista / largo", "bullish_scenario"),
        ("Escenario bajista / corto", "bearish_scenario"),
        ("Supuestos y niveles de invalidación", "assumptions_and_invalidation"),
        ("Evaluación de riesgos", "risks"),
        ("Contexto macroeconómico", "macro_context"),
        ("Noticias relevantes del mercado", "news"),
        ("Limitaciones de los datos", "limitations"),
        ("Metodología", "methodology"),
    ):
        value = report.get(key)
        if value is None:
            continue
        story.extend([section_heading(heading, styles), paragraph(_text(value), styles["body"])])
    for heading, key in (("Registro de fuentes macroeconómicas", "macro_sources"),
                         ("Registro de fuentes de noticias", "news_sources")):
        rows = _source_rows(report.get(key))
        if rows:
            story.extend([
                section_heading(heading, styles),
                data_table(["Título", "Editor", "Publicado en UTC", "URL de origen", "Relevancia"],
                           rows, styles, widths=[32*mm, 22*mm, 24*mm, 42*mm, 45*mm]),
            ])
    context_sources = report.get("context_sources") or []
    if context_sources:
        context_rows = [[
            str(item.get("publisher", "Unknown")),
            str(item.get("kind", "Unknown")),
            str(item.get("status", "no verificada")),
            str(item.get("retrieved_at_utc", "No suministrado")),
            str(item.get("matching_items", item.get("error", "No suministrado"))),
            str(item.get("feed_url", "URL no suministrada")),
        ] for item in context_sources if isinstance(item, dict)]
        if context_rows:
            story.extend([
                section_heading("Registro de consulta de fuentes macro/noticias", styles),
                data_table(["Editor", "Tipo", "Estado", "Consultado en UTC", "Elementos / error", "URL del feed"],
                           context_rows, styles, widths=[25*mm, 15*mm, 18*mm, 30*mm, 40*mm, 37*mm]),
            ])
    provenance = report.get("provenance")
    if provenance:
        story.extend([section_heading("Procedencia de los datos", styles), paragraph(_text(provenance), styles["body"])])
    story.extend([
        section_heading("Aviso importante", styles),
        paragraph(
            "Este informe es informativo y no constituye asesoramiento de inversión. Los escenarios de mercado son interpretaciones condicionales e inciertas, "
            "no garantías. Verifique de forma independiente los datos de origen y los riesgos.",
            styles["small"],
        ),
    ])
    destination = Path(output_directory) / filename
    written = write_pdf_atomic(destination, story, title)
    try:
        inspect_pdf_artifact(written)
    except Exception:
        written.unlink(missing_ok=True)
        raise
    return written


def build_opening_report_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Build a PDF opening report for a previously completed UTC market day."""
    return _build_session_pdf(report, output_directory, "opening")


def build_closing_report_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Build a PDF closing report for a just-completed UTC market day."""
    return _build_session_pdf(report, output_directory, "closing")
