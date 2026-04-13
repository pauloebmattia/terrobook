"""Testes de exemplo para o Coletor."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.collector.collector import Coletor
from src.collector.seen_urls import SeenUrls
from src.models import CollectionResult, FonteConfig, Noticia, TipoFonte


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fonte_rss(id: str = "fonte_rss", ativo: bool = True) -> FonteConfig:
    return FonteConfig(
        id=id,
        nome="Fonte RSS Teste",
        url="https://example.com/feed.xml",
        tipo=TipoFonte.RSS,
        ativo=ativo,
    )


def _make_fonte_html(id: str = "fonte_html", ativo: bool = True) -> FonteConfig:
    return FonteConfig(
        id=id,
        nome="Fonte HTML Teste",
        url="https://example.com/noticias",
        tipo=TipoFonte.HTML,
        ativo=ativo,
        seletores={
            "container": ".item",
            "titulo": ".titulo",
            "url": "a",
            "resumo": ".resumo",
        },
    )


def _make_noticia(url: str = "https://example.com/noticia-1", fonte_id: str = "fonte_rss") -> Noticia:
    return Noticia(
        url=url,
        titulo="Notícia de Teste",
        data_publicacao=datetime.now(tz=timezone.utc),
        fonte_id=fonte_id,
        texto_resumido="Resumo da notícia de teste.",
        coletado_em=datetime.now(tz=timezone.utc),
    )


def _make_seen_urls(tmp_path: Path) -> SeenUrls:
    return SeenUrls(filepath=tmp_path / "seen_urls.json")


# ---------------------------------------------------------------------------
# Testes de coleta RSS
# ---------------------------------------------------------------------------

class TestColetaRSS:
    def test_coleta_rss_retorna_noticias(self, tmp_path):
        """Coletor deve retornar notícias coletadas de fonte RSS válida."""
        fonte = _make_fonte_rss()
        noticia = _make_noticia()
        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

        assert isinstance(result, CollectionResult)
        assert len(result.collected) == 1
        assert result.collected[0].url == noticia.url
        assert result.skipped_duplicates == 0
        assert result.errors == []

    def test_coleta_rss_multiplas_noticias(self, tmp_path):
        """Coletor deve retornar todas as notícias de um feed RSS com múltiplos itens."""
        fonte = _make_fonte_rss()
        noticias = [
            _make_noticia(url=f"https://example.com/noticia-{i}")
            for i in range(5)
        ]
        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_rss", return_value=noticias):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

        assert len(result.collected) == 5
        assert result.skipped_duplicates == 0

    def test_fonte_inativa_nao_e_coletada(self, tmp_path):
        """Fontes com ativo=False não devem ser processadas."""
        fonte = _make_fonte_rss(ativo=False)
        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_rss") as mock_fetch:
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

        mock_fetch.assert_not_called()
        assert result.collected == []
        assert result.errors == []


# ---------------------------------------------------------------------------
# Testes de coleta HTML
# ---------------------------------------------------------------------------

class TestColetaHTML:
    def test_coleta_html_retorna_noticias(self, tmp_path):
        """Coletor deve retornar notícias coletadas de fonte HTML válida."""
        fonte = _make_fonte_html()
        noticia = _make_noticia(url="https://example.com/pagina-1", fonte_id="fonte_html")
        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_html", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

        assert len(result.collected) == 1
        assert result.collected[0].url == noticia.url
        assert result.errors == []

    def test_coleta_html_multiplas_noticias(self, tmp_path):
        """Coletor deve retornar todas as notícias de uma página HTML com múltiplos itens."""
        fonte = _make_fonte_html()
        noticias = [
            _make_noticia(url=f"https://example.com/pagina-{i}", fonte_id="fonte_html")
            for i in range(3)
        ]
        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_html", return_value=noticias):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

        assert len(result.collected) == 3


# ---------------------------------------------------------------------------
# Testes de tratamento de erros
# ---------------------------------------------------------------------------

class TestTratamentoErros:
    def test_erro_http_500_capturado_e_continua(self, tmp_path):
        """Fonte com erro HTTP 500 deve gerar SourceError e não interromper coleta."""
        fonte_erro = _make_fonte_rss(id="fonte_com_erro")
        fonte_ok = _make_fonte_rss(id="fonte_ok")
        fonte_ok.url = "https://example.com/feed2.xml"
        noticia_ok = _make_noticia(url="https://example.com/noticia-ok", fonte_id="fonte_ok")
        seen = _make_seen_urls(tmp_path)

        def fetch_rss_side_effect(fonte):
            if fonte.id == "fonte_com_erro":
                raise RuntimeError(
                    f"Falha ao acessar o feed '{fonte.nome}' ({fonte.url}): HTTP 500"
                )
            return [noticia_ok]

        with patch("src.collector.collector.fetch_rss", side_effect=fetch_rss_side_effect):
            coletor = Coletor(sources=[fonte_erro, fonte_ok], seen_urls=seen)
            result = coletor.run()

        # Deve ter coletado da fonte OK
        assert len(result.collected) == 1
        assert result.collected[0].url == noticia_ok.url

        # Deve ter registrado o erro da fonte com falha
        assert len(result.errors) == 1
        assert result.errors[0].fonte_id == "fonte_com_erro"
        assert "HTTP 500" in result.errors[0].mensagem
        assert result.errors[0].etapa == "fetch"

    def test_erro_nao_interrompe_demais_fontes(self, tmp_path):
        """Erro em uma fonte não deve impedir coleta das demais."""
        fontes = [_make_fonte_rss(id=f"fonte_{i}") for i in range(3)]
        for f in fontes:
            f.url = f"https://example.com/feed{f.id}.xml"

        noticias_por_fonte = {
            "fonte_0": RuntimeError("Timeout"),
            "fonte_1": [_make_noticia(url="https://example.com/n1", fonte_id="fonte_1")],
            "fonte_2": [_make_noticia(url="https://example.com/n2", fonte_id="fonte_2")],
        }

        def fetch_side_effect(fonte):
            resultado = noticias_por_fonte[fonte.id]
            if isinstance(resultado, Exception):
                raise resultado
            return resultado

        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_rss", side_effect=fetch_side_effect):
            coletor = Coletor(sources=fontes, seen_urls=seen)
            result = coletor.run()

        assert len(result.collected) == 2
        assert len(result.errors) == 1
        assert result.errors[0].fonte_id == "fonte_0"


# ---------------------------------------------------------------------------
# Testes de deduplicação
# ---------------------------------------------------------------------------

class TestDeduplicacao:
    def test_url_ja_vista_nao_aparece_em_collected(self, tmp_path):
        """URL já presente em seen_urls não deve aparecer em collected."""
        url_duplicada = "https://example.com/noticia-duplicada"
        fonte = _make_fonte_rss()
        noticia = _make_noticia(url=url_duplicada)
        seen = _make_seen_urls(tmp_path)
        seen.add(url_duplicada)  # Pré-popula como já vista

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

        assert url_duplicada not in [n.url for n in result.collected]
        assert result.skipped_duplicates == 1

    def test_url_nova_aparece_em_collected(self, tmp_path):
        """URL nova (não vista antes) deve aparecer em collected."""
        url_nova = "https://example.com/noticia-nova"
        fonte = _make_fonte_rss()
        noticia = _make_noticia(url=url_nova)
        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            result = coletor.run()

        assert url_nova in [n.url for n in result.collected]
        assert result.skipped_duplicates == 0

    def test_mesma_url_em_duas_fontes_deduplica(self, tmp_path):
        """Mesma URL retornada por duas fontes distintas deve ser coletada apenas uma vez."""
        url_compartilhada = "https://example.com/noticia-compartilhada"
        fonte1 = _make_fonte_rss(id="fonte1")
        fonte2 = _make_fonte_rss(id="fonte2")
        fonte2.url = "https://example.com/feed2.xml"

        noticia1 = _make_noticia(url=url_compartilhada, fonte_id="fonte1")
        noticia2 = _make_noticia(url=url_compartilhada, fonte_id="fonte2")

        seen = _make_seen_urls(tmp_path)

        call_count = 0

        def fetch_side_effect(fonte):
            nonlocal call_count
            call_count += 1
            if fonte.id == "fonte1":
                return [noticia1]
            return [noticia2]

        with patch("src.collector.collector.fetch_rss", side_effect=fetch_side_effect):
            coletor = Coletor(sources=[fonte1, fonte2], seen_urls=seen)
            result = coletor.run()

        urls_coletadas = [n.url for n in result.collected]
        assert urls_coletadas.count(url_compartilhada) == 1
        assert result.skipped_duplicates == 1

    def test_seen_urls_atualizado_apos_coleta(self, tmp_path):
        """Após run(), as URLs coletadas devem estar presentes em seen_urls."""
        url = "https://example.com/nova-noticia"
        fonte = _make_fonte_rss()
        noticia = _make_noticia(url=url)
        seen = _make_seen_urls(tmp_path)

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            coletor.run()

        assert seen.contains(url)

    def test_seen_urls_salvo_em_disco_apos_coleta(self, tmp_path):
        """Após run(), o arquivo seen_urls deve ser persistido em disco."""
        url = "https://example.com/noticia-persistida"
        fonte = _make_fonte_rss()
        noticia = _make_noticia(url=url)
        seen_path = tmp_path / "seen_urls.json"
        seen = SeenUrls(filepath=seen_path)

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            coletor = Coletor(sources=[fonte], seen_urls=seen)
            coletor.run()

        assert seen_path.exists()
        # Carrega novamente para verificar persistência
        seen2 = SeenUrls(filepath=seen_path)
        assert seen2.contains(url)
