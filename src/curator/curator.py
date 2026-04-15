"""Módulo principal do Curador do Terrobook Portal."""

from pathlib import Path

import yaml

from src.curator import classifier, keyword_scorer
from src.models import Categoria, KeywordConfig, Noticia, ResultadoCuradoria, StatusCuradoria


class Curador:
    """Avalia relevância e classifica notícias com base em keywords configuradas."""

    def __init__(self, config: KeywordConfig) -> None:
        self.config = config

    def evaluate(self, noticia: Noticia) -> ResultadoCuradoria:
        """Avalia uma notícia e retorna classificação + pontuação."""

        # Filtro de filmes/séries: descartar posts sobre adaptações que não mencionam livros
        texto_lower = (noticia.titulo + " " + noticia.texto_resumido).lower()
        _TERMOS_MIDIA = ["filme", "série", "séries", "cinema", "netflix", "streaming",
                         "trailer", "elenco", "ator", "atriz", "diretor", "episódio",
                         "temporada", "movie", "film", "series", "tv show", "television"]
        _TERMOS_LIVRO = ["livro", "livros", "romance", "conto", "obra", "publicação",
                         "lançamento", "edição", "autor", "autora", "editora", "leitura",
                         "resenha", "book", "novel", "release", "publish"]
        eh_midia = any(t in texto_lower for t in _TERMOS_MIDIA)
        tem_livro = any(t in texto_lower for t in _TERMOS_LIVRO)
        if eh_midia and not tem_livro:
            return ResultadoCuradoria(
                noticia=noticia,
                status=StatusCuradoria.DESCARTADO,
                score=0.0,
                categoria=None,
                motivo_rejeicao="Conteúdo sobre filme/série sem menção a livros",
            )

        score = keyword_scorer.score(noticia, self.config)
        categoria = classifier.classify(noticia, self.config)

        if score == 0.0:
            return ResultadoCuradoria(
                noticia=noticia,
                status=StatusCuradoria.DESCARTADO,
                score=score,
                categoria=None,
                motivo_rejeicao="Nenhuma keyword relevante encontrada",
            )

        # score > 0: garante categoria não-nula
        if categoria is None:
            categoria = Categoria.NOTICIA_GERAL

        # Qualquer score > 0 é aprovado automaticamente
        # (PENDENTE_REVISAO reservado para revisão manual via CLI)
        return ResultadoCuradoria(
            noticia=noticia,
            status=StatusCuradoria.APROVADO,
            score=score,
            categoria=categoria,
            motivo_rejeicao=None,
        )

    @classmethod
    def from_config(cls, config_path: Path) -> "Curador":
        """Carrega keywords de um arquivo YAML e retorna uma instância de Curador.

        Args:
            config_path: Caminho para o arquivo keywords.yaml.

        Returns:
            Instância de Curador configurada.
        """
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        config = KeywordConfig(
            por_genero=data.get("por_genero", {}),
            por_evento=data.get("por_evento", {}),
            limiar_confianca=data.get("limiar_confianca", 0.6),
        )
        return cls(config)
