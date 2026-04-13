"""Testes de integração do pipeline completo do Terrobook Portal.

Cobre os cenários:
1. Pipeline completo com fontes mock (coleta → curadoria → geração)
2. Pipeline com fonte indisponível (deve continuar e reportar erro)
3. Pipeline com item problemático na geração (deve continuar e reportar erro)

Requisitos: 1.3, 1.4, 4.6, 6.6
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.models import FonteConfig, Noticia, TipoFonte
from src.pipeline import PipelineResult, run_pipeline


# ---------------------------------------------------------------------------
# Fixtures de configuração
# ---------------------------------------------------------------------------

@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Cria um diretório de configuração mínimo e funcional em tmp_path."""
    cfg = tmp_path / "config"
    cfg.mkdir()

    # sources.yaml — uma fonte RSS ativa
    sources = {
        "sources": [
            {
                "id": "fonte_mock",
                "nome": "Fonte Mock",
                "url": "https://mock.example.com/feed.xml",
                "tipo": "rss",
                "ativo": True,
            }
        ]
    }
    (cfg / "sources.yaml").write_text(yaml.dump(sources, allow_unicode=True), encoding="utf-8")

    # keywords.yaml — keywords mínimas para aprovação
    keywords = {
        "por_genero": {
            "terror": ["terror", "horror"],
            "suspense": ["suspense"],
        },
        "por_evento": {
            "lancamento": ["lançamento", "tradução"],
            "traducao": ["tradução"],
        },
        "limiar_confianca": 0.3,
    }
    (cfg / "keywords.yaml").write_text(yaml.dump(keywords, allow_unicode=True), encoding="utf-8")

    # settings.yaml — aponta storage e generator para tmp_path
    settings = {
        "storage": {
            "data_dir": str(tmp_path / "data"),
            "raw_dir": str(tmp_path / "data/raw"),
            "curated_dir": str(tmp_path / "data/curated"),
            "pending_review_dir": str(tmp_path / "data/pending_review"),
            "discarded_dir": str(tmp_path / "data/discarded"),
            "seen_urls_file": str(tmp_path / "data/seen_urls.json"),
            "reports_dir": str(tmp_path / "reports"),
        },
        "generator": {
            "output_dir": str(tmp_path / "site"),
            "templates_dir": "src/generator/templates",
            "site_title": "Terrobook Portal",
            "site_description": "Teste",
            "site_url": "https://terrobook.github.io",
            "itens_por_pagina": 20,
            "rss_max_items": 50,
            "json_api_max_items": 100,
        },
    }
    (cfg / "settings.yaml").write_text(yaml.dump(settings, allow_unicode=True), encoding="utf-8")

    return cfg


def _make_noticia(
    url: str = "https://mock.example.com/noticia-terror-1",
    titulo: str = "Novo lançamento de terror chega ao Brasil",
    texto: str = "Grande lançamento de terror e horror no Brasil. Tradução anunciada.",
    fonte_id: str = "fonte_mock",
) -> Noticia:
    return Noticia(
        url=url,
        titulo=titulo,
        data_publicacao=datetime.now(tz=timezone.utc),
        fonte_id=fonte_id,
        texto_resumido=texto,
        coletado_em=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Cenário 1: Pipeline completo com fontes mock
# ---------------------------------------------------------------------------

class TestPipelineCompleto:
    """Req 1.3 — pipeline executa coleta → curadoria → geração em sequência."""

    def test_pipeline_retorna_pipeline_result(self, config_dir: Path) -> None:
        """run_pipeline deve retornar um PipelineResult."""
        noticias = [_make_noticia()]

        with patch("src.collector.collector.fetch_rss", return_value=noticias):
            result = run_pipeline(config_dir)

        assert isinstance(result, PipelineResult)

    def test_pipeline_coleta_noticias(self, config_dir: Path) -> None:
        """Notícias retornadas pelo fetcher mock devem aparecer em collection_result."""
        noticias = [_make_noticia(url=f"https://mock.example.com/n{i}") for i in range(3)]

        with patch("src.collector.collector.fetch_rss", return_value=noticias):
            result = run_pipeline(config_dir)

        assert result.collection_result is not None
        assert len(result.collection_result.collected) == 3

    def test_pipeline_executa_curadoria(self, config_dir: Path) -> None:
        """Notícias coletadas devem ser avaliadas pelo Curador."""
        noticias = [_make_noticia()]

        with patch("src.collector.collector.fetch_rss", return_value=noticias):
            result = run_pipeline(config_dir)

        # Deve haver ao menos um resultado de curadoria
        assert len(result.curadoria_results) >= 1

    def test_pipeline_gera_site_com_aprovados(self, config_dir: Path) -> None:
        """Itens aprovados devem resultar em arquivos gerados no diretório de saída."""
        noticia = _make_noticia(
            texto="terror horror suspense lançamento tradução Brasil",
        )

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            result = run_pipeline(config_dir)

        settings = yaml.safe_load((config_dir / "settings.yaml").read_text())
        output_dir = Path(settings["generator"]["output_dir"])

        if result.build_result is not None:
            assert output_dir.exists()

    def test_pipeline_sem_erros_criticos_com_fontes_validas(self, config_dir: Path) -> None:
        """Pipeline com fontes válidas não deve gerar PipelineError de etapa crítica."""
        noticias = [_make_noticia()]

        with patch("src.collector.collector.fetch_rss", return_value=noticias):
            result = run_pipeline(config_dir)

        etapas_criticas = {"config", "collect", "curate"}
        erros_criticos = [e for e in result.pipeline_errors if e.etapa in etapas_criticas]
        assert erros_criticos == []

    def test_pipeline_gera_relatorio_de_ciclo(self, config_dir: Path) -> None:
        """Ao final do ciclo, deve existir um relatório JSON em reports/."""
        noticias = [_make_noticia()]

        with patch("src.collector.collector.fetch_rss", return_value=noticias):
            result = run_pipeline(config_dir)

        settings = yaml.safe_load((config_dir / "settings.yaml").read_text())
        reports_dir = Path(settings["storage"]["reports_dir"])
        report_files = list(reports_dir.glob("report_*.json"))
        assert len(report_files) >= 1

        report = json.loads(report_files[0].read_text())
        assert "data" in report
        assert "total_coletado" in report
        assert "aprovados" in report

    def test_pipeline_data_corresponde_a_hoje(self, config_dir: Path) -> None:
        """O campo data do PipelineResult deve corresponder à data atual."""
        from datetime import date

        with patch("src.collector.collector.fetch_rss", return_value=[]):
            result = run_pipeline(config_dir)

        assert result.data == date.today()


# ---------------------------------------------------------------------------
# Cenário 2: Pipeline com fonte indisponível
# ---------------------------------------------------------------------------

class TestPipelineFonteIndisponivel:
    """Req 1.4, 6.6 — falha em fonte não interrompe pipeline; erro é reportado."""

    def test_fonte_indisponivel_nao_interrompe_pipeline(self, config_dir: Path) -> None:
        """RuntimeError em fetch_rss deve ser capturado; pipeline deve concluir."""
        with patch(
            "src.collector.collector.fetch_rss",
            side_effect=RuntimeError("Connection refused"),
        ):
            result = run_pipeline(config_dir)

        assert isinstance(result, PipelineResult)

    def test_fonte_indisponivel_gera_pipeline_error(self, config_dir: Path) -> None:
        """Erro de fonte deve aparecer em pipeline_errors com etapa='collect'."""
        with patch(
            "src.collector.collector.fetch_rss",
            side_effect=RuntimeError("HTTP 503 Service Unavailable"),
        ):
            result = run_pipeline(config_dir)

        erros_collect = [e for e in result.pipeline_errors if e.etapa == "collect"]
        assert len(erros_collect) >= 1

    def test_pipeline_error_tem_campos_obrigatorios(self, config_dir: Path) -> None:
        """Req 6.6 — PipelineError deve ter etapa, mensagem e timestamp não-nulos."""
        with patch(
            "src.collector.collector.fetch_rss",
            side_effect=RuntimeError("Timeout"),
        ):
            result = run_pipeline(config_dir)

        for erro in result.pipeline_errors:
            assert erro.etapa is not None and erro.etapa != ""
            assert erro.mensagem is not None and erro.mensagem != ""
            assert erro.timestamp is not None

    def test_fonte_indisponivel_gera_relatorio_de_erro(self, config_dir: Path) -> None:
        """Req 6.6 — Deve existir error_report_*.json quando há PipelineError."""
        with patch(
            "src.collector.collector.fetch_rss",
            side_effect=RuntimeError("Network error"),
        ):
            result = run_pipeline(config_dir)

        settings = yaml.safe_load((config_dir / "settings.yaml").read_text())
        reports_dir = Path(settings["storage"]["reports_dir"])

        if result.pipeline_errors:
            error_files = list(reports_dir.glob("error_report_*.json"))
            assert len(error_files) >= 1

            errors_data = json.loads(error_files[0].read_text())
            assert isinstance(errors_data, list)
            assert len(errors_data) >= 1

    def test_duas_fontes_uma_indisponivel_coleta_da_outra(self, config_dir: Path) -> None:
        """Req 1.4 — Com duas fontes, falha em uma não impede coleta da outra."""
        sources = yaml.safe_load((config_dir / "sources.yaml").read_text())
        sources["sources"].append({
            "id": "fonte_ok",
            "nome": "Fonte OK",
            "url": "https://ok.example.com/feed.xml",
            "tipo": "rss",
            "ativo": True,
        })
        (config_dir / "sources.yaml").write_text(
            yaml.dump(sources, allow_unicode=True), encoding="utf-8"
        )

        noticia_ok = _make_noticia(
            url="https://ok.example.com/noticia-1",
            fonte_id="fonte_ok",
        )

        def fetch_side_effect(fonte: FonteConfig):
            if fonte.id == "fonte_mock":
                raise RuntimeError("Fonte indisponível")
            return [noticia_ok]

        with patch("src.collector.collector.fetch_rss", side_effect=fetch_side_effect):
            result = run_pipeline(config_dir)

        assert result.collection_result is not None
        urls = [n.url for n in result.collection_result.collected]
        assert noticia_ok.url in urls

        erros_collect = [e for e in result.pipeline_errors if e.etapa == "collect"]
        assert len(erros_collect) >= 1


# ---------------------------------------------------------------------------
# Cenário 3: Pipeline com item problemático na geração
# ---------------------------------------------------------------------------

class TestPipelineItemProblematico:
    """Req 4.6, 6.6 — item problemático na geração não interrompe os demais."""

    def test_item_problematico_nao_interrompe_geracao(self, config_dir: Path) -> None:
        """Req 4.6 — Erro em render_detail de um item não deve interromper o pipeline."""
        from src.generator.generator import BuildResult
        from src.models import BuildError

        noticia = _make_noticia(texto="terror horror lançamento tradução Brasil")

        def build_com_erro(self, items):
            return BuildResult(pages_generated=1, errors=[
                BuildError(
                    item_id="item-problematico",
                    etapa="render_detail",
                    mensagem="Erro simulado de renderização",
                    timestamp=datetime.now(tz=timezone.utc),
                )
            ])

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            with patch("src.generator.generator.Gerador.build", build_com_erro):
                result = run_pipeline(config_dir)

        assert isinstance(result, PipelineResult)

    def test_build_error_aparece_em_pipeline_errors(self, config_dir: Path) -> None:
        """Req 6.6 — BuildError deve ser propagado para pipeline_errors com etapa='generate'."""
        from src.generator.generator import BuildResult
        from src.models import BuildError

        noticia = _make_noticia(texto="terror horror lançamento tradução Brasil")

        def build_com_erro(self, items):
            return BuildResult(
                pages_generated=0,
                errors=[
                    BuildError(
                        item_id="item-xyz",
                        etapa="render_detail",
                        mensagem="Template inválido",
                        timestamp=datetime.now(tz=timezone.utc),
                    )
                ],
            )

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            with patch("src.generator.generator.Gerador.build", build_com_erro):
                result = run_pipeline(config_dir)

        erros_generate = [e for e in result.pipeline_errors if e.etapa == "generate"]
        assert len(erros_generate) >= 1
        assert any("item-xyz" in e.mensagem for e in erros_generate)

    def test_pipeline_continua_apos_erro_na_geracao(self, config_dir: Path) -> None:
        """Req 4.6 — Mesmo com erro na geração, relatórios devem ser gerados."""
        noticia = _make_noticia(texto="terror horror lançamento tradução Brasil")

        def build_levanta_excecao(self, items):
            raise RuntimeError("Falha crítica no gerador")

        with patch("src.collector.collector.fetch_rss", return_value=[noticia]):
            with patch("src.generator.generator.Gerador.build", build_levanta_excecao):
                result = run_pipeline(config_dir)

        assert isinstance(result, PipelineResult)

        erros_generate = [e for e in result.pipeline_errors if e.etapa == "generate"]
        assert len(erros_generate) >= 1

        settings = yaml.safe_load((config_dir / "settings.yaml").read_text())
        reports_dir = Path(settings["storage"]["reports_dir"])
        report_files = list(reports_dir.glob("report_*.json"))
        assert len(report_files) >= 1
