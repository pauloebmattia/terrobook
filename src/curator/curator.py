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
        """Avalia uma notícia e retorna classificação + pontuação.

        Regras:
        - score == 0.0 → DESCARTADO, motivo_rejeicao preenchido
        - 0 < score < limiar_confianca → PENDENTE_REVISAO, categoria preenchida
        - score >= limiar_confianca → APROVADO, categoria preenchida
        - classify() retorna None mas score > 0 → usa Categoria.NOTICIA_GERAL
        """
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

        if score < self.config.limiar_confianca:
            return ResultadoCuradoria(
                noticia=noticia,
                status=StatusCuradoria.PENDENTE_REVISAO,
                score=score,
                categoria=categoria,
                motivo_rejeicao=None,
            )

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
