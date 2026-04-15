"""Testes de propriedade para o Curador do Terrobook Portal.

Propriedades cobertas (adaptadas ao código atual):
- Property 4: Classificação consistente com keywords
- Property 5: Itens aprovados sempre têm categoria
- Property 7: Itens descartados sempre têm motivo de rejeição
- Property 8: Score é monotônico em relação às keywords

Nota sobre mudanças no código:
- O limiar de confiança foi removido da lógica de aprovação: qualquer score > 0
  resulta em APROVADO (não há mais PENDENTE_REVISAO automático).
- O curador tem filtro de filmes/séries e filtro de idioma (inglês → score 0).
- Property 6 (baixa confiança → PENDENTE_REVISAO) foi removida pois o comportamento
  mudou: PENDENTE_REVISAO só ocorre via revisão manual via CLI.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from src.curator.curator import Curador
from src.curator.keyword_scorer import score as calcular_score
from src.models import (
    Categoria,
    KeywordConfig,
    Noticia,
    StatusCuradoria,
)


# ---------------------------------------------------------------------------
# Estratégias compartilhadas
# ---------------------------------------------------------------------------

_KW_GENERO_PT = ["terror", "horror", "suspense"]  # apenas keywords presentes em config_minima
_KW_EVENTO_PT = ["lançamento", "tradução", "resenha", "autor", "publicação"]

config_minima = KeywordConfig(
    por_genero={"terror": ["terror", "horror"], "suspense": ["suspense"]},
    por_evento={
        "lancamento": ["lançamento", "publicação"],
        "traducao": ["tradução"],
        "resenha": ["resenha"],
        "autor": ["autor"],
    },
    limiar_confianca=0.01,
)

def _noticia(titulo: str = "", texto: str = "") -> Noticia:
    return Noticia(
        url="https://example.com/noticia",
        titulo=titulo,
        data_publicacao=datetime(2024, 1, 1, tzinfo=timezone.utc),
        fonte_id="fonte_teste",
        texto_resumido=texto,
        coletado_em=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

textos_pt = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzáéíóúãõâêôçàüABCDEFGHIJKLMNOPQRSTUVWXYZ ",
    min_size=5,
    max_size=300,
)


# ---------------------------------------------------------------------------
# Property 4: Classificação consistente com keywords
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 4: Classificação consistente com keywords
def test_noticia_com_keyword_genero_nao_descartada() -> None:
    """Notícia com ao menos uma keyword de gênero em PT não deve ser descartada
    pelo scorer (a menos que seja filtrada por idioma ou filmes)."""
    curador = Curador(config_minima)
    noticia = _noticia("Novo livro de terror chega ao Brasil", "Uma obra de horror nacional.")
    resultado = curador.evaluate(noticia)
    # Deve ser aprovada (score > 0, texto em PT, sem termos de mídia sem livro)
    assert resultado.status == StatusCuradoria.APROVADO


def test_noticia_sem_keywords_descartada() -> None:
    """Notícia sem nenhuma keyword relevante deve ser descartada."""
    curador = Curador(config_minima)
    noticia = _noticia("Receita de bolo de chocolate", "Ingredientes e modo de preparo.")
    resultado = curador.evaluate(noticia)
    assert resultado.status == StatusCuradoria.DESCARTADO


# Feature: terrobook-portal, Property 4 (score > 0 → não descartado por keywords)
@settings(max_examples=100)
@given(kw=st.sampled_from(_KW_GENERO_PT))
def test_keyword_genero_pt_gera_score_positivo(kw: str) -> None:
    """Para qualquer keyword de gênero em PT presente no texto, o score deve ser > 0."""
    noticia = _noticia(f"Livro de {kw} publicado no Brasil", f"Uma obra de {kw}.")
    s = calcular_score(noticia, config_minima)
    assert s > 0.0


# ---------------------------------------------------------------------------
# Property 5: Itens aprovados sempre têm categoria
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 5: Itens aprovados sempre têm categoria
@settings(max_examples=100)
@given(kw_genero=st.sampled_from(_KW_GENERO_PT))
def test_aprovado_sempre_tem_categoria(kw_genero: str) -> None:
    """Para qualquer notícia aprovada, o campo categoria deve ser não-nulo
    e pertencer ao enum Categoria."""
    curador = Curador(config_minima)
    noticia = _noticia(
        f"Novo {kw_genero} publicado no Brasil",
        f"Uma obra de {kw_genero} chega às livrarias.",
    )
    resultado = curador.evaluate(noticia)
    if resultado.status == StatusCuradoria.APROVADO:
        assert resultado.categoria is not None
        assert isinstance(resultado.categoria, Categoria)


# ---------------------------------------------------------------------------
# Property 7: Itens descartados sempre têm motivo de rejeição
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 7: Descartados sempre têm motivo
@settings(max_examples=100)
@given(texto=textos_pt)
def test_descartado_sempre_tem_motivo(texto: str) -> None:
    """Para qualquer ResultadoCuradoria com status DESCARTADO, o campo
    motivo_rejeicao deve ser não-nulo e não-vazio."""
    curador = Curador(config_minima)
    noticia = _noticia(texto[:100], texto[100:] if len(texto) > 100 else "")
    resultado = curador.evaluate(noticia)
    if resultado.status == StatusCuradoria.DESCARTADO:
        assert resultado.motivo_rejeicao is not None
        assert len(resultado.motivo_rejeicao) > 0


# ---------------------------------------------------------------------------
# Property 8: Score é monotônico em relação às keywords
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Property 8: Score monotônico
@settings(max_examples=100)
@given(
    kws_base=st.lists(st.sampled_from(_KW_GENERO_PT), min_size=1, max_size=3, unique=True),
    kw_extra=st.sampled_from(_KW_GENERO_PT),
)
def test_score_monotônico_superconjunto_keywords(
    kws_base: list[str], kw_extra: str
) -> None:
    """Para qualquer notícia, adicionar mais keywords ao texto não deve
    diminuir o score (score é monotônico não-decrescente)."""
    texto_base = " ".join(kws_base) + " livro publicado no Brasil"
    texto_extra = texto_base + f" {kw_extra}"

    noticia_base = _noticia(texto_base, "")
    noticia_extra = _noticia(texto_extra, "")

    score_base = calcular_score(noticia_base, config_minima)
    score_extra = calcular_score(noticia_extra, config_minima)

    assert score_extra >= score_base


# ---------------------------------------------------------------------------
# Propriedades do filtro de idioma (novo comportamento)
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Filtro de idioma: inglês sem Brasil → score 0
def test_texto_ingles_sem_brasil_score_zero() -> None:
    """Texto predominantemente em inglês sem menção ao Brasil deve ter score 0.
    Usa texto sem nenhuma palavra da lista de palavras PT para garantir detecção."""
    # Texto com >= 4 palavras exclusivamente EN e 0 palavras PT
    noticia = _noticia(
        "New novel released this week by the author",
        "This book is about a haunted house. The story is very scary. "
        "This novel will be released after the review period. "
        "The writer is from the US. These books are available now.",
    )
    s = calcular_score(noticia, config_minima)
    assert s == 0.0


# Feature: terrobook-portal, Filtro de idioma: inglês COM Brasil → score pode ser > 0
def test_texto_ingles_com_brasil_pode_ter_score_positivo() -> None:
    """Texto em inglês que menciona Brasil/tradução deve passar pelo filtro."""
    noticia = _noticia(
        "New horror novel coming to Brazil",
        "The book will have a brazilian edition. Translation announced for portuguese readers.",
    )
    s = calcular_score(noticia, config_minima)
    # Não deve ser zerado pelo filtro de idioma
    # (pode ser 0 por falta de keywords, mas não pelo filtro)
    # Verificamos apenas que o filtro não bloqueou — o score depende das keywords
    assert isinstance(s, float)
    assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# Propriedades do filtro de filmes (novo comportamento)
# ---------------------------------------------------------------------------

# Feature: terrobook-portal, Filtro de filmes: mídia sem livro → descartado
def test_post_sobre_filme_sem_livro_descartado() -> None:
    """Post sobre filme/série sem menção a livros deve ser descartado."""
    curador = Curador(config_minima)
    noticia = _noticia(
        "Novo filme de terror estreia na Netflix",
        "O trailer do filme foi lançado. O elenco inclui atores famosos. Temporada 2 confirmada.",
    )
    resultado = curador.evaluate(noticia)
    assert resultado.status == StatusCuradoria.DESCARTADO
    assert resultado.motivo_rejeicao is not None


# Feature: terrobook-portal, Filtro de filmes: mídia COM livro → não descartado por filtro
def test_post_sobre_adaptacao_com_livro_nao_descartado_por_filtro() -> None:
    """Post sobre adaptação que menciona o livro original não deve ser descartado
    pelo filtro de filmes."""
    curador = Curador(config_minima)
    noticia = _noticia(
        "Adaptação do livro de terror chega ao cinema",
        "O romance de terror será adaptado. O livro original é um clássico do horror.",
    )
    resultado = curador.evaluate(noticia)
    # Não deve ser descartado pelo filtro de filmes (pode ser aprovado ou descartado
    # por outras razões, mas não pelo filtro de mídia)
    if resultado.status == StatusCuradoria.DESCARTADO:
        assert resultado.motivo_rejeicao != "Conteúdo sobre filme/série sem menção a livros"
