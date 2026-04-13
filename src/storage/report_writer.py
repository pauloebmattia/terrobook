"""report_writer — geração de relatórios de ciclo e de erros."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.models import CollectionResult, PipelineError, ResultadoCuradoria, StatusCuradoria
from src.storage.serializer import (
    pipeline_error_to_dict,
    resultado_curadoria_to_dict,
)


def write_cycle_report(
    result: CollectionResult,
    curadoria: list[ResultadoCuradoria],
    data: date,
    reports_dir: Path,
) -> dict[str, Any]:
    """Gera os dois arquivos de relatório do ciclo e retorna o sumário.

    Arquivos gerados:
    - reports/report_YYYY-MM-DD.json  — sumário do ciclo
    - reports/pending_review_YYYY-MM-DD.json — itens PENDENTE_REVISAO
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    date_str = data.isoformat()

    aprovados = [r for r in curadoria if r.status == StatusCuradoria.APROVADO]
    pendentes = [r for r in curadoria if r.status == StatusCuradoria.PENDENTE_REVISAO]
    descartados = [r for r in curadoria if r.status == StatusCuradoria.DESCARTADO]

    summary: dict[str, Any] = {
        "data": date_str,
        "total_coletado": len(result.collected),
        "aprovados": len(aprovados),
        "pendentes": len(pendentes),
        "descartados": len(descartados),
        "erros": len(result.errors),
    }

    # Relatório principal
    report_path = reports_dir / f"report_{date_str}.json"
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Lista de pendentes
    pending_payload: list[dict[str, Any]] = [
        resultado_curadoria_to_dict(r) for r in pendentes
    ]
    pending_path = reports_dir / f"pending_review_{date_str}.json"
    pending_path.write_text(
        json.dumps(pending_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return summary


def write_error_report(
    errors: list[PipelineError],
    data: date,
    reports_dir: Path,
) -> Path:
    """Gera reports/error_report_YYYY-MM-DD.json com a lista de PipelineError.

    Retorna o Path do arquivo gerado.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    date_str = data.isoformat()
    path = reports_dir / f"error_report_{date_str}.json"
    payload: list[dict[str, Any]] = [pipeline_error_to_dict(e) for e in errors]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
