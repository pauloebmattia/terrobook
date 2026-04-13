"""Gerenciamento de URLs já coletadas para deduplicação."""

from __future__ import annotations

import json
from pathlib import Path

SEEN_URLS_FILE = Path("data/seen_urls.json")


class SeenUrls:
    """Mantém um índice de URLs já coletadas, persistido em disco como JSON."""

    def __init__(self, filepath: Path = SEEN_URLS_FILE) -> None:
        self._filepath = filepath
        self._urls: set[str] = set()
        self._load()

    def _load(self) -> None:
        """Carrega o índice do disco. Cria o arquivo se não existir."""
        if self._filepath.exists():
            with self._filepath.open("r", encoding="utf-8") as f:
                data = json.load(f)
                self._urls = set(data)
        else:
            self._urls = set()

    def add(self, url: str) -> None:
        """Adiciona uma URL ao índice."""
        self._urls.add(url)

    def contains(self, url: str) -> bool:
        """Retorna True se a URL já foi coletada anteriormente."""
        return url in self._urls

    def save(self) -> None:
        """Persiste o índice em disco, criando o arquivo e diretórios se necessário."""
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        with self._filepath.open("w", encoding="utf-8") as f:
            json.dump(sorted(self._urls), f, ensure_ascii=False, indent=2)
