"""RawStore — persistência de notícias brutas em data/raw/YYYY-MM-DD.json."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.models import Noticia
from src.storage.serializer import noticia_from_dict, noticia_to_dict


class RawStore:
    """Salva e carrega notícias brutas organizadas por data de coleta."""

    def __init__(self, raw_dir: str | Path = "data/raw") -> None:
        self.raw_dir = Path(raw_dir)

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def save(self, noticias: list[Noticia], data: date) -> Path:
        """Serializa *noticias* e salva em data/raw/YYYY-MM-DD.json.

        Cria o diretório se não existir. Retorna o Path do arquivo gerado.
        """
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path = self.raw_dir / f"{data.isoformat()}.json"
        payload: list[dict[str, Any]] = [noticia_to_dict(n) for n in noticias]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def load(self, data: date) -> list[Noticia]:
        """Carrega notícias do arquivo correspondente à *data*.

        Retorna lista vazia se o arquivo não existir.
        """
        path = self.raw_dir / f"{data.isoformat()}.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [noticia_from_dict(d) for d in raw]

    def load_all(self) -> list[Noticia]:
        """Carrega todas as notícias de todos os arquivos em data/raw/.

        Retorna lista vazia se o diretório não existir ou estiver vazio.
        """
        if not self.raw_dir.exists():
            return []
        noticias: list[Noticia] = []
        for path in sorted(self.raw_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            noticias.extend(noticia_from_dict(d) for d in raw)
        return noticias
