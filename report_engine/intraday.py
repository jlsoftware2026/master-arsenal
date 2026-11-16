"""Intraday snapshot report composer and PDF output contract."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer

from .charts import MarketChart
from .pdf import (
    data_table, key_value_table, paragraph, report_styles, section_heading,
    write_pdf_atomic,
)
from .qa import inspect_pdf_artifact

REQUIRED_SYMBOLS = ("BTCUSDT", "ETHUSDT")


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC string") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field} must include a UTC timezone")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


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
        "not_verified": "No verificado", "execution_time_local_default": "Hora local de ejecución",
        "explicit_local_cutoff": "Hora de corte local explícita",
        "explicit_utc_cutoff": "Hora de corte UTC explícita",
        "Binance public REST API": "API REST pública de Binance",
        "spot": "Spot", "usdm": "Futuros USDⓈ-M",
        "premarket": "Premercado", "regular": "Sesión regular",
        "postmarket": "Posmercado", "closed": "Mercado cerrado",
    }
    return labels.get(str(value), str(value) if value is not None else "No suministrado")


def _display(value: Any) -> str:
    if value is None:
        return "Datos insuficientes / no disponibles"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, dict):
        labels = {"lastPrice": "Último precio", "priceChangePercent": "Cambio porcentual", "highPrice": "Máximo 24 h", "lowPrice": "Mínimo 24 h", "volume": "Volumen base", "quoteVolume": "Volumen cotizado"}
        return "; ".join(f"{labels.get(k, k)}: {_display(v)}" for k, v in value.items())
    if isinstance(value, list):
        return f"{len(value)} elemento(s)"
    return str(value)


def _metric_rows(indicators: dict[str, Any]) -> list[list[str]]:
    keys = ("ema_20", "ema_50", "ema_200", "rsi_14", "macd", "atr_14",
            "bollinger_20", "volume_sma_20")
    labels = ("EMA 20", "EMA 50", "EMA 200", "RSI 14", "MACD", "ATR 14",
              "Bollinger 20", "SMA 20 del volumen")
    return [[label, _display(indicators.get(key))] for key, label in zip(keys, labels)]


def _validate_input(report: dict[str, Any]):
    if not isinstance(report, dict):
        raise ValueError("La entrada del informe debe ser un objeto")
    required = {
        "window_start_utc", "cutoff_utc", "generated_at_utc", "symbols",
        "report_timezone", "report_date_local", "requested_report_date_local", "cutoff_resolution", "window_start_local", "cutoff_local", "window_semantics", "is_partial",
    }
    missing = required - set(report)
    if missing:
        raise ValueError(f"Faltan campos obligatorios del informe: {sorted(missing)}")
    start = _utc(report["window_start_utc"], "window_start_utc")
    cutoff = _utc(report["cutoff_utc"], "cutoff_utc")
    generated = _utc(report["generated_at_utc"], "generated_at_utc")
    if report["report_timezone"] != "America/Santo_Domingo":
        raise ValueError("Report timezone must be America/Santo_Domingo")
    if report["window_semantics"] != "[start, cutoff)" or not isinstance(report["is_partial"], bool):
        raise ValueError("Report must declare half-open window semantics and a boolean partial-day status")
    try:
        local_start = datetime.fromisoformat(report["window_start_local"])
        local_cutoff = datetime.fromisoformat(report["cutoff_local"])
        report_date = datetime.fromisoformat(report["report_date_local"]).date()
    except (TypeError, ValueError) as exc:
        raise ValueError("Local report date and window timestamps must be valid ISO-8601 values") from exc
    if local_start.tzinfo is None or local_cutoff.tzinfo is None:
        raise ValueError("Local report window timestamps must include their UTC offsets")
    if local_start.astimezone(timezone.utc) != start or local_cutoff.astimezone(timezone.utc) != cutoff:
        raise ValueError("Local and UTC report window boundaries do not match")
    expected_local_start = start.astimezone(ZoneInfo("America/Santo_Domingo"))
    expected_local_cutoff = cutoff.astimezone(ZoneInfo("America/Santo_Domingo"))
    if (local_start.replace(tzinfo=None) != expected_local_start.replace(tzinfo=None)
            or local_start.utcoffset() != expected_local_start.utcoffset()
            or local_cutoff.replace(tzinfo=None) != expected_local_cutoff.replace(tzinfo=None)
            or local_cutoff.utcoffset() != expected_local_cutoff.utcoffset()):
        raise ValueError("Local timestamps do not match the IANA America/Santo_Domingo rules")
    if local_start.date() != report_date or local_start.time().isoformat() != "00:00:00":
        raise ValueError("Intraday report must begin at local midnight on report_date_local")
    if local_cutoff.date() != report_date or local_cutoff <= local_start:
        raise ValueError("cutoff_local must be later than local midnight on report_date_local")
    if report.get("is_partial") is not True:
        raise ValueError("Intraday snapshots must be marked as partial local-day windows")
    if report["requested_report_date_local"] != report["report_date_local"]:
        raise ValueError("Intraday requested and reporting local dates must match")
    if report["cutoff_resolution"] not in {
        "explicit_utc_cutoff", "explicit_local_cutoff", "execution_time_local_default"
    }:
        raise ValueError("Intraday report has an invalid cutoff-resolution method")
    if cutoff <= start:
        raise ValueError("cutoff_utc must be later than the report window start")
    if generated < cutoff:
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
        count = item.get("candle_count")
        if count is not None and (not isinstance(count, int) or count < 0):
            raise ValueError(f"{symbol} candle_count must be a non-negative integer")
        first = item.get("first_open_time_utc")
        last = item.get("last_close_time_utc")
        if count and (first is None or last is None):
            raise ValueError(f"{symbol} candle timestamps are required when candle_count is non-zero")
        if first is not None:
            first_open = _utc(first, f"{symbol}.first_open_time_utc")
            if first_open < start or first_open >= cutoff:
                raise ValueError(f"{symbol} first candle is outside the reporting window")
        if last is not None:
            last_close = _utc(last, f"{symbol}.last_close_time_utc")
            if last_close >= cutoff:
                raise ValueError(f"{symbol} includes a candle closing at or after the exclusive cutoff")
            if first is not None and last_close < _utc(first, f"{symbol}.first_open_time_utc"):
                raise ValueError(f"{symbol} last candle closes before its first candle opens")
        candles = item.get("candles")
        if candles is not None:
            if not isinstance(candles, list):
                raise ValueError(f"{symbol}.candles must be a list")
            if count is not None and len(candles) != count:
                raise ValueError(f"{symbol} candle_count does not match supplied candle evidence")
            previous_open = None
            for index, candle in enumerate(candles):
                if not isinstance(candle, dict):
                    raise ValueError(f"{symbol}.candles[{index}] must be an object")
                opened = _utc(candle.get("open_time"), f"{symbol}.candles[{index}].open_time")
                closed = _utc(candle.get("close_time"), f"{symbol}.candles[{index}].close_time")
                if opened < start or opened >= cutoff or closed >= cutoff or closed < opened:
                    raise ValueError(f"{symbol}.candles[{index}] falls outside the valid report window")
                if previous_open is not None and opened <= previous_open:
                    raise ValueError(f"{symbol} candle evidence must be strictly ordered and unique")
                previous_open = opened
    return start, cutoff, generated


def _us_market_rows(snapshot: Any) -> tuple[list[list[str]], list[str]]:
    if not isinstance(snapshot, dict):
        return [], []
    labels = {
        "indices": "Índices", "volatility": "Volatilidad", "futures": "Futuros",
        "rates": "Tasas", "dollar": "Dólar", "commodities": "Materias primas",
        "sectors": "Sectores",
    }
    rows, unavailable = [], []
    groups = snapshot.get("groups") or {}
    if not isinstance(groups, dict):
        return [], []
    for category, items in groups.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "ok":
                unavailable.append(str(item.get("symbol", "símbolo desconocido")))
                continue
            change = (
                f"{item['change_basis_points']:+.1f} pb"
                if item.get("unit") == "yield_percent" and item.get("change_basis_points") is not None
                else f"{item['change_percent']:+.2f}%"
                if item.get("change_percent") is not None else "N/D"
            )
            unit = item.get("unit")
            value = item["last_price"]
            if unit == "yield_percent":
                price_label = f"{value:.3f}%"
            elif unit == "USD_per_barrel":
                price_label = f"${value:.2f}/bbl"
            elif unit == "USD_per_troy_ounce":
                price_label = f"${value:.2f}/oz"
            elif unit == "ETF_USD":
                price_label = f"${value:.2f}"
            else:
                price_label = f"{value:.2f} pts"
            rows.append([
                labels.get(category, category),
                str(item.get("name", "Instrumento")),
                str(item.get("symbol", "N/D")),
                price_label,
                change,
                str(item.get("observed_at_et", "N/D")),
            ])
    return rows, unavailable


def _account_rows(snapshot: Any) -> tuple[list[list[str]], list[str]]:
    if not isinstance(snapshot, dict):
        return [], []
    labels = {
        "realized_pnl": "PnL realizado reportado", "commission": "Comisiones",
        "funding_fee": "Funding", "deposit": "Depósitos", "withdrawal": "Retiros",
        "internal_transfer": "Transferencias internas", "trade_spend": "Gasto de operaciones",
        "trade_receive": "Ingreso de operaciones", "interest": "Intereses/recompensas",
        "other": "Otros movimientos",
    }
    rows = []
    aggregates = snapshot.get("aggregates_by_event_and_asset") or {}
    if isinstance(aggregates, dict):
        for event, assets in aggregates.items():
            if not isinstance(assets, dict):
                continue
            for asset, amount in sorted(assets.items()):
                rows.append([labels.get(event, event), str(asset), str(amount)])
    assumptions = snapshot.get("assumptions") or []
    return rows, [str(item) for item in assumptions if item]


def _summary_flowables(value: Any, styles) -> list[Any]:
    if isinstance(value, list):
        return [paragraph(f"• {_display(item)}", styles["body"]) for item in value[:7]]
    return [paragraph(_display(value or "No se suministró un resumen ejecutivo."), styles["body"])]


def build_intraday_snapshot_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Build and validate an intraday PDF from already-acquired, structured evidence.

    This function does not fetch market data or invent analysis. Scenario, news, and
    macro sections are rendered only when supplied by the upstream report composer.
    """
    start, cutoff, generated = _validate_input(report)
    date_text = report["report_date_local"]
    time_text = datetime.fromisoformat(report["cutoff_local"]).strftime("%H-%M")
    destination = Path(output_directory) / f"snapshot-mercado_{date_text}_{time_text}.pdf"
    styles = report_styles()
    story = [
        Paragraph("Snapshot intradía del mercado", styles["title"]),
        Paragraph("Análisis del día calendario dominicano con fuentes y calidad de datos",
                  styles["subtitle"]),
        key_value_table([
            ("Ventana de análisis local", f"{report['window_start_local']} hasta {report['cutoff_local']} ({report['report_timezone']})"),
            ("Ventana de evidencia UTC", f"{_iso_utc(start)} hasta {_iso_utc(cutoff)} (hora de corte exclusiva)"),
            ("Límite de la última vela cerrada (UTC)", report.get("data_cutoff_utc", "No suministrado")),
            ("Se excluyó el intervalo final incompleto", _label((report.get("indicator_methodology") or {}).get("partial_final_interval_excluded", False))),
            ("Estado de la ventana", "DÍA LOCAL PARCIAL"),
            ("Fecha de solicitud local", report.get("requested_report_date_local", report.get("report_date_local"))),
            ("Resolución de la hora de corte", _label(report.get("cutoff_resolution"))),
            ("Análisis de la cuenta Binance", _label(report.get("binance_account_data_status", "unavailable"))),
            ("Cobertura del mercado bursátil estadounidense", _label(report.get("us_equity_market_data_status", "not_integrated"))),
            ("Generado en UTC", _iso_utc(generated)),
            ("Hora de corte ET", cutoff.astimezone(ZoneInfo("America/New_York")).isoformat()),
            ("Generado en hora local", generated.astimezone(ZoneInfo("America/Santo_Domingo")).isoformat()),
            ("Generado en ET", generated.astimezone(ZoneInfo("America/New_York")).isoformat()),
            ("Fuente principal", _label(report.get("source", "No especificado"))),
            ("Mercado", _label(report.get("market", "No especificado"))),
            ("Intervalo", report.get("interval", "No especificado")),
            ("Estado de los datos", _label(report.get("data_status", "No certificado de forma independiente"))),
            ("Estado de la sesión bursátil estadounidense", _label(report.get("us_equity_session_state", "not_available"))),
            ("Última sesión bursátil completada (ET)", (report.get("us_equity_calendar") or {}).get("last_completed_session_date", "No disponible")),
            ("Próxima sesión bursátil (ET)", (report.get("us_equity_calendar") or {}).get("next_session_date", "No disponible")),
            ("Apertura / cierre oficial (ET)", f"{(report.get('us_equity_calendar') or {}).get('session_open_et') or 'N/D'} / {(report.get('us_equity_calendar') or {}).get('session_close_et') or 'N/D'}"),
            ("Cierre anticipado", _label((report.get("us_equity_calendar") or {}).get("early_close", "not_available"))),
            ("Base de comparación", report.get("comparison_basis", "Ventana del día local; el período móvil de 24 horas es distinto")),
        ], styles),
        Spacer(1, 4 * mm),
        section_heading("Resumen ejecutivo", styles),
        *_summary_flowables(report.get("executive_summary"), styles),
    ]
    market_rows, unavailable_market_symbols = _us_market_rows(report.get("us_equity_market_data"))
    story.append(section_heading("Mercado bursátil estadounidense", styles))
    if market_rows:
        story.append(data_table(
            ["Grupo", "Instrumento", "Ticker", "Último", "Cambio", "Observado (ET)"],
            market_rows, styles, widths=[20*mm, 43*mm, 20*mm, 22*mm, 20*mm, 47*mm],
        ))
    else:
        story.append(paragraph("No se obtuvieron cotizaciones bursátiles verificables para este corte.", styles["body"]))
    if unavailable_market_symbols:
        story.append(paragraph("Símbolos no disponibles: " + ", ".join(unavailable_market_symbols), styles["small"]))
    story.append(paragraph(
        "Fuente: Yahoo Finance (endpoint público best-effort); las marcas de observación y URLs exactas se conservan "
        "en el manifiesto. Las cotizaciones pueden estar retrasadas y no son un feed de ejecución.",
        styles["small"],
    ))
    account_snapshot = report.get("binance_account_data") or {}
    account_rows, account_assumptions = _account_rows(account_snapshot)
    story.append(section_heading("Actividad de cuenta Binance — CSV local", styles))
    story.append(paragraph(
        f"Estado: {_label(account_snapshot.get('status', 'unavailable'))}; "
        f"archivos: {account_snapshot.get('file_count', 0)}; "
        f"eventos dentro de la ventana: {account_snapshot.get('events_in_window', 0)}; "
        f"filas leídas: {account_snapshot.get('rows_scanned', 0)}; "
        f"duplicados omitidos: {account_snapshot.get('duplicate_rows', 0)}.",
        styles["body"],
    ))
    if account_rows:
        story.append(data_table(
            ["Tipo de movimiento", "Activo", "Variación agregada"],
            account_rows, styles, widths=[70*mm, 30*mm, 50*mm],
        ))
    else:
        story.append(paragraph(
            "No hay movimientos de cuenta verificables en esta ventana. Coloca exportaciones CSV compatibles en data/account_exports.",
            styles["body"],
        ))
    if account_assumptions:
        story.append(paragraph("Advertencias de importación: " + "; ".join(account_assumptions), styles["small"]))
    story.append(paragraph(
        "El importador solo agrega movimientos de CSV. No calcula patrimonio total, PnL no realizado, costo base completo "
        "ni rentabilidad ajustada por flujos; esos cálculos requieren balances y registros completos.",
        styles["small"],
    ))

    for symbol in REQUIRED_SYMBOLS:
        item = report["symbols"][symbol]
        indicators = item.get("indicators") or {}
        story.extend([
            section_heading(symbol, styles),
            key_value_table([
                ("Velas", item.get("candle_count", "No suministrado")),
                ("Primera vela local", _local_time(item.get("first_open_time_utc"))),
                ("Primera vela UTC", item.get("first_open_time_utc", "No suministrado")),
                ("Cierre de la última vela (local)", _local_time(item.get("last_close_time_utc"))),
                ("Cierre de la última vela (UTC)", item.get("last_close_time_utc", "No suministrado")),
                ("Ticker de 24 horas", _display(item.get("ticker_24h"))),
                ("Rendimiento del día local", _display(item.get("performance"))),
                ("Datos de velas consultados en UTC", ((item.get("response_metadata", {}).get("candles") or item.get("response_metadata") or {}).get("retrieved_at_utc", "No suministrado"))),
            ], styles),
            Spacer(1, 2 * mm),
            data_table(["Indicador técnico", "Valor"], _metric_rows(indicators), styles,
                       widths=[45 * mm, 122 * mm]),
        ])
        issues = item.get("validation") or []
        story.append(Paragraph("Validación de datos: " + (
            f"Se reportaron {len(issues)} incidencias; consulte los detalles de origen." if issues
            else "No se suministraron incidencias de validación; su ausencia no demuestra que los datos en vivo estén completos."
        ), styles["small"]))
        if issues:
            issue_rows = [[str(x.get("code", "desconocido")), str(x.get("severity", "advertencia")),
                           str(x.get("message", ""))] for x in issues if isinstance(x, dict)]
            if issue_rows:
                story.append(data_table(["Incidencia", "Severidad", "Detalles"], issue_rows, styles,
                                        widths=[30 * mm, 25 * mm, 112 * mm]))
        candles = item.get("candles")
        if candles:
            labels = [datetime.fromisoformat(str(candle["open_time"]).replace("Z", "+00:00")).astimezone(ZoneInfo("America/Santo_Domingo")).strftime("%H:%M") for candle in candles]
            closes = [candle["close"] for candle in candles]
            volumes = [candle["volume"] for candle in candles]
            story.extend([
                section_heading("Gráficos de precio y volumen", styles),
                MarketChart(f"{symbol}: precio de cierre ({report.get('interval', 'intervalo')})",
                            closes, labels, kind="line"),
                Spacer(1, 2 * mm),
                MarketChart(f"{symbol}: volumen del activo base ({report.get('interval', 'intervalo')})",
                            volumes, labels, kind="bar"),
            ])
        story.append(Spacer(1, 3 * mm))

    for section_key, title in (
        ("derivatives_context", "Contexto de derivados"),
        ("macro_context", "Contexto macroeconómico"),
        ("news_context", "Noticias relevantes"),
        ("bullish_scenario", "Escenario alcista / largo"),
        ("bearish_scenario", "Escenario bajista / corto"),
        ("risk_factors", "Factores de riesgo e invalidación"),
        ("limitations", "Metodología y limitaciones"),
        ("methodology_limitations", "Notas metodológicas adicionales"),
    ):
        if section_key in report:
            story.extend([section_heading(title, styles),
                          paragraph(_display(report[section_key]), styles["body"])])

    for source_key, title in (("macro_sources", "Registro de fuentes macroeconómicas"),
                               ("news_sources", "Registro de fuentes de noticias de activos digitales")):
        source_items = report.get(source_key) or []
        rows = []
        for item in source_items:
            if isinstance(item, dict):
                rows.append([
                    str(item.get("title", "Sin título")),
                    str(item.get("publisher", "No suministrado")),
                    str(item.get("published_at_utc", "No suministrado")),
                    str(item.get("url", "URL no suministrada")),
                    str(item.get("summary") or item.get("relevance", "No se suministró resumen")),
                ])
        if rows:
            story.extend([
                section_heading(title, styles),
                data_table(["Titular / comunicado", "Editor", "Publicado en UTC", "URL de origen", "Resumen / relevancia"],
                           rows, styles, widths=[38 * mm, 20 * mm, 25 * mm, 42 * mm, 45 * mm]),
            ])

    context_sources = report.get("context_sources") or []
    context_rows = [[
        str(item.get("publisher", "Desconocido")),
        str(item.get("kind", "Desconocido")),
        _label(item.get("status", "not_verified")),
        str(item.get("retrieved_at_utc", "No suministrado")),
        str(item.get("matching_items", item.get("error", "No suministrado"))),
        str(item.get("feed_url", "URL no suministrada")),
    ] for item in context_sources if isinstance(item, dict)]
    if not context_rows:
        context_rows = [["No consultado", "No consultado", "No verificado", "N/A",
                         "No hay elementos; disponibilidad no verificada", "URL no disponible"]]
    story.extend([
        section_heading("Registro de consulta de fuentes macro/noticias", styles),
        data_table(["Editor", "Tipo", "Estado", "Consultado en UTC", "Elementos / error", "URL del feed"],
                   context_rows, styles, widths=[25*mm, 15*mm, 18*mm, 30*mm, 40*mm, 37*mm]),
    ])

    provenance = report.get("provenance") or []
    story.append(section_heading("Fuentes y notas de procedencia", styles))
    if provenance:
        rows = [[str(x.get("source", "No especificado")),
                 str(x.get("retrieved_at_utc", "No especificado")),
                 str(x.get("note", ""))] for x in provenance if isinstance(x, dict)]
        story.append(data_table(["Fuente", "Consultado en UTC", "Nota"], rows, styles,
                                widths=[42 * mm, 45 * mm, 80 * mm]))
    else:
        story.append(paragraph(
            "No se suministró un manifiesto de procedencia independiente. Los valores anteriores conservan únicamente los metadatos presentes en la entrada del informe.",
            styles["body"]))
    story.append(Spacer(1, 4 * mm))
    story.append(paragraph(
        "Aviso: Este documento es un análisis informativo del mercado, no asesoramiento de inversión. "
        "Los escenarios son condicionales e inciertos; no garantizan resultados.",
        styles["small"]))
    artifact = write_pdf_atomic(
        destination, story, f"MASTER ARSENAL - Snapshot intradía {date_text}"
    )
    try:
        inspect_pdf_artifact(artifact)
    except Exception:
        artifact.unlink(missing_ok=True)
        raise
    return artifact
