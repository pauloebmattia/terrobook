"""Módulo de scoring de keywords para o Curador do Terrobook Portal."""

from src.models import KeywordConfig, Noticia

# Peso relativo das keywords de evento em relação às de gênero
_PESO_EVENTO = 2
_PESO_GENERO = 1


def score(noticia: Noticia, config: KeywordConfig) -> float:
    """Calcula pontuação de relevância de uma notícia com base em keywords.

    Algoritmo:
    - Busca case-insensitive de keywords no texto combinado (titulo + texto_resumido)
    - Keywords de evento têm peso 2x em relação a keywords de gênero
    - Normalização: score = min(1.0, hits_ponderados / total_keywords_ponderadas)

    Args:
        noticia: Notícia a ser avaliada.
        config: Configuração de keywords com listas por gênero e por evento.

    Returns:
        Valor entre 0.0 e 1.0 representando a relevância da notícia.
    """
    texto = (noticia.titulo + " " + noticia.texto_resumido).lower()

    hits_ponderados = 0
    total_ponderado = 0

    # Keywords de gênero — peso 1
    for keywords in config.por_genero.values():
        for kw in keywords:
            total_ponderado += _PESO_GENERO
            if kw.lower() in texto:
                hits_ponderados += _PESO_GENERO

    # Keywords de evento — peso 2
    for keywords in config.por_evento.values():
        for kw in keywords:
            total_ponderado += _PESO_EVENTO
            if kw.lower() in texto:
                hits_ponderados += _PESO_EVENTO

    if total_ponderado == 0:
        return 0.0

    return min(1.0, hits_ponderados / total_ponderado)
