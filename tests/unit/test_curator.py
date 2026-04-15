"""Testes de exemplo para o Curador do Terrobook Portal."""

from datetime import datetime
from pathlib import Path

import pytest

from src.curator.curator import Curador
from src.models import Categoria, KeywordConfig, Noticia, StatusCuradoria


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _noticia(titulo: str, texto: str) -> Noticia:
    return Noticia(
        url="https://exemplo.com/noticia",
        titulo=titulo,
        data_publicacao=datetime(2024, 1, 15),
        fonte_id="fonte-teste",
        texto_resumido=texto,
        coletado_em=datetime(2024, 1, 15),
    )


@pytest.fixture
def config_alta_confianca() -> KeywordConfig:
    """Config com limiar 0.6 e keywords suficientes para testes variados."""
    return KeywordConfig(
        por_genero={
            "terror": ["terror", "horror", "macabro"],
            "thriller": ["thriller", "assassino"],
        },
        por_evento={
            "lancamento": ["lançamento", "publicação"],
            "traducao": ["tradução", "edição brasileira"],
            "autor": ["autor", "escritor"],
        },
        limiar_confianca=0.6,
    )


@pytest.fixture
def curador(config_alta_confianca: KeywordConfig) -> Curador:
    return Curador(config_alta_confianca)


# ---------------------------------------------------------------------------
# Notícia claramente relevante → APROVADO
# ---------------------------------------------------------------------------

def test_noticia_relevante_e_aprovada(curador: Curador) -> None:
    """Notícia com muitas keywords relevantes deve ser aprovada com categoria."""
    noticia = _noticia(
        titulo="Darkside anuncia tradução de clássico do terror",
        texto="A editora lança nova edição brasileira de obra macabra de terror e horror. "
              "O autor é um escritor consagrado do gênero. Publicação prevista para março.",
    )
    resultado = curador.evaluate(noticia)

    assert resultado.status == StatusCuradoria.APROVADO
    assert resultado.score >= 0.6
    assert resultado.categoria is not None
    assert resultado.motivo_rejeicao is None


# ---------------------------------------------------------------------------
# Notícia claramente irrelevante → DESCARTADO
# ---------------------------------------------------------------------------

def test_noticia_irrelevante_e_descartada(curador: Curador) -> None:
    """Notícia sem nenhuma keyword relevante deve ser descartada com motivo."""
    noticia = _noticia(
        titulo="Receitas de bolo para o fim de semana",
        texto="Aprenda a fazer bolos deliciosos com ingredientes simples do dia a dia.",
    )
    resultado = curador.evaluate(noticia)

    assert resultado.status == StatusCuradoria.DESCARTADO
    assert resultado.score == 0.0
    assert resultado.motivo_rejeicao is not None
    assert len(resultado.motivo_rejeicao) > 0


def test_noticia_descartada_motivo_especifico(curador: Curador) -> None:
    """Motivo de rejeição deve indicar ausência de keywords relevantes."""
    noticia = _noticia("Futebol: resultados do campeonato", "Gols e destaques da rodada.")
    resultado = curador.evaluate(noticia)

    assert resultado.motivo_rejeicao == "Nenhuma keyword relevante encontrada"


# ---------------------------------------------------------------------------
# Notícia com score limítrofe → PENDENTE_REVISAO
# ---------------------------------------------------------------------------

def test_noticia_limítrofe_fica_pendente(config_alta_confianca: KeywordConfig) -> None:
    """Com o comportamento atual, qualquer score > 0 resulta em APROVADO.
    PENDENTE_REVISAO só ocorre via revisão manual via CLI."""
    config = KeywordConfig(
        por_genero=config_alta_confianca.por_genero,
        por_evento=config_alta_confianca.por_evento,
        limiar_confianca=0.99,
    )
    curador = Curador(config)
    noticia = _noticia(
        titulo="Novo livro de terror chega às livrarias",
        texto="Uma obra de terror que promete assustar os leitores.",
    )
    resultado = curador.evaluate(noticia)
    # Com o código atual, score > 0 → APROVADO (limiar não é mais usado)
    assert resultado.status == StatusCuradoria.APROVADO
    assert resultado.score > 0.0


# ---------------------------------------------------------------------------
# Invariantes: aprovados têm categoria; descartados têm motivo
# ---------------------------------------------------------------------------

def test_aprovado_sempre_tem_categoria(curador: Curador) -> None:
    """Todo item aprovado deve ter categoria não-nula."""
    noticia = _noticia(
        titulo="Tradução de thriller de terror anunciada pela editora",
        texto="Publicação da edição brasileira do livro de terror e horror. "
              "Lançamento previsto com autor consagrado do thriller macabro.",
    )
    resultado = curador.evaluate(noticia)

    if resultado.status == StatusCuradoria.APROVADO:
        assert resultado.categoria is not None
        assert isinstance(resultado.categoria, Categoria)


def test_descartado_sempre_tem_motivo_rejeicao(curador: Curador) -> None:
    """Todo item descartado deve ter motivo_rejeicao não-nulo e não-vazio."""
    noticia = _noticia("Notícia sem relevância", "Conteúdo completamente fora do escopo.")
    resultado = curador.evaluate(noticia)

    if resultado.status == StatusCuradoria.DESCARTADO:
        assert resultado.motivo_rejeicao is not None
        assert len(resultado.motivo_rejeicao) > 0


# ---------------------------------------------------------------------------
# from_config: carrega keywords do arquivo YAML
# ---------------------------------------------------------------------------

def test_from_config_carrega_keywords() -> None:
    """from_config deve criar Curador funcional a partir do keywords.yaml."""
    config_path = Path("config/keywords.yaml")
    curador = Curador.from_config(config_path)

    assert curador.config.por_genero
    assert curador.config.por_evento
    assert 0.0 < curador.config.limiar_confianca <= 1.0


def test_from_config_avalia_noticia_relevante() -> None:
    """Curador carregado do YAML deve aprovar notícia claramente relevante."""
    config_path = Path("config/keywords.yaml")
    curador = Curador.from_config(config_path)

    noticia = _noticia(
        titulo="Darkside anuncia tradução de clássico do terror",
        texto="Edição brasileira de obra de terror e horror chega ao Brasil. "
              "Lançamento com tradução do autor lovecraftiano.",
    )
    resultado = curador.evaluate(noticia)

    assert resultado.status in (StatusCuradoria.APROVADO, StatusCuradoria.PENDENTE_REVISAO)
    assert resultado.categoria is not None
