"""CLI de administração do Terrobook Portal.

Uso:
    python -m src collect
    python -m src curate
    python -m src generate
    python -m src approve <id>
    python -m src reject <id> --motivo <texto>
    python -m src edit <id>
    python -m src run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Carregamento de configurações
# ---------------------------------------------------------------------------

def _load_settings(settings_path: Path = Path("config/settings.yaml")) -> dict:
    if not settings_path.exists():
        print(f"[ERRO] Arquivo de configuração não encontrado: {settings_path}", file=sys.stderr)
        sys.exit(1)
    with settings_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_sources(sources_path: Path = Path("config/sources.yaml")) -> dict:
    if not sources_path.exists():
        print(f"[ERRO] Arquivo de fontes não encontrado: {sources_path}", file=sys.stderr)
        sys.exit(1)
    with sources_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_keywords(keywords_path: Path = Path("config/keywords.yaml")) -> dict:
    if not keywords_path.exists():
        print(f"[ERRO] Arquivo de keywords não encontrado: {keywords_path}", file=sys.stderr)
        sys.exit(1)
    with keywords_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_all_configs() -> tuple[dict, dict, dict]:
    """Carrega e retorna (settings, sources, keywords)."""
    settings = _load_settings()
    sources = _load_sources()
    keywords = _load_keywords()
    return settings, sources, keywords


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------

def cmd_collect(args: argparse.Namespace) -> int:
    """Executa o Coletor e salva notícias brutas."""
    print("[collect] Carregando configurações...")
    settings, sources, _keywords = _load_all_configs()

    storage_cfg = settings.get("storage", {})
    seen_urls_file = Path(storage_cfg.get("seen_urls_file", "data/seen_urls.json"))
    raw_dir = Path(storage_cfg.get("raw_dir", "data/raw"))

    try:
        from src.collector.collector import Coletor
        from src.collector.seen_urls import SeenUrls
        from src.storage.raw_store import RawStore
    except ImportError as exc:
        print(f"[ERRO] Falha ao importar módulos: {exc}", file=sys.stderr)
        return 1

    print("[collect] Iniciando coleta de notícias...")
    try:
        coletor = Coletor.from_config(Path("config/sources.yaml"))
        result = coletor.run()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] Falha durante a coleta: {exc}", file=sys.stderr)
        return 1

    print(f"[collect] Coletadas: {len(result.collected)} notícias")
    print(f"[collect] Duplicatas ignoradas: {result.skipped_duplicates}")
    if result.errors:
        print(f"[collect] Erros em {len(result.errors)} fonte(s):")
        for err in result.errors:
            print(f"  - {err.fonte_id}: {err.mensagem}")

    if result.collected:
        store = RawStore(raw_dir)
        today = datetime.now(tz=timezone.utc).date()
        path = store.save(result.collected, today)
        print(f"[collect] Notícias salvas em: {path}")
    else:
        print("[collect] Nenhuma notícia nova para salvar.")

    return 0


def cmd_curate(args: argparse.Namespace) -> int:
    """Executa o Curador nas notícias brutas do dia e salva resultados."""
    print("[curate] Carregando configurações...")
    settings, _sources, _keywords = _load_all_configs()

    storage_cfg = settings.get("storage", {})
    raw_dir = Path(storage_cfg.get("raw_dir", "data/raw"))
    curated_dir = Path(storage_cfg.get("curated_dir", "data/curated"))
    pending_dir = Path(storage_cfg.get("pending_review_dir", "data/pending_review"))
    discarded_dir = Path(storage_cfg.get("discarded_dir", "data/discarded"))

    try:
        from src.curator.curator import Curador
        from src.models import ItemCurado, StatusCuradoria
        from src.storage.curated_store import CuratedStore
        from src.storage.raw_store import RawStore
    except ImportError as exc:
        print(f"[ERRO] Falha ao importar módulos: {exc}", file=sys.stderr)
        return 1

    today = datetime.now(tz=timezone.utc).date()
    raw_store = RawStore(raw_dir)
    noticias = raw_store.load_all()

    if not noticias:
        print(f"[curate] Nenhuma notícia bruta encontrada.")
        return 0

    print(f"[curate] Avaliando {len(noticias)} notícias (todos os arquivos em data/raw/)...")

    try:
        curador = Curador.from_config(Path("config/keywords.yaml"))
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] Falha ao inicializar Curador: {exc}", file=sys.stderr)
        return 1

    curated_store = CuratedStore(curated_dir, pending_dir, discarded_dir)
    aprovados = pendentes = descartados = 0

    for noticia in noticias:
        try:
            resultado = curador.evaluate(noticia)
        except Exception as exc:  # noqa: BLE001
            print(f"  [AVISO] Erro ao avaliar '{noticia.url}': {exc}")
            continue

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
            aprovados += 1
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
            pendentes += 1
        else:
            curated_store.save_discarded(resultado)
            descartados += 1

    print(f"[curate] Aprovados: {aprovados} | Pendentes: {pendentes} | Descartados: {descartados}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Executa o Gerador com os itens aprovados."""
    print("[generate] Carregando configurações...")
    settings, _sources, _keywords = _load_all_configs()

    storage_cfg = settings.get("storage", {})
    curated_dir = Path(storage_cfg.get("curated_dir", "data/curated"))

    try:
        from src.generator.generator import Gerador
        from src.storage.curated_store import CuratedStore
    except ImportError as exc:
        print(f"[ERRO] Falha ao importar módulos: {exc}", file=sys.stderr)
        return 1

    curated_store = CuratedStore(curated_dir=curated_dir)
    items = curated_store.load_approved()

    if not items:
        print("[generate] Nenhum item aprovado encontrado. Gerando site vazio...")

    print(f"[generate] Gerando site com {len(items)} item(ns) aprovado(s)...")

    try:
        gerador = Gerador.from_config(Path("config/settings.yaml"))
        result = gerador.build(items)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] Falha durante a geração: {exc}", file=sys.stderr)
        return 1

    print(f"[generate] Páginas geradas: {result.pages_generated}")
    if result.errors:
        print(f"[generate] Erros em {len(result.errors)} item(ns):")
        for err in result.errors:
            print(f"  - {err.item_id} ({err.etapa}): {err.mensagem}")

    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    """Move item de pending_review para curated."""
    item_id: str = args.id
    print(f"[approve] Carregando configurações...")
    settings, _sources, _keywords = _load_all_configs()

    storage_cfg = settings.get("storage", {})
    curated_dir = Path(storage_cfg.get("curated_dir", "data/curated"))
    pending_dir = Path(storage_cfg.get("pending_review_dir", "data/pending_review"))
    discarded_dir = Path(storage_cfg.get("discarded_dir", "data/discarded"))

    try:
        from src.storage.curated_store import CuratedStore
    except ImportError as exc:
        print(f"[ERRO] Falha ao importar módulos: {exc}", file=sys.stderr)
        return 1

    store = CuratedStore(curated_dir, pending_dir, discarded_dir)
    print(f"[approve] Aprovando item '{item_id}'...")

    if store.move_to_approved(item_id):
        print(f"[approve] Item '{item_id}' movido para curated com sucesso.")
        return 0
    else:
        print(f"[ERRO] Item '{item_id}' não encontrado em pending_review.", file=sys.stderr)
        return 1


def cmd_reject(args: argparse.Namespace) -> int:
    """Move item de pending_review para discarded."""
    item_id: str = args.id
    motivo: str = args.motivo

    print(f"[reject] Carregando configurações...")
    settings, _sources, _keywords = _load_all_configs()

    storage_cfg = settings.get("storage", {})
    curated_dir = Path(storage_cfg.get("curated_dir", "data/curated"))
    pending_dir = Path(storage_cfg.get("pending_review_dir", "data/pending_review"))
    discarded_dir = Path(storage_cfg.get("discarded_dir", "data/discarded"))

    try:
        from src.storage.curated_store import CuratedStore
    except ImportError as exc:
        print(f"[ERRO] Falha ao importar módulos: {exc}", file=sys.stderr)
        return 1

    store = CuratedStore(curated_dir, pending_dir, discarded_dir)
    print(f"[reject] Rejeitando item '{item_id}' com motivo: {motivo}")

    if store.move_to_discarded(item_id, motivo):
        print(f"[reject] Item '{item_id}' movido para discarded com sucesso.")
        return 0
    else:
        print(f"[ERRO] Item '{item_id}' não encontrado em pending_review.", file=sys.stderr)
        return 1


def cmd_edit(args: argparse.Namespace) -> int:
    """Abre o arquivo JSON do item em pending_review para edição manual."""
    item_id: str = args.id

    print(f"[edit] Carregando configurações...")
    settings, _sources, _keywords = _load_all_configs()

    storage_cfg = settings.get("storage", {})
    pending_dir = Path(storage_cfg.get("pending_review_dir", "data/pending_review"))

    # Localiza o arquivo do item
    if not pending_dir.exists():
        print(f"[ERRO] Diretório pending_review não encontrado: {pending_dir}", file=sys.stderr)
        return 1

    matches = list(pending_dir.glob(f"*_{item_id}.json"))
    if not matches:
        print(f"[ERRO] Item '{item_id}' não encontrado em pending_review.", file=sys.stderr)
        return 1

    item_path = matches[0]
    editor = os.environ.get("EDITOR", "")

    if editor:
        print(f"[edit] Abrindo '{item_path}' com {editor}...")
        try:
            subprocess.run([editor, str(item_path)], check=True)
            print(f"[edit] Edição concluída.")
            return 0
        except subprocess.CalledProcessError as exc:
            print(f"[ERRO] Editor retornou código {exc.returncode}.", file=sys.stderr)
            return 1
        except FileNotFoundError:
            print(f"[ERRO] Editor '{editor}' não encontrado.", file=sys.stderr)
            return 1
    else:
        print(f"[edit] Variável $EDITOR não definida.")
        print(f"[edit] Edite manualmente o arquivo: {item_path.resolve()}")
        return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Executa o pipeline completo: collect → curate → generate."""
    print("[run] Iniciando pipeline completo...")
    _load_all_configs()  # valida configs antes de começar

    etapas = [
        ("collect", cmd_collect),
        ("curate", cmd_curate),
        ("generate", cmd_generate),
    ]

    for nome, func in etapas:
        print(f"\n[run] ── Etapa: {nome} ──")
        code = func(args)
        if code != 0:
            print(f"[ERRO] Pipeline interrompido na etapa '{nome}' (código {code}).", file=sys.stderr)
            return 1

    print("\n[run] Pipeline concluído com sucesso.")
    return 0


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terrobook",
        description="CLI de administração do Terrobook Portal",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<comando>")
    subparsers.required = True

    # collect
    subparsers.add_parser(
        "collect",
        help="Executa o Coletor e salva notícias brutas",
    )

    # curate
    subparsers.add_parser(
        "curate",
        help="Executa o Curador nas notícias brutas do dia e salva resultados",
    )

    # generate
    subparsers.add_parser(
        "generate",
        help="Executa o Gerador com os itens aprovados",
    )

    # approve
    approve_p = subparsers.add_parser(
        "approve",
        help="Move item de pending_review para curated",
    )
    approve_p.add_argument("id", help="ID do item a aprovar")

    # reject
    reject_p = subparsers.add_parser(
        "reject",
        help="Move item de pending_review para discarded",
    )
    reject_p.add_argument("id", help="ID do item a rejeitar")
    reject_p.add_argument("--motivo", required=True, help="Motivo da rejeição")

    # edit
    edit_p = subparsers.add_parser(
        "edit",
        help="Abre o arquivo JSON do item em pending_review para edição manual",
    )
    edit_p.add_argument("id", help="ID do item a editar")

    # run
    subparsers.add_parser(
        "run",
        help="Executa o pipeline completo (collect → curate → generate)",
    )

    return parser


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_COMMANDS = {
    "collect": cmd_collect,
    "curate": cmd_curate,
    "generate": cmd_generate,
    "approve": cmd_approve,
    "reject": cmd_reject,
    "edit": cmd_edit,
    "run": cmd_run,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = _COMMANDS[args.command]
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
