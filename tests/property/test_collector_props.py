"""Testes de propriedade para o Coletor do Terrobook Portal.

Propriedades cobertas:
- Property 1: Coleta preserva campos obrigatórios
- Property 2: Resiliência a fontes indisponíveis
- Property 3: Deduplicação por URL
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.collector.collector import Coletor
from src.collector.seen_urls import SeenUrls
from src.models import CollectionResult, FonteConfig, Noticia, TipoFonte


# ---------------------------------------------------------------------------
# Estratégias compartilhadas
# ---------------------------------------------------------------------------

urls = st.from_regex(r"https://example\.com/[a-z0-9\-]{5,20}", fullmatch=True)
titulos = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())

noticias_validas = st.builds(
    Noticia,
    url=urls,
    titulo=titulos,
    data_publicacao=st.just(datetime(2024, 1, 1, tzinfo=timezone.utc)),
    fonte_id=st.just("fonte_teste"),
    texto_resumido=st.text(max_size=500),
    coletado_em=st.just(datetime(2024, 1, 1, tzinfo=timezone.utc)),
    raw_html=st.none(),
)


def _fonte_rss(fonte_id: str = "fonte_rss") -> FonteConfig:
    return FonteConfig(
        id=fonte_id,
        nome="Fonte Teste",
        url=f"https://example.com/{fonte_id}/feed.xml",
        tipo=TipoFonte.RSS,
        ativo=True,
    )


def _seen(tmp_dir: str) -> SeenUrls:
    return SeenUrls(filepath=Path(tmp_dir) / "seen.json")


# ---------------------------------------------------------------------------
# Property 1: Coleta preserva campos obrigatórios
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 1: Coleta preserva campos obrigatórios
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(noticias=st.lists(noticias_validas, min_size=1, max_size=10))
def test_campos_obrigatorios_preservados(noticias: list[Noticia]) -> None:
    """Para qualquer lista de notícias retornadas pelo fetcher, todos os campos
    obrigatórios devem estar presentes e não-nulos no CollectionResult."""
    with tempfile.TemporaryDirectory() as tmp:
        fonte = _fonte_rss()
        seen = _seen(tmp)
        with patch("src.collector.collector.fetch_rss", return_value=noticias):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

    for noticia in result.collected:
        assert noticia.url is not None and noticia.url != ""
        assert noticia.titulo is not None and noticia.titulo != ""
        assert noticia.data_publicacao is not None
        assert noticia.texto_resumido is not None
        assert noticia.fonte_id is not None and noticia.fonte_id != ""
        assert noticia.coletado_em is not None


# ---------------------------------------------------------------------------
# Property 2: Resiliência a fontes indisponíveis
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 2: Resiliência a fontes indisponíveis
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    noticias_ok=st.lists(noticias_validas, min_size=1, max_size=5),
    n_fontes_erro=st.integers(min_value=1, max_value=3),
)
def test_resiliencia_fontes_indisponiveis(
    noticias_ok: list[Noticia],
    n_fontes_erro: int,
) -> None:
    """Para qualquer combinação de fontes disponíveis e indisponíveis:
    - Cada fonte indisponível gera exatamente um SourceError
    - As notícias das fontes disponíveis aparecem em collected"""
    fonte_ok = _fonte_rss("fonte_ok")
    fontes_erro = [_fonte_rss(f"fonte_erro_{i}") for i in range(n_fontes_erro)]
    todas_fontes = fontes_erro + [fonte_ok]

    def fetch_side_effect(fonte: FonteConfig) -> list[Noticia]:
        if fonte.id.startswith("fonte_erro"):
            raise RuntimeError(f"HTTP 503 — {fonte.id}")
        return noticias_ok

    with tempfile.TemporaryDirectory() as tmp:
        seen = _seen(tmp)
        with patch("src.collector.collector.fetch_rss", side_effect=fetch_side_effect):
            coletor = Coletor(sources=todas_fontes, seen_urls=seen)
            result = coletor.run()

    assert len(result.errors) == n_fontes_erro
    for err in result.errors:
        assert err.fonte_id.startswith("fonte_erro")
        assert err.etapa == "fetch"
        assert err.mensagem != ""

    urls_coletadas = {n.url for n in result.collected}
    for noticia in noticias_ok:
        assert noticia.url in urls_coletadas


# ---------------------------------------------------------------------------
# Property 3: Deduplicação por URL
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 3: Deduplicação por URL
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(noticia=noticias_validas)
def test_deduplicacao_url_ja_vista(noticia: Noticia) -> None:
    """URL já presente em seen_urls deve ser ignorada — não aparece em collected."""
    with tempfile.TemporaryDirectory() as tmp:
        fonte = _fonte_rss()
        seen = _seen(tmp)
        seen.add(noticia.url)
        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

    assert noticia.url not in [n.url for n in result.collected]
    assert result.skipped_duplicates >= 1


# Feature: terrobook-portal, Property 3 (complemento): URL nova é coletada
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(noticia=noticias_validas)
def test_url_nova_e_coletada(noticia: Noticia) -> None:
    """URL não presente em seen_urls deve aparecer em collected."""
    with tempfile.TemporaryDirectory() as tmp:
        fonte = _fonte_rss()
        seen = _seen(tmp)
        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

    assert noticia.url in [n.url for n in result.collected]
    assert result.skipped_duplicates == 0


# Feature: terrobook-portal, Property 3 (mesma URL em duas fontes)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(noticia=noticias_validas)
def test_mesma_url_duas_fontes_deduplica(noticia: Noticia) -> None:
    """Mesma URL retornada por duas fontes deve aparecer apenas uma vez em collected."""
    fonte1 = _fonte_rss("fonte1")
    fonte2 = _fonte_rss("fonte2")

    with tempfile.TemporaryDirectory() as tmp:
        seen = _seen(tmp)
        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte1, fonte2], seen_urls=seen)
            result = coletor.run()

    urls = [n.url for n in result.collected]
    assert urls.count(noticia.url) == 1
    assert result.skipped_duplicates == 1
