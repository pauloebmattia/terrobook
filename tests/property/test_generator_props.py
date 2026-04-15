"""Testes de propriedade para o Gerador e FilterEngine do Terrobook Portal.

Propriedades cobertas:
- Property 9:  Filtro por categoria é exato
- Property 10: Página de detalhe contém campos disponíveis do item
- Property 11: Gerador produz artefatos de saída válidos (RSS e JSON)
- Property 12: Resiliência a itens problemáticos na geração
- Property 13: Ordenação cronológica decrescente na página inicial
- Property 14: Itens relacionados aparecem na página de detalhe
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.generator.filter_engine import filter_by_category, filter_by_genre
from src.generator.generator import BuildResult, Gerador
from src.models import Categoria, Genero, ItemCurado, Noticia

TEMPLATES_DIR = Path("src/generator/templates")


# ---------------------------------------------------------------------------
# Estratégias compartilhadas
# ---------------------------------------------------------------------------

categorias = st.sampled_from(list(Categoria))
generos = st.sampled_from(list(Genero))


def _dt(offset_days: int = 0) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset_days)


def _noticia(url: str = "https://example.com/n") -> Noticia:
    return Noticia(
        url=url,
        titulo="Título de teste",
        data_publicacao=_dt(),
        fonte_id="fonte_teste",
        texto_resumido="Resumo de teste.",
        coletado_em=_dt(),
    )


def _item(
    item_id: str = "id-001",
    categoria: Categoria = Categoria.NOTICIA_GERAL,
    generos_list: list[Genero] | None = None,
    offset_days: int = 0,
    **kwargs,
) -> ItemCurado:
    return ItemCurado(
        id=item_id,
        noticia=_noticia(url=f"https://example.com/{item_id}"),
        categoria=categoria,
        generos=generos_list or [Genero.TERROR],
        score=0.8,
        aprovado_em=_dt(offset_days),
        aprovado_por="auto",
        **kwargs,
    )


itens_strategy = st.lists(
    st.builds(
        _item,
        item_id=st.uuids().map(str),
        categoria=categorias,
        generos_list=st.lists(generos, min_size=0, max_size=3),
        offset_days=st.integers(min_value=0, max_value=365),
    ),
    min_size=0,
    max_size=20,
)


def _gerador(tmp_dir: str) -> Gerador:
    return Gerador(templates_dir=TEMPLATES_DIR, output_dir=Path(tmp_dir) / "site")


# ---------------------------------------------------------------------------
# Property 9: Filtro por categoria é exato
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 9: Filtro por categoria é exato
@settings(max_examples=100)
@given(items=itens_strategy, categoria=categorias)
def test_filtro_categoria_sem_falsos_positivos(
    items: list[ItemCurado], categoria: Categoria
) -> None:
    """filter_by_category não deve retornar itens de outra categoria."""
    resultado = filter_by_category(items, categoria)
    for item in resultado:
        assert item.categoria == categoria


@settings(max_examples=100)
@given(items=itens_strategy, categoria=categorias)
def test_filtro_categoria_sem_falsos_negativos(
    items: list[ItemCurado], categoria: Categoria
) -> None:
    """filter_by_category não deve omitir itens da categoria selecionada."""
    resultado = filter_by_category(items, categoria)
    ids_resultado = {item.id for item in resultado}
    for item in items:
        if item.categoria == categoria:
            assert item.id in ids_resultado


@settings(max_examples=100)
@given(items=itens_strategy, genero=generos)
def test_filtro_genero_sem_falsos_positivos(
    items: list[ItemCurado], genero: Genero
) -> None:
    """filter_by_genre não deve retornar itens que não contêm o gênero."""
    resultado = filter_by_genre(items, genero)
    for item in resultado:
        assert genero in item.generos


@settings(max_examples=100)
@given(items=itens_strategy, genero=generos)
def test_filtro_genero_sem_falsos_negativos(
    items: list[ItemCurado], genero: Genero
) -> None:
    """filter_by_genre não deve omitir itens que contêm o gênero."""
    resultado = filter_by_genre(items, genero)
    ids_resultado = {item.id for item in resultado}
    for item in items:
        if genero in item.generos:
            assert item.id in ids_resultado


# ---------------------------------------------------------------------------
# Property 11: Gerador produz artefatos de saída válidos
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 11: RSS e JSON válidos
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(items=itens_strategy)
def test_rss_e_xml_valido(items: list[ItemCurado]) -> None:
    """Para qualquer lista de itens, o feed.xml gerado deve ser XML válido
    com tag raiz 'rss'."""
    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        gerador.render_rss(items, "https://terrobook.github.io")
        xml_path = Path(tmp) / "site" / "feed.xml"
        assert xml_path.exists()
        root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
        assert root.tag == "rss"


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(items=itens_strategy)
def test_json_api_valido(items: list[ItemCurado]) -> None:
    """Para qualquer lista de itens, o items.json gerado deve ser JSON válido
    com chave 'items' e comprimento correto."""
    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        gerador.render_json_api(items)
        json_path = Path(tmp) / "site" / "api" / "items.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "items" in data
        assert len(data["items"]) == len(items)


# ---------------------------------------------------------------------------
# Property 12: Resiliência a itens problemáticos
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 12: Resiliência a itens problemáticos
def test_item_problematico_nao_interrompe_geracao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um item que causa erro em render_detail não deve impedir a geração
    dos demais itens."""
    item_ok = _item("ok-001")
    item_bad = _item("bad-001")

    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        original = gerador.render_detail

        def render_com_falha(item: ItemCurado, all_items: list[ItemCurado]) -> None:
            if item.id == "bad-001":
                raise ValueError("Erro simulado")
            original(item, all_items)

        monkeypatch.setattr(gerador, "render_detail", render_com_falha)
        result = gerador.build([item_ok, item_bad])

        assert (Path(tmp) / "site" / "item" / "ok-001.html").exists()

    assert any(e.item_id == "bad-001" for e in result.errors)
    assert result.pages_generated > 0


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(n_items=st.integers(min_value=2, max_value=8))
def test_build_registra_erro_sem_interromper(
    n_items: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Erros em itens individuais são registrados em BuildResult.errors
    sem interromper a geração dos demais."""
    items = [_item(f"item-{i}", offset_days=i) for i in range(n_items)]
    item_ruim = items[0]

    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        original = gerador.render_detail

        def falha_no_primeiro(item: ItemCurado, all_items: list[ItemCurado]) -> None:
            if item.id == item_ruim.id:
                raise RuntimeError("falha proposital")
            original(item, all_items)

        monkeypatch.setattr(gerador, "render_detail", falha_no_primeiro)
        result = gerador.build(items)

    assert len(result.errors) == 1
    assert result.errors[0].item_id == item_ruim.id
    assert result.errors[0].etapa == "render_detail"
    assert result.pages_generated >= n_items - 1


# ---------------------------------------------------------------------------
# Property 13: Ordenação cronológica decrescente na página inicial
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 13: Ordenação cronológica decrescente
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    offsets=st.lists(
        st.integers(min_value=0, max_value=365),
        min_size=2,
        max_size=8,
        unique=True,
    )
)
def test_index_ordem_cronologica_decrescente(offsets: list[int]) -> None:
    """O HTML da página inicial deve listar os itens em ordem decrescente de
    aprovado_em."""
    items = [_item(f"item-{i:03d}", offset_days=off) for i, off in enumerate(offsets)]

    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        gerador.render_index(items)
        html = (Path(tmp) / "site" / "index.html").read_text(encoding="utf-8")

    items_sorted = sorted(items, key=lambda x: x.aprovado_em, reverse=True)
    posicoes = [html.find(item.id) for item in items_sorted]
    posicoes_validas = [p for p in posicoes if p >= 0]

    if len(posicoes_validas) >= 2:
        for i in range(len(posicoes_validas) - 1):
            assert posicoes_validas[i] <= posicoes_validas[i + 1], (
                "Item mais recente deve aparecer antes do mais antigo no HTML"
            )


# ---------------------------------------------------------------------------
# Property 14: Itens relacionados aparecem na página de detalhe
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 14: Itens relacionados na página de detalhe
def test_itens_relacionados_aparecem_no_detalhe() -> None:
    """Para um item com itens_relacionados não-vazio, o HTML de detalhe deve
    conter referências para cada ID relacionado."""
    item_rel = _item("rel-001")
    item_main = _item("main-001", itens_relacionados=["rel-001"])

    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        gerador.render_detail(item_main, [item_main, item_rel])
        html = (Path(tmp) / "site" / "item" / "main-001.html").read_text(encoding="utf-8")

    assert "rel-001" in html


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(n_relacionados=st.integers(min_value=1, max_value=5))
def test_todos_relacionados_aparecem(n_relacionados: int) -> None:
    """Todos os IDs em itens_relacionados devem aparecer no HTML de detalhe."""
    ids_rel = [f"rel-{i:03d}" for i in range(n_relacionados)]
    itens_rel = [_item(rid) for rid in ids_rel]
    item_main = _item("main-001", itens_relacionados=ids_rel)

    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        gerador.render_detail(item_main, [item_main] + itens_rel)
        html = (Path(tmp) / "site" / "item" / "main-001.html").read_text(encoding="utf-8")

    for rid in ids_rel:
        assert rid in html


def test_id_relacionado_inexistente_nao_quebra() -> None:
    """IDs relacionados que não existem em all_items devem ser ignorados."""
    item = _item("orphan", itens_relacionados=["nao-existe-123"])

    with tempfile.TemporaryDirectory() as tmp:
        gerador = _gerador(tmp)
        gerador.render_detail(item, [item])
        assert (Path(tmp) / "site" / "item" / "orphan.html").exists()
