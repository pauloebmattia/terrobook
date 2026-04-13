"""Funções de serialização/deserialização para os modelos do Terrobook Portal.

Converte dataclasses para dict (JSON-serializável) e reconstrói a partir de dict.
- datetime → ISO 8601 string (com timezone UTC)
- Enum → .value (string)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.models import (
    Categoria,
    CollectionResult,
    Genero,
    ItemCurado,
    Noticia,
    PipelineError,
    ResultadoCuradoria,
    SourceError,
    StatusCuradoria,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt_to_iso(dt: datetime | None) -> str | None:
    """Converte datetime para string ISO 8601 com sufixo Z (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _iso_to_dt(value: str | None) -> datetime | None:
    """Reconstrói datetime a partir de string ISO 8601, garantindo timezone UTC."""
    if value is None:
        return None
    # Normaliza o sufixo Z para +00:00 que o fromisoformat aceita (Python 3.11+)
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Noticia
# ---------------------------------------------------------------------------

def noticia_to_dict(n: Noticia) -> dict[str, Any]:
    return {
        "url": n.url,
        "titulo": n.titulo,
        "data_publicacao": _dt_to_iso(n.data_publicacao),
        "fonte_id": n.fonte_id,
        "texto_resumido": n.texto_resumido,
        "coletado_em": _dt_to_iso(n.coletado_em),
        "raw_html": n.raw_html,
    }


def noticia_from_dict(d: dict[str, Any]) -> Noticia:
    return Noticia(
        url=d["url"],
        titulo=d["titulo"],
        data_publicacao=_iso_to_dt(d["data_publicacao"]),
        fonte_id=d["fonte_id"],
        texto_resumido=d["texto_resumido"],
        coletado_em=_iso_to_dt(d["coletado_em"]),
        raw_html=d.get("raw_html"),
    )


# ---------------------------------------------------------------------------
# ItemCurado
# ---------------------------------------------------------------------------

def item_curado_to_dict(item: ItemCurado) -> dict[str, Any]:
    return {
        "id": item.id,
        "noticia": noticia_to_dict(item.noticia),
        "categoria": item.categoria.value,
        "generos": [g.value for g in item.generos],
        "score": item.score,
        "aprovado_em": _dt_to_iso(item.aprovado_em),
        "aprovado_por": item.aprovado_por,
        "titulo_original": item.titulo_original,
        "autor": item.autor,
        "editora": item.editora,
        "data_prevista": item.data_prevista,
        "sinopse": item.sinopse,
        "itens_relacionados": item.itens_relacionados,
    }


def item_curado_from_dict(d: dict[str, Any]) -> ItemCurado:
    return ItemCurado(
        id=d["id"],
        noticia=noticia_from_dict(d["noticia"]),
        categoria=Categoria(d["categoria"]),
        generos=[Genero(g) for g in d.get("generos", [])],
        score=d["score"],
        aprovado_em=_iso_to_dt(d["aprovado_em"]),
        aprovado_por=d["aprovado_por"],
        titulo_original=d.get("titulo_original"),
        autor=d.get("autor"),
        editora=d.get("editora"),
        data_prevista=d.get("data_prevista"),
        sinopse=d.get("sinopse"),
        itens_relacionados=d.get("itens_relacionados", []),
    )


# ---------------------------------------------------------------------------
# ResultadoCuradoria
# ---------------------------------------------------------------------------

def resultado_curadoria_to_dict(r: ResultadoCuradoria) -> dict[str, Any]:
    return {
        "noticia": noticia_to_dict(r.noticia),
        "status": r.status.value,
        "score": r.score,
        "categoria": r.categoria.value if r.categoria else None,
        "motivo_rejeicao": r.motivo_rejeicao,
    }


def resultado_curadoria_from_dict(d: dict[str, Any]) -> ResultadoCuradoria:
    return ResultadoCuradoria(
        noticia=noticia_from_dict(d["noticia"]),
        status=StatusCuradoria(d["status"]),
        score=d["score"],
        categoria=Categoria(d["categoria"]) if d.get("categoria") else None,
        motivo_rejeicao=d.get("motivo_rejeicao"),
    )


# ---------------------------------------------------------------------------
# SourceError
# ---------------------------------------------------------------------------

def source_error_to_dict(e: SourceError) -> dict[str, Any]:
    return {
        "fonte_id": e.fonte_id,
        "url": e.url,
        "etapa": e.etapa,
        "mensagem": e.mensagem,
        "timestamp": _dt_to_iso(e.timestamp),
    }


def source_error_from_dict(d: dict[str, Any]) -> SourceError:
    return SourceError(
        fonte_id=d["fonte_id"],
        url=d["url"],
        etapa=d["etapa"],
        mensagem=d["mensagem"],
        timestamp=_iso_to_dt(d["timestamp"]),
    )


# ---------------------------------------------------------------------------
# PipelineError
# ---------------------------------------------------------------------------

def pipeline_error_to_dict(e: PipelineError) -> dict[str, Any]:
    return {
        "etapa": e.etapa,
        "mensagem": e.mensagem,
        "timestamp": _dt_to_iso(e.timestamp),
        "fonte_id": e.fonte_id,
        "traceback": e.traceback,
    }


def pipeline_error_from_dict(d: dict[str, Any]) -> PipelineError:
    return PipelineError(
        etapa=d["etapa"],
        mensagem=d["mensagem"],
        timestamp=_iso_to_dt(d["timestamp"]),
        fonte_id=d.get("fonte_id"),
        traceback=d.get("traceback"),
    )


# ---------------------------------------------------------------------------
# CollectionResult
# ---------------------------------------------------------------------------

def collection_result_to_dict(r: CollectionResult) -> dict[str, Any]:
    return {
        "collected": [noticia_to_dict(n) for n in r.collected],
        "skipped_duplicates": r.skipped_duplicates,
        "errors": [source_error_to_dict(e) for e in r.errors],
    }
