"""Módulo de classificação de categorias para o Curador do Terrobook Portal."""

from src.models import Categoria, KeywordConfig, Noticia

# Indicadores de autoria nacional (busca case-insensitive no texto)
_INDICADORES_NACIONAL = ["nacional", "brasileiro", "brasileira", "brasil"]

# Prioridade de classificação
_PRIORIDADE = [
    "resenha",    # Resenha tem prioridade máxima — evita classificar como lançamento
    "traducao",
    "lancamento",
    "autor",
]


def classify(noticia: Noticia, config: KeywordConfig) -> Categoria | None:
    """Atribui a categoria mais adequada com base nas keywords de evento.

    Prioridade:
    1. "resenha"   → Categoria.NOTICIA_GERAL (resenhas não são lançamentos)
    2. "traducao"  → Categoria.TRADUCAO_ANUNCIADA
    3. "lancamento" → Categoria.LANCAMENTO_PREVISTO
    4. "autor" + indicador nacional → Categoria.NOVO_AUTOR_NACIONAL
    5. "autor" sem indicador nacional → Categoria.AUTOR_INTERNACIONAL_PT
    6. Nenhuma keyword de evento → Categoria.NOTICIA_GERAL

    Retorna None apenas quando score == 0 (notícia irrelevante).
    """
    texto = (noticia.titulo + " " + noticia.texto_resumido).lower()

    tem_keyword_genero = any(
        kw.lower() in texto
        for keywords in config.por_genero.values()
        for kw in keywords
    )
    tem_keyword_evento = any(
        kw.lower() in texto
        for keywords in config.por_evento.values()
        for kw in keywords
    )

    if not tem_keyword_genero and not tem_keyword_evento:
        return None

    eventos_encontrados: set[str] = set()
    for chave in _PRIORIDADE:
        keywords = config.por_evento.get(chave, [])
        if any(kw.lower() in texto for kw in keywords):
            eventos_encontrados.add(chave)

    # Resenha tem prioridade — não classificar como lançamento
    if "resenha" in eventos_encontrados:
        return Categoria.NOTICIA_GERAL

    if "traducao" in eventos_encontrados:
        return Categoria.TRADUCAO_ANUNCIADA

    if "lancamento" in eventos_encontrados:
        return Categoria.LANCAMENTO_PREVISTO

    if "autor" in eventos_encontrados:
        if any(ind in texto for ind in _INDICADORES_NACIONAL):
            return Categoria.NOVO_AUTOR_NACIONAL
        return Categoria.AUTOR_INTERNACIONAL_PT

    return Categoria.NOTICIA_GERAL
