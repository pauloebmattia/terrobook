"""Coleta de notícias via scraping HTML usando requests + BeautifulSoup."""

from __future__ import annotations

import html as html_module
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src.models import FonteConfig, Noticia

_TIMEOUT = 30
_MAX_RESUMO = 500
_TAG_RE = re.compile(r"<[^>]+>")
_USER_AGENT = (
    "Mozilla/5.0 (compatible; TerrobookPortalBot/1.0; "
    "+https://github.com/terrobook-portal)"
)

_REQUIRED_SELECTORS = {"container", "titulo", "url", "resumo"}


def _strip_html(text: str) -> str:
    """Remove tags HTML e decodifica entidades HTML."""
    sem_tags = _TAG_RE.sub(" ", text)
    decodificado = html_module.unescape(sem_tags)
    return " ".join(decodificado.split())


def _validar_seletores(source: FonteConfig) -> dict:
    """Valida e retorna os seletores da fonte.

    Raises:
        RuntimeError: Se seletores estiverem ausentes ou incompletos.
    """
    if not source.seletores:
        raise RuntimeError(
            f"Fonte '{source.nome}' ({source.id}) não possui seletores configurados. "
            f"Campos obrigatórios: {', '.join(sorted(_REQUIRED_SELECTORS))}"
        )

    faltando = _REQUIRED_SELECTORS - source.seletores.keys()
    if faltando:
        raise RuntimeError(
            f"Seletores inválidos para a fonte '{source.nome}' ({source.id}). "
            f"Campos ausentes: {', '.join(sorted(faltando))}"
        )

    return source.seletores


def fetch_html(source: FonteConfig) -> list[Noticia]:
    """Coleta notícias via scraping HTML com seletores CSS configuráveis.

    Args:
        source: Configuração da fonte com URL e seletores CSS.
            Os seletores devem conter as chaves:
            - ``container``: seletor do elemento que agrupa cada notícia
            - ``titulo``: seletor do título dentro do container
            - ``url``: seletor do link (atributo ``href``) dentro do container
            - ``resumo``: seletor do resumo/sinopse dentro do container

    Returns:
        Lista de :class:`~src.models.Noticia` extraídas da página.

    Raises:
        RuntimeError: Se a requisição HTTP falhar (status >= 400 ou timeout)
            ou se os seletores estiverem ausentes/incompletos.
    """
    seletores = _validar_seletores(source)

    headers = {"User-Agent": _USER_AGENT}

    try:
        response = requests.get(source.url, headers=headers, timeout=_TIMEOUT)
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Timeout ao acessar '{source.nome}' ({source.url}): "
            f"limite de {_TIMEOUT}s excedido"
        )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Falha de rede ao acessar '{source.nome}' ({source.url}): {exc}"
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Falha ao acessar '{source.nome}' ({source.url}): "
            f"HTTP {response.status_code}"
        )

    soup = BeautifulSoup(response.text, "html.parser")
    containers = soup.select(seletores["container"])

    if not containers:
        raise RuntimeError(
            f"Seletor de container '{seletores['container']}' não encontrou elementos "
            f"em '{source.nome}' ({source.url})"
        )

    coletado_em = datetime.now(tz=timezone.utc)
    noticias: list[Noticia] = []

    for container in containers:
        # Extrai título
        el_titulo = container.select_one(seletores["titulo"])
        if not el_titulo:
            continue
        titulo = _strip_html(el_titulo.get_text()).strip()
        if not titulo:
            continue

        # Extrai URL
        el_url = container.select_one(seletores["url"])
        if not el_url:
            continue
        url = el_url.get("href", "").strip()
        if not url:
            # Tenta o texto como fallback (caso o seletor aponte para o próprio <a>)
            url = el_url.get_text().strip()
        if not url:
            continue

        # Normaliza URL relativa
        if url.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(source.url)
            url = f"{parsed.scheme}://{parsed.netloc}{url}"

        # Extrai resumo
        el_resumo = container.select_one(seletores["resumo"])
        texto_resumido = ""
        if el_resumo:
            texto_resumido = _strip_html(el_resumo.get_text()).strip()
        texto_resumido = texto_resumido[:_MAX_RESUMO]

        # data_publicacao: usa utcnow() pois HTML raramente expõe data estruturada
        data_publicacao = datetime.now(tz=timezone.utc)

        noticias.append(
            Noticia(
                url=url,
                titulo=titulo,
                data_publicacao=data_publicacao,
                fonte_id=source.id,
                texto_resumido=texto_resumido,
                coletado_em=coletado_em,
                raw_html=str(container),
            )
        )

    return noticias
