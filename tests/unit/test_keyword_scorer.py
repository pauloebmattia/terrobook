"""Testes unitários para src/curator/keyword_scorer.py."""

from datetime import datetime

import pytest

from src.curator.keyword_scorer import score
from src.models import KeywordConfig, Noticia


def _noticia(titulo: str = "", texto: str = "") -> Noticia:
    return Noticia(
        url="https://example.com/noticia",
        titulo=titulo,
        data_publicacao=datetime(2024, 1, 1),
        fonte_id="fonte_teste",
        texto_resumido=texto,
        coletado_em=datetime(2024, 1, 1),
    )


def _config_simples() -> KeywordConfig:
    return KeywordConfig(
        por_genero={"terror": ["terror", "horror"]},
        por_evento={"lancamento": ["lançamento", "estreia"]},
    )


class TestScoreRetornaEntre0e1:
    def test_sem_keywords_retorna_zero(self):
        noticia = _noticia("Notícia sem nenhuma palavra relevante", "Texto qualquer")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado == 0.0

    def test_com_keyword_retorna_positivo(self):
        noticia = _noticia("Novo lançamento de terror", "")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado > 0.0

    def test_resultado_nunca_excede_1(self):
        noticia = _noticia("terror horror lançamento estreia", "terror horror lançamento estreia")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado <= 1.0

    def test_resultado_nunca_negativo(self):
        noticia = _noticia("", "")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado >= 0.0


class TestCaseInsensitive:
    def test_keyword_maiuscula_no_texto(self):
        noticia = _noticia("TERROR no Brasil", "")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado > 0.0

    def test_keyword_mista_no_texto(self):
        noticia = _noticia("Novo Lançamento de Horror", "")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado > 0.0


class TestPesosEventoVsGenero:
    def test_keyword_evento_tem_peso_maior(self):
        """Keyword de evento (peso 2) deve gerar score maior que keyword de gênero (peso 1)
        quando a configuração tem o mesmo número de keywords em cada categoria."""
        config = KeywordConfig(
            por_genero={"terror": ["terror"]},   # 1 keyword, peso 1
            por_evento={"lancamento": ["lançamento"]},  # 1 keyword, peso 2
        )
        # total_ponderado = 1*1 + 1*2 = 3
        noticia_genero = _noticia("terror", "")
        noticia_evento = _noticia("lançamento", "")

        score_genero = score(noticia_genero, config)
        score_evento = score(noticia_evento, config)

        assert score_evento > score_genero

    def test_score_com_apenas_keyword_genero(self):
        config = KeywordConfig(
            por_genero={"terror": ["terror"]},
            por_evento={"lancamento": ["lançamento"]},
        )
        noticia = _noticia("terror", "")
        # hits_ponderados = 1, total_ponderado = 3 → score = 1/3
        resultado = score(noticia, config)
        assert abs(resultado - 1 / 3) < 1e-9

    def test_score_com_apenas_keyword_evento(self):
        config = KeywordConfig(
            por_genero={"terror": ["terror"]},
            por_evento={"lancamento": ["lançamento"]},
        )
        noticia = _noticia("lançamento", "")
        # hits_ponderados = 2, total_ponderado = 3 → score = 2/3
        resultado = score(noticia, config)
        assert abs(resultado - 2 / 3) < 1e-9


class TestDeterminismo:
    def test_mesma_entrada_mesmo_resultado(self):
        noticia = _noticia("Novo lançamento de terror", "Livro de horror chega às livrarias")
        config = _config_simples()
        resultado1 = score(noticia, config)
        resultado2 = score(noticia, config)
        assert resultado1 == resultado2


class TestConfigVazia:
    def test_config_sem_keywords_retorna_zero(self):
        noticia = _noticia("terror horror lançamento", "")
        config = KeywordConfig(por_genero={}, por_evento={})
        resultado = score(noticia, config)
        assert resultado == 0.0


class TestTextoCombinadoTituloETexto:
    def test_keyword_apenas_no_titulo(self):
        noticia = _noticia("terror", "texto sem relevância")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado > 0.0

    def test_keyword_apenas_no_texto_resumido(self):
        noticia = _noticia("título sem relevância", "lançamento de livro")
        config = _config_simples()
        resultado = score(noticia, config)
        assert resultado > 0.0
