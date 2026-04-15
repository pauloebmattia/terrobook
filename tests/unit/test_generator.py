"""Testes de exemplo para o Gerador de site estático do Terrobook Portal.

Cobre:
- Renderização de index com lista de itens mock
- Renderização de detalhe com campos opcionais ausentes
- Geração de RSS com XML válido (parseável)
- Resiliência: item problemático não interrompe geração dos demais
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from src.generator.generator import BuildResult, Gerador
from src.models import Categoria, Genero, ItemCurado, Noticia


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path("src/generator/templates")


def _make_noticia(url: str = "https://exemplo.com/noticia-1") -> Noticia:
    return Noticia(
        url=url,
        titulo="Darkside anuncia tradução de novo livro de terror",
        data_publicacao=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
        fonte_id="darkside",
        texto_resumido="A editora Darkside Books anunciou a tradução de um novo título.",
        coletado_em=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
    )


def _make_item(
    item_id: str = "item-001",
    categoria: Categoria = Categoria.TRADUCAO_ANUNCIADA,
    generos: list[Genero] | None = None,
    aprovado_em: datetime | None = None,
    **kwargs,
) -> ItemCurado:
    return ItemCurado(
        id=item_id,
        noticia=_make_noticia(url=f"https://exemplo.com/{item_id}"),
        categoria=categoria,
        generos=generos or [Genero.TERROR],
        score=0.9,
        aprovado_em=aprovado_em or datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
        aprovado_por="auto",
        **kwargs,
    )


@pytest.fixture()
def gerador(tmp_path: Path) -> Gerador:
    return Gerador(templates_dir=TEMPLATES_DIR, output_dir=tmp_path / "site")


# ---------------------------------------------------------------------------
# Testes de render_index
# ---------------------------------------------------------------------------

class TestRenderIndex:
    def test_gera_arquivo_index(self, gerador: Gerador) -> None:
        items = [_make_item("a"), _make_item("b")]
        gerador.render_index(items)
        assert (gerador.output_dir / "index.html").exists()

    def test_index_contem_titulos_dos_itens(self, gerador: Gerador) -> None:
        item = _make_item("x")
        gerador.render_index([item])
        html = (gerador.output_dir / "index.html").read_text(encoding="utf-8")
        assert item.noticia.titulo in html

    def test_index_com_lista_vazia(self, gerador: Gerador) -> None:
        gerador.render_index([])
        html = (gerador.output_dir / "index.html").read_text(encoding="utf-8")
        assert "Nenhum item publicado ainda" in html

    def test_index_ordem_cronologica_decrescente(self, gerador: Gerador) -> None:
        item_antigo = _make_item(
            "antigo",
            aprovado_em=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        item_novo = _make_item(
            "novo",
            aprovado_em=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        gerador.render_index([item_antigo, item_novo])
        html = (gerador.output_dir / "index.html").read_text(encoding="utf-8")
        # O template usa link direto para a URL da notícia — verifica pela URL
        pos_novo = html.find(item_novo.noticia.url)
        pos_antigo = html.find(item_antigo.noticia.url)
        assert pos_novo != -1 and pos_antigo != -1, "Ambas as URLs devem aparecer no HTML"
        assert pos_novo < pos_antigo, "Item mais novo deve aparecer antes do mais antigo"


# ---------------------------------------------------------------------------
# Testes de render_detail
# ---------------------------------------------------------------------------

class TestRenderDetail:
    def test_gera_arquivo_de_detalhe(self, gerador: Gerador) -> None:
        item = _make_item("det-001")
        gerador.render_detail(item, [item])
        assert (gerador.output_dir / "item" / "det-001.html").exists()

    def test_detalhe_sem_campos_opcionais(self, gerador: Gerador) -> None:
        """Campos opcionais ausentes não devem causar erro na renderização."""
        item = _make_item(
            "sem-opcionals",
            autor=None,
            editora=None,
            sinopse=None,
            data_prevista=None,
            titulo_original=None,
        )
        gerador.render_detail(item, [item])
        html = (gerador.output_dir / "item" / "sem-opcionals.html").read_text(encoding="utf-8")
        assert item.noticia.titulo in html

    def test_detalhe_contem_link_fonte_original(self, gerador: Gerador) -> None:
        item = _make_item("link-test")
        gerador.render_detail(item, [item])
        html = (gerador.output_dir / "item" / "link-test.html").read_text(encoding="utf-8")
        assert item.noticia.url in html

    def test_detalhe_com_campos_opcionais_preenchidos(self, gerador: Gerador) -> None:
        item = _make_item(
            "completo",
            autor="Stephen King",
            editora="Darkside Books",
            sinopse="Uma história de terror.",
            data_prevista="Março 2025",
            titulo_original="The Shining",
        )
        gerador.render_detail(item, [item])
        html = (gerador.output_dir / "item" / "completo.html").read_text(encoding="utf-8")
        assert "Stephen King" in html
        assert "Darkside Books" in html
        assert "The Shining" in html

    def test_detalhe_resolve_itens_relacionados(self, gerador: Gerador) -> None:
        item_rel = _make_item("rel-001")
        item_main = _make_item("main-001", itens_relacionados=["rel-001"])
        all_items = [item_main, item_rel]
        gerador.render_detail(item_main, all_items)
        html = (gerador.output_dir / "item" / "main-001.html").read_text(encoding="utf-8")
        assert "rel-001" in html

    def test_detalhe_id_relacionado_inexistente_nao_quebra(self, gerador: Gerador) -> None:
        """IDs relacionados que não existem em all_items devem ser ignorados silenciosamente."""
        item = _make_item("orphan", itens_relacionados=["nao-existe"])
        gerador.render_detail(item, [item])
        assert (gerador.output_dir / "item" / "orphan.html").exists()


# ---------------------------------------------------------------------------
# Testes de render_rss
# ---------------------------------------------------------------------------

class TestRenderRss:
    def test_gera_arquivo_feed_xml(self, gerador: Gerador) -> None:
        items = [_make_item("rss-1")]
        gerador.render_rss(items, "https://terrobook.github.io")
        assert (gerador.output_dir / "feed.xml").exists()

    def test_rss_e_xml_valido(self, gerador: Gerador) -> None:
        """O feed.xml deve ser parseável como XML válido."""
        items = [_make_item("rss-valid")]
        gerador.render_rss(items, "https://terrobook.github.io")
        xml_content = (gerador.output_dir / "feed.xml").read_text(encoding="utf-8")
        # Não deve lançar exceção
        root = ET.fromstring(xml_content)
        assert root.tag == "rss"

    def test_rss_contem_itens(self, gerador: Gerador) -> None:
        items = [_make_item("rss-a"), _make_item("rss-b")]
        gerador.render_rss(items, "https://terrobook.github.io")
        xml_content = (gerador.output_dir / "feed.xml").read_text(encoding="utf-8")
        root = ET.fromstring(xml_content)
        channel = root.find("channel")
        assert channel is not None
        item_elements = channel.findall("item")
        assert len(item_elements) == 2

    def test_rss_com_lista_vazia(self, gerador: Gerador) -> None:
        gerador.render_rss([], "https://terrobook.github.io")
        xml_content = (gerador.output_dir / "feed.xml").read_text(encoding="utf-8")
        root = ET.fromstring(xml_content)
        assert root.tag == "rss"


# ---------------------------------------------------------------------------
# Testes de render_json_api
# ---------------------------------------------------------------------------

class TestRenderJsonApi:
    def test_gera_arquivo_json(self, gerador: Gerador) -> None:
        items = [_make_item("json-1")]
        gerador.render_json_api(items)
        assert (gerador.output_dir / "api" / "items.json").exists()

    def test_json_e_valido(self, gerador: Gerador) -> None:
        items = [_make_item("json-valid")]
        gerador.render_json_api(items)
        content = (gerador.output_dir / "api" / "items.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert "items" in data
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Testes de build — resiliência
# ---------------------------------------------------------------------------

class TestBuild:
    def test_build_retorna_build_result(self, gerador: Gerador) -> None:
        items = [_make_item("build-1")]
        result = gerador.build(items)
        assert isinstance(result, BuildResult)
        assert result.pages_generated > 0

    def test_build_item_problematico_nao_interrompe_demais(
        self, gerador: Gerador, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Um item que causa erro em render_detail não deve impedir os demais."""
        item_ok = _make_item("ok-item")
        item_bad = _make_item("bad-item")

        original_render_detail = gerador.render_detail

        def render_detail_com_falha(item: ItemCurado, all_items: list[ItemCurado]) -> None:
            if item.id == "bad-item":
                raise ValueError("Erro simulado no item problemático")
            original_render_detail(item, all_items)

        monkeypatch.setattr(gerador, "render_detail", render_detail_com_falha)

        result = gerador.build([item_ok, item_bad])

        # O item ok deve ter sido gerado
        assert (gerador.output_dir / "item" / "ok-item.html").exists()
        # O item problemático deve ter gerado um BuildError
        assert any(e.item_id == "bad-item" for e in result.errors)
        # A geração não foi interrompida (pages_generated > 0)
        assert result.pages_generated > 0

    def test_build_sem_itens(self, gerador: Gerador) -> None:
        result = gerador.build([])
        assert isinstance(result, BuildResult)
        assert result.errors == []

    def test_build_registra_erro_sem_interromper(
        self, gerador: Gerador, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Erros em itens individuais são registrados em BuildResult.errors."""
        items = [_make_item(f"item-{i}") for i in range(3)]
        item_ruim = items[1]

        original = gerador.render_detail

        def falha_no_segundo(item: ItemCurado, all_items: list[ItemCurado]) -> None:
            if item.id == item_ruim.id:
                raise RuntimeError("falha proposital")
            original(item, all_items)

        monkeypatch.setattr(gerador, "render_detail", falha_no_segundo)

        result = gerador.build(items)
        assert len(result.errors) == 1
        assert result.errors[0].item_id == item_ruim.id
        assert result.errors[0].etapa == "render_detail"


# ---------------------------------------------------------------------------
# Testes de from_config
# ---------------------------------------------------------------------------

class TestFromConfig:
    def test_from_config_carrega_settings(self, tmp_path: Path) -> None:
        config = {
            "generator": {
                "templates_dir": str(TEMPLATES_DIR),
                "output_dir": str(tmp_path / "site"),
            }
        }
        import yaml

        config_path = tmp_path / "settings.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        gerador = Gerador.from_config(config_path)
        assert gerador.templates_dir == TEMPLATES_DIR
        assert gerador.output_dir == tmp_path / "site"
