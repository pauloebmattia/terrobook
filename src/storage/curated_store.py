"""CuratedStore — persistência de ItemCurado em curated/, pending_review/ e discarded/."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from src.models import ItemCurado, ResultadoCuradoria
from src.storage.serializer import (
    item_curado_from_dict,
    item_curado_to_dict,
    resultado_curadoria_to_dict,
)


def _url_hash(url: str) -> str:
    """Retorna os primeiros 12 caracteres do SHA-256 da URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _filename_for_item(item: ItemCurado) -> str:
    """Gera nome de arquivo YYYY-MM-DD_{id}.json a partir do item."""
    data_str = item.aprovado_em.date().isoformat()
    return f"{data_str}_{item.id}.json"


class CuratedStore:
    """Gerencia a persistência de itens curados, pendentes e descartados."""

    def __init__(
        self,
        curated_dir: str | Path = "data/curated",
        pending_dir: str | Path = "data/pending_review",
        discarded_dir: str | Path = "data/discarded",
    ) -> None:
        self.curated_dir = Path(curated_dir)
        self.pending_dir = Path(pending_dir)
        self.discarded_dir = Path(discarded_dir)

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def save_approved(self, item: ItemCurado) -> Path:
        """Salva item em data/curated/{YYYY-MM-DD}_{id}.json."""
        self.curated_dir.mkdir(parents=True, exist_ok=True)
        path = self.curated_dir / _filename_for_item(item)
        path.write_text(
            json.dumps(item_curado_to_dict(item), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def save_pending(self, item: ItemCurado) -> Path:
        """Salva item em data/pending_review/{YYYY-MM-DD}_{id}.json."""
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        path = self.pending_dir / _filename_for_item(item)
        path.write_text(
            json.dumps(item_curado_to_dict(item), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def save_discarded(self, resultado: ResultadoCuradoria) -> Path:
        """Salva resultado descartado em data/discarded/{YYYY-MM-DD}_{url_hash}.json."""
        self.discarded_dir.mkdir(parents=True, exist_ok=True)
        data_str = resultado.noticia.coletado_em.date().isoformat()
        url_hash = _url_hash(resultado.noticia.url)
        path = self.discarded_dir / f"{data_str}_{url_hash}.json"
        payload: dict[str, Any] = resultado_curadoria_to_dict(resultado)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def load_approved(self) -> list[ItemCurado]:
        """Carrega todos os itens de data/curated/."""
        return self._load_items(self.curated_dir)

    def load_pending(self) -> list[ItemCurado]:
        """Carrega todos os itens de data/pending_review/."""
        return self._load_items(self.pending_dir)

    def _load_items(self, directory: Path) -> list[ItemCurado]:
        if not directory.exists():
            return []
        items: list[ItemCurado] = []
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append(item_curado_from_dict(data))
        return items

    # ------------------------------------------------------------------
    # Movimentação
    # ------------------------------------------------------------------

    def move_to_approved(self, item_id: str) -> bool:
        """Move item de pending_review para curated.

        Retorna True se o item foi encontrado e movido, False caso contrário.
        """
        source = self._find_in_dir(self.pending_dir, item_id)
        if source is None:
            return False
        self.curated_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(self.curated_dir / source.name))
        return True

    def move_to_discarded(self, item_id: str, motivo: str) -> bool:
        """Move item de pending_review para discarded, adicionando motivo_rejeicao.

        Retorna True se o item foi encontrado e movido, False caso contrário.
        """
        source = self._find_in_dir(self.pending_dir, item_id)
        if source is None:
            return False
        self.discarded_dir.mkdir(parents=True, exist_ok=True)

        # Atualiza o payload com o motivo antes de mover
        payload: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))

        payload["motivo_rejeicao"] = motivo

        dest = self.discarded_dir / source.name
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        source.unlink()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_in_dir(self, directory: Path, item_id: str) -> Path | None:
        """Localiza o arquivo de um item pelo seu ID dentro de *directory*."""
        if not directory.exists():
            return None
        for path in directory.glob(f"*_{item_id}.json"):
            return path
        return None
