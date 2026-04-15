"""Módulo de scoring de keywords para o Curador do Terrobook Portal."""

from src.models import KeywordConfig, Noticia

_PESO_EVENTO = 2
_PESO_GENERO = 1

# Palavras comuns em português — presença indica texto em PT
_PALAVRAS_PT = [
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
    "um", "uma", "uns", "umas", "que", "com", "por", "para", "como",
    "mas", "ou", "se", "ao", "às", "pelo", "pela", "pelos", "pelas",
    "este", "esta", "esse", "essa", "isso", "isto", "aqui", "ali",
    "livro", "livros", "autor", "autora", "editora", "lançamento",
    "resenha", "leitura", "história", "romance", "conto", "obra",
    "publicação", "leitor", "leitores", "página", "capítulo",
]

# Palavras exclusivamente em inglês — presença forte indica texto em EN
_PALAVRAS_EN_EXCLUSIVAS = [
    " the ", " a ", " an ", " is ", " are ", " was ", " were ",
    " has ", " have ", " had ", " will ", " would ", " could ",
    " should ", " this ", " that ", " these ", " those ",
    " with ", " from ", " into ", " about ", " after ", " before ",
    " their ", " there ", " where ", " when ", " which ", " who ",
    " book ", " books ", " author ", " novel ", " story ", " read ",
    " review ", " release ", " publisher ", " chapter ",
]


def _detectar_idioma(texto: str) -> str:
    """Detecta se o texto é predominantemente em português ou inglês.

    Returns:
        'pt' se português, 'en' se inglês, 'unknown' se inconclusivo.
    """
    texto_lower = " " + texto.lower() + " "

    hits_pt = sum(1 for w in _PALAVRAS_PT if w in texto_lower)
    hits_en = sum(1 for w in _PALAVRAS_EN_EXCLUSIVAS if w in texto_lower)

    if hits_pt >= 3:
        return "pt"
    if hits_en >= 4 and hits_pt == 0:
        return "en"
    return "unknown"


def score(noticia: Noticia, config: KeywordConfig) -> float:
    """Calcula pontuação de relevância de uma notícia com base em keywords.

    Retorna 0.0 para textos detectados como predominantemente em inglês,
    a menos que mencionem explicitamente edição brasileira/portuguesa.

    Args:
        noticia: Notícia a ser avaliada.
        config: Configuração de keywords com listas por gênero e por evento.

    Returns:
        Valor entre 0.0 e 1.0 representando a relevância da notícia.
    """
    texto_completo = noticia.titulo + " " + noticia.texto_resumido
    texto = texto_completo.lower()

    # Filtro de idioma: descartar inglês sem menção ao Brasil/Portugal
    idioma = _detectar_idioma(texto_completo)
    if idioma == "en":
        menciona_pt = any(kw in texto for kw in [
            "brasil", "brazil", "português", "portuguese", "brazilian",
            "edição brasileira", "tradução", "translation", "portuguese edition",
        ])
        if not menciona_pt:
            return 0.0

    hits_ponderados = 0
    total_ponderado = 0

    for keywords in config.por_genero.values():
        for kw in keywords:
            total_ponderado += _PESO_GENERO
            if kw.lower() in texto:
                hits_ponderados += _PESO_GENERO

    for keywords in config.por_evento.values():
        for kw in keywords:
            total_ponderado += _PESO_EVENTO
            if kw.lower() in texto:
                hits_ponderados += _PESO_EVENTO

    if total_ponderado == 0:
        return 0.0

    return min(1.0, hits_ponderados / total_ponderado)
