"""Testes unitários para src/collector/html_fetcher.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.collector.html_fetcher import fetch_html
from src.models import FonteConfig, TipoFonte

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HTML_VALIDO = """
<html><body>
  <div class="book-item">
    <h2 class="book-title">O Chamado de Cthulhu</h2>
    <a class="book-link" href="https://exemplo.com/cthulhu">Ver livro</a>
    <p class="book-synopsis">Uma história de horror cósmico de H.P. Lovecraft.</p>
  </div>
  <div class="book-item">
    <h2 class="book-title">It — A Coisa</h2>
    <a class="book-link" href="https://exemplo.com/it">Ver livro</a>
    <p class="book-synopsis">O palhaço Pennywise aterroriza a cidade de Derry.</p>
  </div>
</body></html>
"""

_FONTE_VALIDA = FonteConfig(
    id="teste_html",
    nome="Fonte Teste HTML",
    url="https://exemplo.com/livros",
    tipo=TipoFonte.HTML,
    ativo=True,
    seletores={
        "container": ".book-item",
        "titulo": ".book-title",
        "url": "a.book-link",
        "resumo": ".book-synopsis",
    },
)


def _mock_response(status_code: int = 200, text: str = _HTML_VALIDO) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Testes de coleta bem-sucedida
# ---------------------------------------------------------------------------


def test_fetch_html_retorna_noticias_validas():
    """Deve retornar lista de Noticia com todos os campos obrigatórios preenchidos."""
    with patch("src.collector.html_fetcher.requests.get", return_value=_mock_response()):
        noticias = fetch_html(_FONTE_VALIDA)

    assert len(noticias) == 2
    for n in noticias:
        assert n.url
        assert n.titulo
        assert n.fonte_id == "teste_html"
        assert isinstance(n.data_publicacao, datetime)
        assert isinstance(n.coletado_em, datetime)


def test_fetch_html_campos_corretos():
    """Deve extrair título, URL e resumo corretamente dos seletores."""
    with patch("src.collector.html_fetcher.requests.get", return_value=_mock_response()):
        noticias = fetch_html(_FONTE_VALIDA)

    assert noticias[0].titulo == "O Chamado de Cthulhu"
    assert noticias[0].url == "https://exemplo.com/cthulhu"
    assert "Lovecraft" in noticias[0].texto_resumido

    assert noticias[1].titulo == "It — A Coisa"
    assert noticias[1].url == "https://exemplo.com/it"


def test_fetch_html_raw_html_preenchido():
    """O campo raw_html deve conter o HTML do container."""
    with patch("src.collector.html_fetcher.requests.get", return_value=_mock_response()):
        noticias = fetch_html(_FONTE_VALIDA)

    assert noticias[0].raw_html is not None
    assert "book-item" in noticias[0].raw_html


def test_fetch_html_data_publicacao_utc():
    """data_publicacao deve ser timezone-aware (UTC) quando não disponível no HTML."""
    with patch("src.collector.html_fetcher.requests.get", return_value=_mock_response()):
        noticias = fetch_html(_FONTE_VALIDA)

    for n in noticias:
        assert n.data_publicacao.tzinfo is not None


def test_fetch_html_url_relativa_normalizada():
    """URLs relativas devem ser convertidas para absolutas usando a URL da fonte."""
    html_relativo = """
    <html><body>
      <div class="book-item">
        <h2 class="book-title">Livro Relativo</h2>
        <a class="book-link" href="/livro/123">Ver</a>
        <p class="book-synopsis">Resumo aqui.</p>
      </div>
    </body></html>
    """
    with patch(
        "src.collector.html_fetcher.requests.get",
        return_value=_mock_response(text=html_relativo),
    ):
        noticias = fetch_html(_FONTE_VALIDA)

    assert noticias[0].url == "https://exemplo.com/livro/123"


# ---------------------------------------------------------------------------
# Testes de erro HTTP
# ---------------------------------------------------------------------------


def test_fetch_html_levanta_runtime_error_em_http_404():
    """Deve levantar RuntimeError com mensagem clara para HTTP 404."""
    with patch(
        "src.collector.html_fetcher.requests.get",
        return_value=_mock_response(status_code=404),
    ):
        with pytest.raises(RuntimeError, match="HTTP 404"):
            fetch_html(_FONTE_VALIDA)


def test_fetch_html_levanta_runtime_error_em_http_500():
    """Deve levantar RuntimeError com mensagem clara para HTTP 500."""
    with patch(
        "src.collector.html_fetcher.requests.get",
        return_value=_mock_response(status_code=500),
    ):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            fetch_html(_FONTE_VALIDA)


def test_fetch_html_levanta_runtime_error_em_timeout():
    """Deve levantar RuntimeError em caso de timeout."""
    import requests as req_lib

    with patch(
        "src.collector.html_fetcher.requests.get",
        side_effect=req_lib.exceptions.Timeout(),
    ):
        with pytest.raises(RuntimeError, match="[Tt]imeout"):
            fetch_html(_FONTE_VALIDA)


def test_fetch_html_levanta_runtime_error_em_falha_de_rede():
    """Deve levantar RuntimeError em caso de falha de conexão."""
    import requests as req_lib

    with patch(
        "src.collector.html_fetcher.requests.get",
        side_effect=req_lib.exceptions.ConnectionError("connection refused"),
    ):
        with pytest.raises(RuntimeError, match="[Ff]alha"):
            fetch_html(_FONTE_VALIDA)


# ---------------------------------------------------------------------------
# Testes de seletores inválidos
# ---------------------------------------------------------------------------


def test_fetch_html_levanta_runtime_error_sem_seletores():
    """Deve levantar RuntimeError se a fonte não tiver seletores configurados."""
    fonte_sem_seletores = FonteConfig(
        id="sem_sel",
        nome="Sem Seletores",
        url="https://exemplo.com",
        tipo=TipoFonte.HTML,
        ativo=True,
        seletores=None,
    )
    with pytest.raises(RuntimeError, match="seletores"):
        fetch_html(fonte_sem_seletores)


def test_fetch_html_levanta_runtime_error_com_seletores_incompletos():
    """Deve levantar RuntimeError se faltar algum seletor obrigatório."""
    fonte_incompleta = FonteConfig(
        id="incompleto",
        nome="Incompleto",
        url="https://exemplo.com",
        tipo=TipoFonte.HTML,
        ativo=True,
        seletores={"container": ".item", "titulo": ".title"},  # faltam url e resumo
    )
    with pytest.raises(RuntimeError, match="ausentes"):
        fetch_html(fonte_incompleta)


def test_fetch_html_levanta_runtime_error_container_sem_resultados():
    """Deve levantar RuntimeError se o seletor de container não encontrar elementos."""
    fonte_seletor_errado = FonteConfig(
        id="seletor_errado",
        nome="Seletor Errado",
        url="https://exemplo.com",
        tipo=TipoFonte.HTML,
        ativo=True,
        seletores={
            "container": ".nao-existe",
            "titulo": ".titulo",
            "url": "a",
            "resumo": ".resumo",
        },
    )
    with patch(
        "src.collector.html_fetcher.requests.get", return_value=_mock_response()
    ):
        with pytest.raises(RuntimeError, match="container"):
            fetch_html(fonte_seletor_errado)
