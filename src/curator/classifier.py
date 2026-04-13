"""Módulo de classificação de categorias para o Curador do Terrobook Portal."""

from src.models import Categoria, KeywordConfig, Noticia

# Indicadores de autoria nacional (busca case-insensitive no texto)
_INDICADORES_NACIONAL = ["nacional", "brasileiro", "brasileira", "brasil"]

# Prioridade de classificação (menor índice = maior prioridade)
_PRIORIDADE = [
    "traducao",
    "lancamento",
    "autor",
]


def classify(noticia: Noticia, config: KeywordConfig) -> Categoria | None:
    """Atribui a categoria mais adequada com base nas keywords de evento.

    Algoritmo de prioridade:
    1. "traducao"  → Categoria.TRADUCAO_ANUNCIADA
    2. "lancamento" → Categoria.LANCAMENTO_PREVISTO
    3. "autor" + indicador nacional → Categoria.NOVO_AUTOR_NACIONAL
    4. "autor" sem indicador nacional → Categoria.AUTOR_INTERNACIONAL_PT
    5. Nenhuma keyword de evento → Categoria.NOTICIA_GERAL

    Retorna None apenas quando score == 0 (notícia irrelevante, sem nenhuma
    keyword de gênero ou evento presente no texto).

    Args:
        noticia: Notícia a ser classificada.
        config: Configuração de keywords com listas por gênero e por evento.

    Returns:
        Categoria atribuída, ou None se a notícia for irrelevante (score zero).
    """
    texto = (noticia.titulo + " " + noticia.texto_resumido).lower()

    # Verifica se há ao menos uma keyword de gênero ou evento no texto
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
        return None  # score == 0 → notícia irrelevante

    # Verifica presença de cada chave de evento na ordem de prioridade
    eventos_encontrados: set[str] = set()
    for chave in _PRIORIDADE:
        keywords = config.por_evento.get(chave, [])
        if any(kw.lower() in texto for kw in keywords):
            eventos_encontrados.add(chave)

    # Aplica prioridade: tradução > lançamento > autor
    if "traducao" in eventos_encontrados:
        return Categoria.TRADUCAO_ANUNCIADA

    if "lancamento" in eventos_encontrados:
        return Categoria.LANCAMENTO_PREVISTO

    if "autor" in eventos_encontrados:
        if any(ind in texto for ind in _INDICADORES_NACIONAL):
            return Categoria.NOVO_AUTOR_NACIONAL
        return Categoria.AUTOR_INTERNACIONAL_PT

    # Nenhuma keyword de evento, mas há keyword de gênero
    return Categoria.NOTICIA_GERAL
