"""Testes unitários para SeenUrls."""

import json
import pytest
from pathlib import Path

from src.collector.seen_urls import SeenUrls


@pytest.fixture
def tmp_seen_urls(tmp_path):
    """Retorna uma instância de SeenUrls usando um arquivo temporário."""
    return SeenUrls(filepath=tmp_path / "seen_urls.json")


def test_nova_instancia_nao_contem_urls(tmp_seen_urls):
    assert not tmp_seen_urls.contains("https://example.com/artigo")


def test_add_e_contains(tmp_seen_urls):
    url = "https://example.com/artigo"
    tmp_seen_urls.add(url)
    assert tmp_seen_urls.contains(url)


def test_contains_retorna_false_para_url_diferente(tmp_seen_urls):
    tmp_seen_urls.add("https://example.com/a")
    assert not tmp_seen_urls.contains("https://example.com/b")


def test_save_cria_arquivo(tmp_path):
    filepath = tmp_path / "seen_urls.json"
    seen = SeenUrls(filepath=filepath)
    seen.add("https://example.com/artigo")
    seen.save()
    assert filepath.exists()


def test_save_e_reload_preserva_urls(tmp_path):
    filepath = tmp_path / "seen_urls.json"
    seen = SeenUrls(filepath=filepath)
    seen.add("https://example.com/a")
    seen.add("https://example.com/b")
    seen.save()

    reloaded = SeenUrls(filepath=filepath)
    assert reloaded.contains("https://example.com/a")
    assert reloaded.contains("https://example.com/b")


def test_arquivo_inexistente_nao_lanca_excecao(tmp_path):
    filepath = tmp_path / "nao_existe.json"
    seen = SeenUrls(filepath=filepath)
    assert not seen.contains("https://qualquer.com")


def test_save_cria_diretorios_intermediarios(tmp_path):
    filepath = tmp_path / "subdir" / "nested" / "seen_urls.json"
    seen = SeenUrls(filepath=filepath)
    seen.add("https://example.com")
    seen.save()
    assert filepath.exists()


def test_add_duplicata_nao_duplica_entrada(tmp_path):
    filepath = tmp_path / "seen_urls.json"
    seen = SeenUrls(filepath=filepath)
    url = "https://example.com/artigo"
    seen.add(url)
    seen.add(url)
    seen.save()

    data = json.loads(filepath.read_text())
    assert data.count(url) == 1
