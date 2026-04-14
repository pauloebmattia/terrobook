"""Gerador de site estático do Terrobook Portal.

Produz arquivos HTML, RSS e JSON a partir dos itens curados usando Jinja2.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.generator.filter_engine import filter_by_category, filter_by_genre
from src.models import BuildError, Categoria, Genero, ItemCurado


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(value: str) -> str:
    """Converte string para slug URL-safe."""
    value = value.lower()
    value = re.sub(r"[àáâãä]", "a", value)
    value = re.sub(r"[èéêë]", "e", value)
    value = re.sub(r"[ìíîï]", "i", value)
    value = re.sub(r"[òóôõö]", "o", value)
    value = re.sub(r"[ùúûü]", "u", value)
    value = re.sub(r"[ç]", "c", value)
    value = re.sub(r"[ñ]", "n", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


_CATEGORIA_SLUGS: dict[Categoria, str] = {
    Categoria.TRADUCAO_ANUNCIADA: "traducao-anunciada",
    Categoria.LANCAMENTO_PREVISTO: "lancamento-previsto",
    Categoria.NOVO_AUTOR_NACIONAL: "novo-autor-nacional",
    Categoria.AUTOR_INTERNACIONAL_PT: "autor-internacional-pt",
    Categoria.NOTICIA_GERAL: "noticia-geral",
}


# ---------------------------------------------------------------------------
# BuildResult
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    pages_generated: int
    errors: list[BuildError] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Gerador
# ---------------------------------------------------------------------------

class Gerador:
    """Gera o site estático do Terrobook Portal a partir de itens curados."""

    def __init__(self, templates_dir: Path, output_dir: Path, base_path: str = "") -> None:
        self.templates_dir = templates_dir
        self.output_dir = output_dir
        self.base_path = base_path.rstrip("/")
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self._env.globals["base_path"] = self.base_path

    # ------------------------------------------------------------------
    # Renderização de páginas HTML
    # ------------------------------------------------------------------

    def render_index(self, items: list[ItemCurado]) -> None:
        """Gera site/index.html com os itens em ordem cronológica decrescente."""
        sorted_items = sorted(items, key=lambda i: i.aprovado_em, reverse=True)
        template = self._env.get_template("index.html")
        html = template.render(items=sorted_items)
        out = self.output_dir / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

    def render_detail(self, item: ItemCurado, all_items: list[ItemCurado]) -> None:
        """Gera site/item/{id}.html; resolve itens_relacionados por ID em all_items."""
        id_map = {i.id: i for i in all_items}
        related_items = [id_map[rid] for rid in item.itens_relacionados if rid in id_map]

        template = self._env.get_template("detail.html")
        html = template.render(item=item, related_items=related_items)
        out = self.output_dir / "item" / f"{item.id}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

    def render_category_pages(self, items: list[ItemCurado]) -> int:
        """Gera páginas de categoria e gênero; retorna número de páginas geradas."""
        template = self._env.get_template("category.html")
        pages = 0

        # Páginas por categoria
        for categoria in Categoria:
            filtered = filter_by_category(items, categoria)
            if not filtered:
                continue
            slug = _CATEGORIA_SLUGS.get(categoria, _slugify(categoria.value))
            html = template.render(
                page_title=categoria.value,
                items=filtered,
            )
            out = self.output_dir / "categoria" / f"{slug}.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            pages += 1

        # Páginas por gênero
        for genero in Genero:
            filtered = filter_by_genre(items, genero)
            if not filtered:
                continue
            slug = genero.value  # já é slug-safe (ex: "weird_fiction")
            html = template.render(
                page_title=genero.value.replace("_", " ").title(),
                items=filtered,
            )
            out = self.output_dir / "genero" / f"{slug}.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            pages += 1

        return pages

    # ------------------------------------------------------------------
    # RSS
    # ------------------------------------------------------------------

    def render_rss(self, items: list[ItemCurado], site_url: str) -> None:
        """Gera site/feed.xml com RSS 2.0 válido."""
        sorted_items = sorted(items, key=lambda i: i.aprovado_em, reverse=True)

        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")

        ET.SubElement(channel, "title").text = "Terrobook Portal"
        ET.SubElement(channel, "link").text = site_url
        ET.SubElement(channel, "description").text = (
            "Curadoria de notícias sobre literatura de terror, suspense, thriller, "
            "mistério, weird fiction e true crime em português"
        )
        ET.SubElement(channel, "language").text = "pt-BR"

        for item in sorted_items:
            entry = ET.SubElement(channel, "item")
            ET.SubElement(entry, "title").text = item.noticia.titulo
            ET.SubElement(entry, "link").text = f"{site_url}/item/{item.id}.html"
            ET.SubElement(entry, "guid").text = item.id
            ET.SubElement(entry, "description").text = item.noticia.texto_resumido
            pub_dt = item.aprovado_em
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            ET.SubElement(entry, "pubDate").text = format_datetime(pub_dt)

        tree = ET.ElementTree(rss)
        out = self.output_dir / "feed.xml"
        out.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(tree, space="  ")
        tree.write(str(out), encoding="unicode", xml_declaration=True)

    # ------------------------------------------------------------------
    # JSON API
    # ------------------------------------------------------------------

    def render_json_api(self, items: list[ItemCurado]) -> None:
        """Gera site/api/items.json com os itens curados."""
        sorted_items = sorted(items, key=lambda i: i.aprovado_em, reverse=True)

        def _item_to_dict(item: ItemCurado) -> dict[str, Any]:
            return {
                "id": item.id,
                "titulo": item.noticia.titulo,
                "url": item.noticia.url,
                "categoria": item.categoria.value,
                "generos": [g.value for g in item.generos],
                "score": item.score,
                "aprovado_em": item.aprovado_em.isoformat(),
                "texto_resumido": item.noticia.texto_resumido,
                "autor": item.autor,
                "editora": item.editora,
                "data_prevista": item.data_prevista,
                "sinopse": item.sinopse,
                "itens_relacionados": item.itens_relacionados,
            }

        payload = {"items": [_item_to_dict(i) for i in sorted_items]}
        out = self.output_dir / "api" / "items.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Build orquestrador
    # ------------------------------------------------------------------

    def build(self, items: list[ItemCurado]) -> BuildResult:
        """Orquestra a geração completa; isola erros por item e continua."""
        errors: list[BuildError] = []
        pages = 0

        # index.html — opera sobre a lista completa; erros aqui são críticos
        try:
            self.render_index(items)
            pages += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(BuildError(
                item_id="__index__",
                etapa="render_index",
                mensagem=str(exc),
                timestamp=datetime.now(tz=timezone.utc),
            ))

        # Páginas de detalhe — isoladas por item
        valid_items: list[ItemCurado] = []
        for item in items:
            try:
                self.render_detail(item, items)
                pages += 1
                valid_items.append(item)
            except Exception as exc:  # noqa: BLE001
                errors.append(BuildError(
                    item_id=item.id,
                    etapa="render_detail",
                    mensagem=str(exc),
                    timestamp=datetime.now(tz=timezone.utc),
                ))

        # Páginas de categoria/gênero
        try:
            pages += self.render_category_pages(valid_items)
        except Exception as exc:  # noqa: BLE001
            errors.append(BuildError(
                item_id="__categories__",
                etapa="render_category_pages",
                mensagem=str(exc),
                timestamp=datetime.now(tz=timezone.utc),
            ))

        # RSS
        try:
            site_url = "https://terrobook.github.io"
            self.render_rss(valid_items, site_url)
            pages += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(BuildError(
                item_id="__rss__",
                etapa="render_rss",
                mensagem=str(exc),
                timestamp=datetime.now(tz=timezone.utc),
            ))

        # JSON API
        try:
            self.render_json_api(valid_items)
            pages += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(BuildError(
                item_id="__json_api__",
                etapa="render_json_api",
                mensagem=str(exc),
                timestamp=datetime.now(tz=timezone.utc),
            ))

        return BuildResult(pages_generated=pages, errors=errors)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config_path: Path) -> "Gerador":
        """Carrega settings.yaml e instancia o Gerador com os diretórios configurados."""
        with config_path.open(encoding="utf-8") as fh:
            config = yaml.safe_load(fh)

        generator_cfg = config.get("generator", {})
        templates_dir = Path(generator_cfg.get("templates_dir", "src/generator/templates"))
        output_dir = Path(generator_cfg.get("output_dir", "site"))
        base_path = generator_cfg.get("base_path", "")
        return cls(templates_dir=templates_dir, output_dir=output_dir, base_path=base_path)
