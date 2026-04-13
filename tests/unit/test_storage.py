"""Testes de round-trip para RawStore, CuratedStore e report_writer."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.models import (
    Categoria,
    CollectionResult,
    Genero,
    ItemCurado,
    Noticia,
    PipelineError,
    ResultadoCuradoria,
    SourceError,
    StatusCuradoria,
)
from src.storage.curated_store import CuratedStore
from src.storage.raw_store import RawStore
from src.storage.report_writer import write_cycle_report, write_error_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def make_noticia(url: str = "https://example.com/noticia-1") -> Noticia:
    return Noticia(
        url=url,
        titulo="Darkside anuncia tradução de novo livro de terror",
        data_publicacao=_dt("2024-03-10T12:00:00Z"),
        fonte_id="darkside",
        texto_resumido="A editora Darkside anunciou...",
        coletado_em=_dt("2024-03-10T14:00:00Z"),
        raw_html=None,
    )


def make_item_curado(item_id: str = "abc-123") -> ItemCurado:
    return ItemCurado(
        id=item_id,
        noticia=make_noticia(),
        categoria=Categoria.TRADUCAO_ANUNCIADA,
        generos=[Genero.TERROR],
        score=0.92,
        aprovado_em=_dt("2024-03-10T15:00:00Z"),
        aprovado_por="auto",
        titulo_original="The Haunting",
        autor="Shirley Jackson",
        editora="Darkside",
        data_prevista="2024-06",
        sinopse="Uma casa assombrada...",
        itens_relacionados=[],
    )


# ---------------------------------------------------------------------------
# RawStore
# ---------------------------------------------------------------------------

class TestRawStore:
    def test_save_cria_arquivo(self, tmp_path: Path) -> None:
        store = RawStore(raw_dir=tmp_path / "raw")
        noticias = [make_noticia()]
        path = store.save(noticias, date(2024, 3, 10))
        assert path.exists()
        assert path.name == "2024-03-10.json"

    def test_round_trip_load(self, tmp_path: Path) -> None:
        store = RawStore(raw_dir=tmp_path / "raw")
        original = [make_noticia("https://a.com/1"), make_noticia("https://b.com/2")]
        store.save(original, date(2024, 3, 10))

        loaded = store.load(date(2024, 3, 10))
        assert len(loaded) == 2
        assert loaded[0].url == "https://a.com/1"
        assert loaded[1].url == "https://b.com/2"

    def test_load_preserva_datetime_utc(self, tmp_path: Path) -> None:
        store = RawStore(raw_dir=tmp_path / "raw")
        n = make_noticia()
        store.save([n], date(2024, 3, 10))

        loaded = store.load(date(2024, 3, 10))[0]
        assert loaded.data_publicacao.tzinfo is not None
        assert loaded.coletado_em.tzinfo is not None
        assert loaded.data_publicacao == n.data_publicacao
        assert loaded.coletado_em == n.coletado_em

    def test_load_arquivo_inexistente_retorna_vazio(self, tmp_path: Path) -> None:
        store = RawStore(raw_dir=tmp_path / "raw")
        assert store.load(date(2024, 1, 1)) == []

    def test_load_all_agrega_multiplos_arquivos(self, tmp_path: Path) -> None:
        store = RawStore(raw_dir=tmp_path / "raw")
        store.save([make_noticia("https://a.com/1")], date(2024, 3, 10))
        store.save([make_noticia("https://b.com/2")], date(2024, 3, 11))

        all_noticias = store.load_all()
        urls = {n.url for n in all_noticias}
        assert urls == {"https://a.com/1", "https://b.com/2"}

    def test_load_all_diretorio_inexistente_retorna_vazio(self, tmp_path: Path) -> None:
        store = RawStore(raw_dir=tmp_path / "nao_existe")
        assert store.load_all() == []

    def test_save_cria_diretorios_automaticamente(self, tmp_path: Path) -> None:
        store = RawStore(raw_dir=tmp_path / "a" / "b" / "raw")
        store.save([make_noticia()], date(2024, 3, 10))
        assert (tmp_path / "a" / "b" / "raw" / "2024-03-10.json").exists()


# ---------------------------------------------------------------------------
# CuratedStore
# ---------------------------------------------------------------------------

class TestCuratedStore:
    def _store(self, tmp_path: Path) -> CuratedStore:
        return CuratedStore(
            curated_dir=tmp_path / "curated",
            pending_dir=tmp_path / "pending_review",
            discarded_dir=tmp_path / "discarded",
        )

    def test_save_approved_round_trip(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        item = make_item_curado("id-001")
        path = store.save_approved(item)
        assert path.exists()

        loaded = store.load_approved()
        assert len(loaded) == 1
        assert loaded[0].id == "id-001"
        assert loaded[0].categoria == Categoria.TRADUCAO_ANUNCIADA

    def test_save_pending_round_trip(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        item = make_item_curado("id-002")
        store.save_pending(item)

        loaded = store.load_pending()
        assert len(loaded) == 1
        assert loaded[0].id == "id-002"

    def test_save_discarded_cria_arquivo(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        resultado = ResultadoCuradoria(
            noticia=make_noticia(),
            status=StatusCuradoria.DESCARTADO,
            score=0.1,
            categoria=None,
            motivo_rejeicao="Sem keywords relevantes",
        )
        path = store.save_discarded(resultado)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["motivo_rejeicao"] == "Sem keywords relevantes"
        assert data["status"] == "descartado"

    def test_load_approved_diretorio_inexistente(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        assert store.load_approved() == []

    def test_load_pending_diretorio_inexistente(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        assert store.load_pending() == []

    def test_move_to_approved(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        item = make_item_curado("id-003")
        store.save_pending(item)

        result = store.move_to_approved("id-003")
        assert result is True
        assert store.load_pending() == []
        approved = store.load_approved()
        assert len(approved) == 1
        assert approved[0].id == "id-003"

    def test_move_to_approved_nao_encontrado(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        assert store.move_to_approved("inexistente") is False

    def test_move_to_discarded(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        item = make_item_curado("id-004")
        store.save_pending(item)

        result = store.move_to_discarded("id-004", "Conteúdo irrelevante")
        assert result is True
        assert store.load_pending() == []

        discarded_files = list((tmp_path / "discarded").glob("*.json"))
        assert len(discarded_files) == 1
        data = json.loads(discarded_files[0].read_text(encoding="utf-8"))
        assert data["motivo_rejeicao"] == "Conteúdo irrelevante"

    def test_move_to_discarded_nao_encontrado(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        assert store.move_to_discarded("inexistente", "motivo") is False

    def test_item_curado_preserva_campos_opcionais(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        item = make_item_curado("id-005")
        store.save_approved(item)

        loaded = store.load_approved()[0]
        assert loaded.titulo_original == "The Haunting"
        assert loaded.autor == "Shirley Jackson"
        assert loaded.editora == "Darkside"
        assert loaded.sinopse == "Uma casa assombrada..."

    def test_item_curado_preserva_datetime_utc(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        item = make_item_curado("id-006")
        store.save_approved(item)

        loaded = store.load_approved()[0]
        assert loaded.aprovado_em.tzinfo is not None
        assert loaded.aprovado_em == item.aprovado_em


# ---------------------------------------------------------------------------
# report_writer
# ---------------------------------------------------------------------------

class TestReportWriter:
    def _make_collection_result(self) -> CollectionResult:
        return CollectionResult(
            collected=[make_noticia("https://a.com/1"), make_noticia("https://b.com/2")],
            skipped_duplicates=1,
            errors=[
                SourceError(
                    fonte_id="fonte-x",
                    url="https://x.com",
                    etapa="fetch",
                    mensagem="timeout",
                    timestamp=_dt("2024-03-10T14:00:00Z"),
                )
            ],
        )

    def _make_curadoria(self) -> list[ResultadoCuradoria]:
        n1 = make_noticia("https://a.com/1")
        n2 = make_noticia("https://b.com/2")
        n3 = make_noticia("https://c.com/3")
        return [
            ResultadoCuradoria(n1, StatusCuradoria.APROVADO, 0.9, Categoria.TRADUCAO_ANUNCIADA, None),
            ResultadoCuradoria(n2, StatusCuradoria.PENDENTE_REVISAO, 0.5, None, None),
            ResultadoCuradoria(n3, StatusCuradoria.DESCARTADO, 0.1, None, "Sem keywords"),
        ]

    def test_write_cycle_report_cria_arquivos(self, tmp_path: Path) -> None:
        result = self._make_collection_result()
        curadoria = self._make_curadoria()
        write_cycle_report(result, curadoria, date(2024, 3, 10), tmp_path)

        assert (tmp_path / "report_2024-03-10.json").exists()
        assert (tmp_path / "pending_review_2024-03-10.json").exists()

    def test_write_cycle_report_sumario_correto(self, tmp_path: Path) -> None:
        result = self._make_collection_result()
        curadoria = self._make_curadoria()
        summary = write_cycle_report(result, curadoria, date(2024, 3, 10), tmp_path)

        assert summary["total_coletado"] == 2
        assert summary["aprovados"] == 1
        assert summary["pendentes"] == 1
        assert summary["descartados"] == 1
        assert summary["erros"] == 1

    def test_write_cycle_report_pending_lista_apenas_pendentes(self, tmp_path: Path) -> None:
        result = self._make_collection_result()
        curadoria = self._make_curadoria()
        write_cycle_report(result, curadoria, date(2024, 3, 10), tmp_path)

        pending_data = json.loads(
            (tmp_path / "pending_review_2024-03-10.json").read_text()
        )
        assert len(pending_data) == 1
        assert pending_data[0]["status"] == "pendente_revisao"

    def test_write_cycle_report_sem_pendentes(self, tmp_path: Path) -> None:
        result = CollectionResult(collected=[], skipped_duplicates=0, errors=[])
        curadoria: list[ResultadoCuradoria] = []
        summary = write_cycle_report(result, curadoria, date(2024, 3, 10), tmp_path)

        assert summary["pendentes"] == 0
        pending_data = json.loads(
            (tmp_path / "pending_review_2024-03-10.json").read_text()
        )
        assert pending_data == []

    def test_write_error_report_cria_arquivo(self, tmp_path: Path) -> None:
        errors = [
            PipelineError(
                etapa="collect",
                mensagem="Falha na coleta",
                timestamp=_dt("2024-03-10T14:00:00Z"),
                fonte_id="fonte-x",
                traceback="Traceback...",
            )
        ]
        path = write_error_report(errors, date(2024, 3, 10), tmp_path)
        assert path.exists()
        assert path.name == "error_report_2024-03-10.json"

    def test_write_error_report_conteudo(self, tmp_path: Path) -> None:
        errors = [
            PipelineError(
                etapa="curate",
                mensagem="Erro inesperado",
                timestamp=_dt("2024-03-10T14:00:00Z"),
                fonte_id=None,
                traceback=None,
            )
        ]
        path = write_error_report(errors, date(2024, 3, 10), tmp_path)
        data = json.loads(path.read_text())
        assert len(data) == 1
        assert data[0]["etapa"] == "curate"
        assert data[0]["mensagem"] == "Erro inesperado"

    def test_write_error_report_lista_vazia(self, tmp_path: Path) -> None:
        path = write_error_report([], date(2024, 3, 10), tmp_path)
        data = json.loads(path.read_text())
        assert data == []
