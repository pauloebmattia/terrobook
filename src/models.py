"""Modelos de dados do Terrobook Portal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Categoria(str, Enum):
    TRADUCAO_ANUNCIADA = "Tradução Anunciada"
    LANCAMENTO_PREVISTO = "Lançamento Previsto"
    NOVO_AUTOR_NACIONAL = "Novo Autor Nacional"
    AUTOR_INTERNACIONAL_PT = "Autor Internacional em Português"
    NOTICIA_GERAL = "Notícia Geral do Gênero"


class Genero(str, Enum):
    TERROR = "terror"
    SUSPENSE = "suspense"
    THRILLER = "thriller"
    MISTERIO = "misterio"
    WEIRD_FICTION = "weird_fiction"
    TRUE_CRIME = "true_crime"


class StatusCuradoria(str, Enum):
    APROVADO = "aprovado"
    PENDENTE_REVISAO = "pendente_revisao"
    DESCARTADO = "descartado"


class TipoFonte(str, Enum):
    RSS = "rss"
    HTML = "html"


@dataclass
class Noticia:
    url: str
    titulo: str
    data_publicacao: datetime
    fonte_id: str
    texto_resumido: str
    coletado_em: datetime
    raw_html: str | None = None


@dataclass
class ItemCurado:
    id: str
    noticia: Noticia
    categoria: Categoria
    generos: list[Genero]
    score: float
    aprovado_em: datetime
    aprovado_por: str
    titulo_original: str | None = None
    autor: str | None = None
    editora: str | None = None
    data_prevista: str | None = None
    sinopse: str | None = None
    itens_relacionados: list[str] = field(default_factory=list)


@dataclass
class FonteConfig:
    id: str
    nome: str
    url: str
    tipo: TipoFonte
    ativo: bool
    seletores: dict | None = None
    ultima_varredura: datetime | None = None


@dataclass
class KeywordConfig:
    por_genero: dict[str, list[str]]
    por_evento: dict[str, list[str]]
    limiar_confianca: float = 0.6


@dataclass
class CollectionResult:
    collected: list[Noticia]
    skipped_duplicates: int
    errors: list[SourceError]


@dataclass
class ResultadoCuradoria:
    noticia: Noticia
    status: StatusCuradoria
    score: float
    categoria: Categoria | None
    motivo_rejeicao: str | None


@dataclass
class SourceError:
    fonte_id: str
    url: str
    etapa: str
    mensagem: str
    timestamp: datetime


@dataclass
class BuildError:
    item_id: str
    etapa: str
    mensagem: str
    timestamp: datetime


@dataclass
class PipelineError:
    etapa: str
    mensagem: str
    timestamp: datetime
    fonte_id: str | None = None
    traceback: str | None = None
