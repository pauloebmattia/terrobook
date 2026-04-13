"""Testes de exemplo para src/curator/classifier.py."""

from datetime import datetime

import pytest

from src.curator.classifier import classify
from src.models import Categoria, KeywordConfig, Noticia


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config() -> KeywordConfig:
    """KeywordConfig mínima baseada em config/keywords.yaml."""
    return KeywordConfig(
        por_genero={
            "terror": ["terror", "horror", "sobrenatural"],
            "suspense": ["suspense", "thriller"],
        },
        por_evento={
            "lancamento": ["lançamento", "lança", "publicação", "pré-venda"],
            "traducao": ["tradução", "traduzido", "versão em português", "edição brasileira"],
            "autor": ["autor", "escritor", "debut", "autor nacional", "autor brasileiro"],
        },
        limiar_confianca=0.6,
    )


def _noticia(titulo: str, texto: str) -> Noticia:
    return Noticia(
        url="https://exemplo.com/noticia",
        titulo=titulo,
        data_publicacao=datetime(2024, 1, 15),
        fonte_id="fonte-teste",
        texto_resumido=texto,
        coletado_em=datetime(2024, 1, 15),
    )


# ---------------------------------------------------------------------------
# Testes de classificação por evento
# ---------------------------------------------------------------------------

class TestClassifyTraducao:
    def test_retorna_traducao_anunciada_quando_keyword_traducao_presente(self, config):
        noticia = _noticia(
            "Darkside anuncia tradução de novo livro de terror",
            "A editora confirmou a tradução do bestseller para o português.",
        )
        assert classify(noticia, config) == Categoria.TRADUCAO_ANUNCIADA

    def test_traducao_tem_prioridade_sobre_lancamento(self, config):
        noticia = _noticia(
            "Tradução e lançamento confirmados para 2024",
            "O livro terá tradução e lançamento simultâneos no Brasil.",
        )
        assert classify(noticia, config) == Categoria.TRADUCAO_ANUNCIADA

    def test_traducao_tem_prioridade_sobre_autor(self, config):
        noticia = _noticia(
            "Autor brasileiro tem tradução anunciada",
            "O escritor nacional terá seu livro traduzido para o inglês.",
        )
        assert classify(noticia, config) == Categoria.TRADUCAO_ANUNCIADA


class TestClassifyLancamento:
    def test_retorna_lancamento_previsto_quando_keyword_lancamento_presente(self, config):
        noticia = _noticia(
            "Novo livro de terror chega às livrarias em março",
            "O lançamento está previsto para o primeiro trimestre.",
        )
        assert classify(noticia, config) == Categoria.LANCAMENTO_PREVISTO

    def test_lancamento_tem_prioridade_sobre_autor(self, config):
        noticia = _noticia(
            "Autor estreia com lançamento de suspense",
            "O escritor apresenta seu debut com data de lançamento confirmada.",
        )
        assert classify(noticia, config) == Categoria.LANCAMENTO_PREVISTO


class TestClassifyAutor:
    def test_retorna_novo_autor_nacional_com_indicador_nacional(self, config):
        noticia = _noticia(
            "Autor nacional de terror ganha destaque",
            "O escritor brasileiro apresenta sua primeira obra de horror.",
        )
        assert classify(noticia, config) == Categoria.NOVO_AUTOR_NACIONAL

    def test_retorna_novo_autor_nacional_com_palavra_brasileiro(self, config):
        noticia = _noticia(
            "Escritor brasileiro conquista prêmio de terror",
            "O autor apresenta obra inédita de suspense sobrenatural.",
        )
        assert classify(noticia, config) == Categoria.NOVO_AUTOR_NACIONAL

    def test_retorna_autor_internacional_sem_indicador_nacional(self, config):
        noticia = _noticia(
            "Autor de thriller psicológico em destaque",
            "O escritor apresenta sua mais recente obra de suspense.",
        )
        assert classify(noticia, config) == Categoria.AUTOR_INTERNACIONAL_PT

    def test_retorna_novo_autor_nacional_com_palavra_brasil(self, config):
        noticia = _noticia(
            "Autor de terror do Brasil em destaque",
            "O escritor apresenta obra de horror sobrenatural.",
        )
        assert classify(noticia, config) == Categoria.NOVO_AUTOR_NACIONAL


class TestClassifyNoticiaGeral:
    def test_retorna_noticia_geral_sem_keyword_de_evento(self, config):
        noticia = _noticia(
            "Festival de terror literário acontece em outubro",
            "O evento reúne fãs de horror e suspense de todo o país.",
        )
        assert classify(noticia, config) == Categoria.NOTICIA_GERAL

    def test_retorna_noticia_geral_apenas_com_keyword_de_genero(self, config):
        noticia = _noticia(
            "Prêmio de literatura de terror anuncia finalistas",
            "Os melhores livros de sobrenatural do ano estão na lista.",
        )
        assert classify(noticia, config) == Categoria.NOTICIA_GERAL


# ---------------------------------------------------------------------------
# Testes de retorno None (notícia irrelevante)
# ---------------------------------------------------------------------------

class TestClassifyIrrelevante:
    def test_retorna_none_sem_nenhuma_keyword(self, config):
        noticia = _noticia(
            "Receitas de bolo para o fim de semana",
            "Confira as melhores receitas para surpreender a família.",
        )
        assert classify(noticia, config) is None

    def test_retorna_none_com_texto_vazio(self, config):
        noticia = _noticia("", "")
        assert classify(noticia, config) is None

    def test_retorna_none_com_conteudo_fora_do_escopo(self, config):
        noticia = _noticia(
            "Novo romance de autoajuda bate recordes de venda",
            "O livro de motivação pessoal lidera as listas de mais vendidos.",
        )
        assert classify(noticia, config) is None


# ---------------------------------------------------------------------------
# Testes de case-insensitivity
# ---------------------------------------------------------------------------

class TestClassifyCaseInsensitive:
    def test_keyword_em_maiusculas_no_titulo(self, config):
        noticia = _noticia(
            "TRADUÇÃO de clássico do TERROR confirmada",
            "Editora anuncia publicação para o próximo ano.",
        )
        assert classify(noticia, config) == Categoria.TRADUCAO_ANUNCIADA

    def test_keyword_em_maiusculas_no_texto(self, config):
        noticia = _noticia(
            "Novidade literária",
            "LANÇAMENTO do novo livro de SUSPENSE está confirmado.",
        )
        assert classify(noticia, config) == Categoria.LANCAMENTO_PREVISTO
