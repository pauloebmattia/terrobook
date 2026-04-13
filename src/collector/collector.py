"""Orquestrador de coleta de notícias a partir de múltiplas fontes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.collector.html_fetcher import fetch_html
from src.collector.rss_fetcher import fetch_rss
from src.collector.seen_urls import SeenUrls
from src.models import CollectionResult, FonteConfig, SourceError, TipoFonte

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path("config/sources.yaml")


class Coletor:
    """Orquestra a coleta de notícias a partir de uma lista de fontes configuradas."""

    def __init__(self, sources: list[FonteConfig], seen_urls: SeenUrls) -> None:
        self.sources = sources
        self.seen_urls = seen_urls

    def run(self) -> CollectionResult:
        """Executa a varredura em todas as fontes ativas.

        Itera sobre as fontes com ``ativo == True``, chama o fetcher adequado
        (RSS ou HTML), aplica deduplicação via ``SeenUrls`` e captura erros
        por fonte sem interromper as demais.

        Returns:
            CollectionResult com as notícias coletadas, contagem de duplicatas
            ignoradas e lista de erros por fonte.
        """
        collected = []
        skipped_duplicates = 0
        errors: list[SourceError] = []

        fontes_ativas = [f for f in self.sources if f.ativo]

        for fonte in fontes_ativas:
            try:
                if fonte.tipo == TipoFonte.RSS:
                    noticias = fetch_rss(fonte)
                elif fonte.tipo == TipoFonte.HTML:
                    noticias = fetch_html(fonte)
                else:
                    logger.warning("Tipo de fonte desconhecido: %s", fonte.tipo)
                    continue
            except RuntimeError as exc:
                logger.error("Erro ao coletar fonte '%s': %s", fonte.id, exc)
                errors.append(
                    SourceError(
                        fonte_id=fonte.id,
                        url=fonte.url,
                        etapa="fetch",
                        mensagem=str(exc),
                        timestamp=datetime.now(tz=timezone.utc),
                    )
                )
                continue

            for noticia in noticias:
                if self.seen_urls.contains(noticia.url):
                    skipped_duplicates += 1
                else:
                    collected.append(noticia)
                    self.seen_urls.add(noticia.url)

        self.seen_urls.save()

        return CollectionResult(
            collected=collected,
            skipped_duplicates=skipped_duplicates,
            errors=errors,
        )

    @classmethod
    def from_config(cls, config_path: Path = _DEFAULT_CONFIG) -> "Coletor":
        """Carrega fontes de ``config/sources.yaml`` e retorna uma instância de Coletor.

        Args:
            config_path: Caminho para o arquivo YAML de fontes.

        Returns:
            Instância de Coletor configurada com as fontes do arquivo.
        """
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        sources: list[FonteConfig] = []
        for item in data.get("sources", []):
            tipo_str = item.get("tipo", "rss").lower()
            tipo = TipoFonte.RSS if tipo_str == "rss" else TipoFonte.HTML
            sources.append(
                FonteConfig(
                    id=item["id"],
                    nome=item["nome"],
                    url=item["url"],
                    tipo=tipo,
                    ativo=item.get("ativo", True),
                    seletores=item.get("seletores"),
                    ultima_varredura=None,
                )
            )

        seen_urls = SeenUrls()
        return cls(sources=sources, seen_urls=seen_urls)
