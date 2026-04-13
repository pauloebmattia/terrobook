"""Coleta de notícias a partir de feeds RSS/Atom usando feedparser."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from src.models import FonteConfig, Noticia

_MAX_RESUMO = 500
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove tags HTML e decodifica entidades HTML."""
    sem_tags = _TAG_RE.sub(" ", text)
    decodificado = html.unescape(sem_tags)
    return " ".join(decodificado.split())


def _extrair_resumo(entry: feedparser.FeedParserDict) -> str:
    """Extrai e limpa o texto resumido de uma entrada do feed."""
    texto = ""
    if hasattr(entry, "summary") and entry.summary:
        texto = entry.summary
    elif hasattr(entry, "content") and entry.content:
        texto = entry.content[0].get("value", "")
    elif hasattr(entry, "description") and entry.description:
        texto = entry.description

    limpo = _strip_html(texto)
    return limpo[:_MAX_RESUMO]


def _extrair_data(entry: feedparser.FeedParserDict) -> datetime:
    """Extrai a data de publicação da entrada; usa utcnow() se indisponível."""
    # feedparser popula published_parsed ou updated_parsed como time.struct_time
    for campo in ("published_parsed", "updated_parsed"):
        valor = getattr(entry, campo, None)
        if valor is not None:
            try:
                return datetime(*valor[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass

    # Tenta parsear a string bruta
    for campo in ("published", "updated"):
        valor = getattr(entry, campo, None)
        if valor:
            try:
                return parsedate_to_datetime(valor)
            except Exception:
                pass

    return datetime.now(tz=timezone.utc)


def fetch_rss(source: FonteConfig) -> list[Noticia]:
    """Coleta notícias de um feed RSS/Atom.

    Args:
        source: Configuração da fonte com URL do feed.

    Returns:
        Lista de Noticia extraídas do feed.

    Raises:
        RuntimeError: Se o feed estiver inacessível ou retornar erro HTTP.
    """
    feed = feedparser.parse(source.url)

    # feedparser não lança exceção em falhas de rede; verifica bozo e status
    if feed.get("bozo") and not feed.entries:
        exc = feed.get("bozo_exception")
        mensagem = str(exc) if exc else "Feed inacessível ou malformado"
        raise RuntimeError(
            f"Falha ao acessar o feed '{source.nome}' ({source.url}): {mensagem}"
        )

    status = feed.get("status")
    if status is not None and status >= 400:
        raise RuntimeError(
            f"Falha ao acessar o feed '{source.nome}' ({source.url}): HTTP {status}"
        )

    coletado_em = datetime.now(tz=timezone.utc)
    noticias: list[Noticia] = []

    for entry in feed.entries:
        url = getattr(entry, "link", None) or getattr(entry, "id", None)
        if not url:
            continue

        titulo = getattr(entry, "title", None) or ""
        titulo = _strip_html(titulo).strip()
        if not titulo:
            continue

        data_publicacao = _extrair_data(entry)
        texto_resumido = _extrair_resumo(entry)

        noticias.append(
            Noticia(
                url=url,
                titulo=titulo,
                data_publicacao=data_publicacao,
                fonte_id=source.id,
                texto_resumido=texto_resumido,
                coletado_em=coletado_em,
            )
        )

    return noticias
