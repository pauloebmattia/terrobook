"""
Testes de smoke para configuração e infraestrutura do Terrobook Portal.

Valida: Requisitos 1.1, 4.3, 7.1, 7.2, 7.3
"""

import os
import yaml
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_yaml(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_text(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Configuração padrão contém fontes de todas as 5 categorias exigidas
# ---------------------------------------------------------------------------

CATEGORIAS_ESPERADAS = {
    "editoras_br": ["darkside", "intrinseca", "aleph", "novo_seculo"],
    "portais_resenha": ["skoob_terror", "leitores_com_br"],
    "blogs": ["medo_literatura", "biblioteca_do_terror"],
    "redes_sociais": ["darkside_instagram"],
    "agregadores_internacionais": ["publishers_weekly", "tor_com"],
}


def test_sources_contem_todas_as_5_categorias():
    """Req 1.1 — sources.yaml deve ter fontes representando as 5 categorias."""
    data = load_yaml("config/sources.yaml")
    ids = {s["id"] for s in data["sources"]}

    for categoria, esperados in CATEGORIAS_ESPERADAS.items():
        encontrados = [sid for sid in esperados if sid in ids]
        assert encontrados, (
            f"Categoria '{categoria}' não possui nenhuma fonte cadastrada. "
            f"Esperava ao menos uma de: {esperados}"
        )


# ---------------------------------------------------------------------------
# 2. Workflow do GitHub Actions contém cron diário e workflow_dispatch
# ---------------------------------------------------------------------------

def test_workflow_tem_cron_diario():
    """Req 7.1 — pipeline.yml deve ter agendamento cron."""
    conteudo = load_text(".github/workflows/pipeline.yml")
    assert "cron:" in conteudo, "pipeline.yml não contém agendamento cron"
    # Verifica que é um cron diário (qualquer expressão com 5 campos e * * *)
    import re
    assert re.search(r"cron:\s*['\"][\d\*\/,\- ]+ \* \* \*['\"]", conteudo), (
        "pipeline.yml não contém cron com frequência diária"
    )


def test_workflow_tem_workflow_dispatch():
    """Req 7.1 — pipeline.yml deve permitir acionamento manual via workflow_dispatch."""
    conteudo = load_text(".github/workflows/pipeline.yml")
    assert "workflow_dispatch" in conteudo, (
        "pipeline.yml não contém 'workflow_dispatch' para acionamento manual"
    )


# ---------------------------------------------------------------------------
# 3. Site gerado não referencia servidor backend
# ---------------------------------------------------------------------------

PACOTES_BACKEND = ["django", "flask", "fastapi", "uvicorn", "gunicorn"]


def test_requirements_sem_servidor_backend():
    """Req 4.3 — requirements.txt não deve conter frameworks de servidor backend."""
    conteudo = load_text("requirements.txt").lower()
    for pacote in PACOTES_BACKEND:
        assert pacote not in conteudo, (
            f"requirements.txt contém '{pacote}', que é um servidor backend. "
            "O portal deve ser estático, sem servidor em execução contínua."
        )


# ---------------------------------------------------------------------------
# 4. Dependências não incluem banco de dados em execução contínua
# ---------------------------------------------------------------------------

PACOTES_BD = ["psycopg2", "sqlalchemy", "pymongo", "redis", "motor", "asyncpg", "tortoise"]


def test_requirements_sem_banco_de_dados():
    """Req 7.2 — requirements.txt não deve conter clientes de banco de dados."""
    conteudo = load_text("requirements.txt").lower()
    for pacote in PACOTES_BD:
        assert pacote not in conteudo, (
            f"requirements.txt contém '{pacote}', que requer banco de dados em execução. "
            "O portal deve usar apenas arquivos JSON/YAML como armazenamento."
        )


# ---------------------------------------------------------------------------
# 5. Arquivos de deploy estão presentes
# ---------------------------------------------------------------------------

ARQUIVOS_DEPLOY = [
    "vercel.json",
    "netlify.toml",
    ".github/workflows/pipeline.yml",
]


@pytest.mark.parametrize("arquivo", ARQUIVOS_DEPLOY)
def test_arquivo_de_deploy_existe(arquivo):
    """Req 7.1, 7.3 — Arquivos de configuração de deploy devem existir."""
    caminho = os.path.join(ROOT, arquivo)
    assert os.path.isfile(caminho), f"Arquivo de deploy ausente: {arquivo}"


# ---------------------------------------------------------------------------
# 6. config/sources.yaml tem ao menos uma fonte ativa por categoria
# ---------------------------------------------------------------------------

FONTES_POR_CATEGORIA = {
    "editoras_br": ["darkside", "intrinseca", "aleph", "novo_seculo"],
    "portais_resenha": ["skoob_terror", "leitores_com_br"],
    "blogs": ["medo_literatura", "biblioteca_do_terror"],
    "agregadores_internacionais": ["publishers_weekly", "tor_com"],
}


def test_sources_tem_fonte_ativa_por_categoria():
    """Req 1.1 — Cada categoria deve ter ao menos uma fonte com ativo: true."""
    data = load_yaml("config/sources.yaml")
    fontes_ativas = {s["id"] for s in data["sources"] if s.get("ativo", False)}

    for categoria, ids_esperados in FONTES_POR_CATEGORIA.items():
        ativas_na_categoria = [sid for sid in ids_esperados if sid in fontes_ativas]
        assert ativas_na_categoria, (
            f"Categoria '{categoria}' não possui nenhuma fonte ativa. "
            f"Fontes esperadas: {ids_esperados}. Ativas no total: {fontes_ativas}"
        )


# ---------------------------------------------------------------------------
# 7. config/keywords.yaml tem keywords para todos os 6 gêneros do escopo
# ---------------------------------------------------------------------------

GENEROS_ESCOPO = ["terror", "suspense", "thriller", "misterio", "weird_fiction", "true_crime"]


def test_keywords_contem_todos_os_generos():
    """Req 1.1 — keywords.yaml deve ter palavras-chave para os 6 gêneros do escopo."""
    data = load_yaml("config/keywords.yaml")
    por_genero = data.get("por_genero", {})

    for genero in GENEROS_ESCOPO:
        assert genero in por_genero, (
            f"Gênero '{genero}' não encontrado em keywords.yaml[por_genero]"
        )
        keywords = por_genero[genero]
        assert isinstance(keywords, list) and len(keywords) > 0, (
            f"Gênero '{genero}' não possui palavras-chave definidas"
        )
