"""Motor de filtros para o Gerador do Terrobook Portal.

Fornece funções puras para filtrar listas de ItemCurado por categoria e gênero.
Usado tanto na geração de páginas estáticas quanto nos templates Jinja2.
"""

from __future__ import annotations

from src.models import Categoria, Genero, ItemCurado


def filter_by_category(items: list[ItemCurado], categoria: Categoria) -> list[ItemCurado]:
    """Retorna exatamente os itens cuja categoria é igual à categoria selecionada.

    Sem falsos positivos (itens de outra categoria) nem falsos negativos
    (itens da categoria que ficam de fora). Property 9.

    Args:
        items: Lista de itens curados a filtrar.
        categoria: Categoria desejada.

    Returns:
        Sublista contendo apenas os itens com a categoria exata.
    """
    return [item for item in items if item.categoria == categoria]


def filter_by_genre(items: list[ItemCurado], genero: Genero) -> list[ItemCurado]:
    """Retorna exatamente os itens que contêm o gênero na lista de gêneros.

    Args:
        items: Lista de itens curados a filtrar.
        genero: Gênero desejado.

    Returns:
        Sublista contendo apenas os itens que possuem o gênero na lista generos.
    """
    return [item for item in items if genero in item.generos]
