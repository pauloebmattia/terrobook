"""Pipeline principal do Terrobook Portal.

Orquestra Coletor → Curador → Gerador → ReportWriter em sequência,
capturando PipelineError por etapa sem interromper o pipeline inteiro.
"""

from __future__ import annotations

import traceback
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from src.models import (
    CollectionResult,
    ItemCurado,
    PipelineError,
    ResultadoCuradoria,
    StatusCuradoria,
)


@dataclass
class PipelineResult:
    """Resultado completo de uma execução do pipeline."""

    collection_result: CollectionResult | None
    curadoria_results: list[ResultadoCuradoria]
    build_result: object  # BuildResult | None
    pipeline_errors: list[PipelineError]
    data: date


def _load_configs(config_dir: Path) -> tuple[dict, dict, dict]:
    """Carrega settings, sources e keywords do diretório de configuração."""
    settings_path = config_dir / "settings.yaml"
    sources_path = config_dir / "sources.yaml"
    keywords_path = config_dir / "keywords.yaml"

    with settings_path.open(encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    with sources_path.open(encoding="utf-8") as f:
        sources = yaml.safe_load(f)
    with keywords_path.open(encoding="utf-8") as f:
        keywords = yaml.safe_load(f)

    return settings, sources, keywords


def run_pipeline(config_dir: Path = Path("config")) -> PipelineResult:
    """Executa o pipeline completo: Coletor → Curador → Gerador → ReportWriter.

    Cada etapa é executada de forma isolada: exceções são capturadas como
    PipelineError e o pipeline continua para as etapas seguintes sempre que
    possível.

    Args:
        config_dir: Diretório contendo sources.yaml, keywords.yaml e settings.yaml.

    Returns:
        PipelineResult com todos os resultados e erros capturados.
    """
    today = datetime.now(tz=timezone.utc).date()
    pipeline_errors: list[PipelineError] = []
    collection_result: CollectionResult | None = None
    curadoria_results: list[ResultadoCuradoria] = []
    build_result = None

    # ------------------------------------------------------------------
    # Carrega configurações
    # ------------------------------------------------------------------
    try:
        settings, _sources_cfg, _keywords_cfg = _load_configs(config_dir)
    except Exception as exc:  # noqa: BLE001
        pipeline_errors.append(PipelineError(
            etapa="config",
            mensagem=f"Falha ao carregar configurações: {exc}",
            timestamp=datetime.now(tz=timezone.utc),
            traceback=traceback.format_exc(),
        ))
        return PipelineResult(
            collection_result=None,
            curadoria_results=[],
            build_result=None,
            pipeline_errors=pipeline_errors,
            data=today,
        )

    storage_cfg = settings.get("storage", {})
    raw_dir = Path(storage_cfg.get("raw_dir", "data/raw"))
    curated_dir = Path(storage_cfg.get("curated_dir", "data/curated"))
    pending_dir = Path(storage_cfg.get("pending_review_dir", "data/pending_review"))
    discarded_dir = Path(storage_cfg.get("discarded_dir", "data/discarded"))
    reports_dir = Path(storage_cfg.get("reports_dir", "reports"))

    # ------------------------------------------------------------------
    # Etapa 1: Coleta
    # ------------------------------------------------------------------
    try:
        from src.collector.collector import Coletor
        from src.collector.seen_urls import SeenUrls
        from src.storage.raw_store import RawStore

        seen_urls_file = Path(storage_cfg.get("seen_urls_file", "data/seen_urls.json"))
        seen_urls = SeenUrls(filepath=seen_urls_file)

        # Carrega fontes e instancia o Coletor com o seen_urls correto
        import yaml as _yaml
        with (config_dir / "sources.yaml").open(encoding="utf-8") as _f:
            _sources_data = _yaml.safe_load(_f)

        from src.models import FonteConfig, TipoFonte
        _sources: list[FonteConfig] = []
        for _item in _sources_data.get("sources", []):
            _tipo_str = _item.get("tipo", "rss").lower()
            _tipo = TipoFonte.RSS if _tipo_str == "rss" else TipoFonte.HTML
            _sources.append(FonteConfig(
                id=_item["id"],
                nome=_item["nome"],
                url=_item["url"],
                tipo=_tipo,
                ativo=_item.get("ativo", True),
                seletores=_item.get("seletores"),
                ultima_varredura=None,
            ))

        coletor = Coletor(sources=_sources, seen_urls=seen_urls)
        collection_result = coletor.run()

        # Registra erros de fonte como PipelineError
        for source_err in collection_result.errors:
            pipeline_errors.append(PipelineError(
                etapa="collect",
                mensagem=source_err.mensagem,
                timestamp=source_err.timestamp,
                fonte_id=source_err.fonte_id,
            ))

        # Persiste notícias brutas
        if collection_result.collected:
            raw_store = RawStore(raw_dir)
            raw_store.save(collection_result.collected, today)

    except Exception as exc:  # noqa: BLE001
        pipeline_errors.append(PipelineError(
            etapa="collect",
            mensagem=str(exc),
            timestamp=datetime.now(tz=timezone.utc),
            traceback=traceback.format_exc(),
        ))
        # Sem notícias coletadas, não há o que curar
        collection_result = collection_result or _empty_collection_result()

    # ------------------------------------------------------------------
    # Etapa 2: Curadoria
    # ------------------------------------------------------------------
    noticias = collection_result.collected if collection_result else []

    if noticias:
        try:
            from src.curator.curator import Curador
            from src.storage.curated_store import CuratedStore

            curador = Curador.from_config(config_dir / "keywords.yaml")
            curated_store = CuratedStore(curated_dir, pending_dir, discarded_dir)

            for noticia in noticias:
                try:
                    resultado = curador.evaluate(noticia)
                    curadoria_results.append(resultado)

                    if resultado.status == StatusCuradoria.APROVADO:
                        item = ItemCurado(
                            id=str(uuid.uuid4()),
                            noticia=noticia,
                            categoria=resultado.categoria,
                            generos=[],
                            score=resultado.score,
                            aprovado_em=datetime.now(tz=timezone.utc),
                            aprovado_por="auto",
                        )
                        curated_store.save_approved(item)

                    elif resultado.status == StatusCuradoria.PENDENTE_REVISAO:
                        item = ItemCurado(
                            id=str(uuid.uuid4()),
                            noticia=noticia,
                            categoria=resultado.categoria,
                            generos=[],
                            score=resultado.score,
                            aprovado_em=datetime.now(tz=timezone.utc),
                            aprovado_por="auto",
                        )
                        curated_store.save_pending(item)

                    else:
                        curated_store.save_discarded(resultado)

                except Exception as exc:  # noqa: BLE001
                    pipeline_errors.append(PipelineError(
                        etapa="curate",
                        mensagem=f"Erro ao curar notícia '{noticia.url}': {exc}",
                        timestamp=datetime.now(tz=timezone.utc),
                        traceback=traceback.format_exc(),
                    ))

        except Exception as exc:  # noqa: BLE001
            pipeline_errors.append(PipelineError(
                etapa="curate",
                mensagem=str(exc),
                timestamp=datetime.now(tz=timezone.utc),
                traceback=traceback.format_exc(),
            ))

    # ------------------------------------------------------------------
    # Etapa 3: Geração do site
    # ------------------------------------------------------------------
    try:
        from src.generator.generator import Gerador
        from src.storage.curated_store import CuratedStore

        curated_store = CuratedStore(curated_dir, pending_dir, discarded_dir)
        approved_items = curated_store.load_approved()

        if approved_items:
            gerador = Gerador.from_config(config_dir / "settings.yaml")
            build_result = gerador.build(approved_items)

            # Registra BuildErrors como PipelineError
            for build_err in build_result.errors:
                pipeline_errors.append(PipelineError(
                    etapa="generate",
                    mensagem=f"[{build_err.etapa}] item={build_err.item_id}: {build_err.mensagem}",
                    timestamp=build_err.timestamp,
                ))

    except Exception as exc:  # noqa: BLE001
        pipeline_errors.append(PipelineError(
            etapa="generate",
            mensagem=str(exc),
            timestamp=datetime.now(tz=timezone.utc),
            traceback=traceback.format_exc(),
        ))

    # ------------------------------------------------------------------
    # Etapa 4: Relatórios
    # ------------------------------------------------------------------
    try:
        from src.storage.report_writer import write_cycle_report, write_error_report

        if collection_result:
            write_cycle_report(
                result=collection_result,
                curadoria=curadoria_results,
                data=today,
                reports_dir=reports_dir,
            )

        if pipeline_errors:
            write_error_report(
                errors=pipeline_errors,
                data=today,
                reports_dir=reports_dir,
            )

    except Exception as exc:  # noqa: BLE001
        pipeline_errors.append(PipelineError(
            etapa="report",
            mensagem=str(exc),
            timestamp=datetime.now(tz=timezone.utc),
            traceback=traceback.format_exc(),
        ))

    return PipelineResult(
        collection_result=collection_result,
        curadoria_results=curadoria_results,
        build_result=build_result,
        pipeline_errors=pipeline_errors,
        data=today,
    )


def _empty_collection_result() -> CollectionResult:
    """Retorna um CollectionResult vazio para uso em caso de falha na coleta."""
    from src.models import CollectionResult
    return CollectionResult(collected=[], skipped_duplicates=0, errors=[])
