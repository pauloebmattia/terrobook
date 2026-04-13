# Plano de Implementação: Terrobook Portal

## Visão Geral

Implementação incremental do pipeline de curadoria automatizada do Terrobook Portal em Python 3.11+. Cada tarefa constrói sobre a anterior, culminando na integração completa do pipeline e no deploy via GitHub Actions.

## Tarefas

- [x] 1. Estrutura do projeto e modelos de dados
  - Criar estrutura de diretórios: `src/collector/`, `src/curator/`, `src/generator/`, `config/`, `data/`, `reports/`, `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/smoke/`
  - Implementar todos os dataclasses e enums em `src/models.py`: `Noticia`, `ItemCurado`, `FonteConfig`, `KeywordConfig`, `CollectionResult`, `ResultadoCuradoria`, `SourceError`, `BuildError`, `PipelineError`, `Categoria`, `Genero`, `StatusCuradoria`, `TipoFonte`
  - Criar arquivos de configuração iniciais: `config/sources.yaml`, `config/keywords.yaml`, `config/settings.yaml` com valores de exemplo cobrindo as categorias de fontes exigidas (editoras BR, portais de resenha, blogs, redes sociais, agregadores internacionais)
  - _Requisitos: 1.1, 1.2, 2.4, 2.6, 3.1, 6.1, 6.2_

- [x] 2. Coletor — coleta RSS/HTML e deduplicação
  - [x] 2.1 Implementar `src/collector/seen_urls.py` com carregamento/salvamento de `data/seen_urls.json` e método `add(url)` / `contains(url)`
    - _Requisitos: 1.6_

  - [ ]* 2.2 Escrever teste de propriedade para deduplicação por URL
    - **Property 3: Deduplicação por URL**
    - **Validates: Requisito 1.6**

  - [x] 2.3 Implementar `src/collector/rss_fetcher.py` com `fetch_rss(source: FonteConfig) -> list[Noticia]` usando `feedparser`; garantir que todos os campos obrigatórios (`url`, `titulo`, `data_publicacao`, `texto_resumido`) sejam preenchidos
    - _Requisitos: 1.2, 1.5_

  - [x] 2.4 Implementar `src/collector/html_fetcher.py` com `fetch_html(source: FonteConfig) -> list[Noticia]` usando `requests` + `BeautifulSoup` e seletores CSS configuráveis
    - _Requisitos: 1.2, 1.5_

  - [ ]* 2.5 Escrever teste de propriedade para preservação de campos obrigatórios
    - **Property 1: Coleta preserva campos obrigatórios**
    - **Validates: Requisito 1.2**

  - [x] 2.6 Implementar `src/collector/collector.py` com classe `Coletor`: método `run()` que itera sobre fontes, chama o fetcher adequado, aplica deduplicação, captura `SourceError` por fonte indisponível e retorna `CollectionResult`
    - _Requisitos: 1.1, 1.3, 1.4, 1.6_

  - [ ]* 2.7 Escrever teste de propriedade para resiliência a fontes indisponíveis
    - **Property 2: Resiliência a fontes indisponíveis**
    - **Validates: Requisito 1.4**

  - [ ]* 2.8 Escrever testes de exemplo para o Coletor em `tests/unit/test_collector.py`
    - Testar coleta RSS com feed mock válido
    - Testar coleta HTML com página mock
    - Testar comportamento com fonte retornando erro HTTP 500

- [x] 3. Checkpoint — Coletor funcional
  - Garantir que todos os testes do Coletor passem. Perguntar ao usuário se há dúvidas antes de continuar.

- [x] 4. Curador — scoring, classificação e triagem
  - [x] 4.1 Implementar `src/curator/keyword_scorer.py` com `score(noticia: Noticia, config: KeywordConfig) -> float` usando contagem ponderada de keywords por gênero e por tipo de evento; retornar valor entre 0.0 e 1.0
    - _Requisitos: 2.2, 2.3, 2.6_

  - [ ]* 4.2 Escrever teste de propriedade para consistência de classificação com keywords
    - **Property 4: Classificação de relevância é consistente com as keywords**
    - **Validates: Requisitos 2.2, 2.3**

  - [ ]* 4.3 Escrever teste de propriedade para monotonicidade do score
    - **Property 8: Score é monotônico em relação às keywords**
    - **Validates: Requisito 2.6**

  - [x] 4.4 Implementar `src/curator/classifier.py` com `classify(noticia: Noticia, config: KeywordConfig) -> Categoria | None` que atribui a categoria mais adequada com base nas keywords de evento
    - _Requisitos: 2.4_

  - [ ]* 4.5 Escrever teste de propriedade para itens aprovados sempre terem categoria
    - **Property 5: Itens aprovados sempre têm categoria**
    - **Validates: Requisito 2.4**

  - [x] 4.6 Implementar `src/curator/curator.py` com classe `Curador`: método `evaluate(noticia) -> ResultadoCuradoria` que combina scorer e classifier, aplica limiar de confiança para decidir entre `APROVADO`, `PENDENTE_REVISAO` e `DESCARTADO`, e preenche `motivo_rejeicao` para itens descartados
    - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7_

  - [ ]* 4.7 Escrever teste de propriedade para baixa confiança implicar revisão manual
    - **Property 6: Baixa confiança implica revisão manual**
    - **Validates: Requisito 2.5**

  - [ ]* 4.8 Escrever teste de propriedade para itens descartados sempre terem motivo
    - **Property 7: Itens descartados sempre têm motivo de rejeição**
    - **Validates: Requisito 2.7**

  - [ ]* 4.9 Escrever testes de exemplo para o Curador em `tests/unit/test_curator.py`
    - Testar notícia claramente relevante (score alto, aprovada)
    - Testar notícia claramente irrelevante (descartada com motivo)
    - Testar notícia com score limítrofe (pendente de revisão)

- [x] 5. Checkpoint — Curador funcional
  - Garantir que todos os testes do Curador passem. Perguntar ao usuário se há dúvidas antes de continuar.

- [x] 6. Persistência de dados
  - [x] 6.1 Implementar `src/storage/raw_store.py` para salvar/carregar notícias brutas em `data/raw/` como JSON por data
    - _Requisitos: 4.2, 7.2_

  - [x] 6.2 Implementar `src/storage/curated_store.py` para salvar/carregar `ItemCurado` em `data/curated/`, `data/pending_review/` e `data/discarded/` como JSON por item
    - _Requisitos: 2.7, 4.2, 6.4, 7.2_

  - [x] 6.3 Implementar `src/storage/report_writer.py` para gerar `reports/report_YYYY-MM-DD.json` e `reports/pending_review_YYYY-MM-DD.json` ao final de cada ciclo
    - _Requisitos: 6.3, 6.6_

- [x] 7. Gerador de site estático
  - [x] 7.1 Criar templates Jinja2 em `src/generator/templates/`: `base.html` (layout escuro temático, responsivo), `index.html`, `detail.html`, `category.html`
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.2 Implementar `src/generator/filter_engine.py` com `filter_by_category(items, categoria)` e `filter_by_genre(items, genero)` para uso nos templates e na geração de páginas de categoria/gênero
    - _Requisitos: 3.5, 3.6_

  - [ ]* 7.3 Escrever teste de propriedade para filtro por categoria
    - **Property 9: Filtro por categoria é exato**
    - **Validates: Requisitos 3.5, 3.6**

  - [x] 7.4 Implementar `src/generator/generator.py` com classe `Gerador`: métodos `render_index`, `render_detail`, `render_rss`, `render_json_api` e `build(items) -> BuildResult`; isolar erros por item (capturar `BuildError`, continuar geração)
    - _Requisitos: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.2, 5.4, 5.6_

  - [ ]* 7.5 Escrever teste de propriedade para página de detalhe com todos os campos disponíveis
    - **Property 10: Página de detalhe contém todos os campos disponíveis do item**
    - **Validates: Requisitos 3.2, 3.3, 3.4, 5.4**

  - [ ]* 7.6 Escrever teste de propriedade para artefatos de saída válidos (RSS e JSON)
    - **Property 11: Gerador produz artefatos de saída válidos**
    - **Validates: Requisitos 4.4, 4.5**

  - [ ]* 7.7 Escrever teste de propriedade para resiliência a itens problemáticos
    - **Property 12: Resiliência a itens problemáticos na geração**
    - **Validates: Requisito 4.6**

  - [ ]* 7.8 Escrever teste de propriedade para ordenação cronológica decrescente
    - **Property 13: Ordenação cronológica decrescente na página inicial**
    - **Validates: Requisito 5.2**

  - [ ]* 7.9 Escrever teste de propriedade para itens relacionados na página de detalhe
    - **Property 14: Itens relacionados aparecem na página de detalhe**
    - **Validates: Requisito 5.6**

  - [ ]* 7.10 Escrever testes de exemplo para o Gerador em `tests/unit/test_generator.py`
    - Testar renderização de index com lista de itens mock
    - Testar renderização de detalhe com campos opcionais ausentes
    - Testar geração de RSS com XML válido

- [x] 8. Checkpoint — Gerador funcional
  - Garantir que todos os testes do Gerador passem. Perguntar ao usuário se há dúvidas antes de continuar.

- [x] 9. Relatórios e notificações ao Administrador
  - [x] 9.1 Implementar geração do relatório de revisão pendente em `src/storage/report_writer.py` (já criado em 6.3): garantir que lista todos e somente os itens `PENDENTE_REVISAO`
    - _Requisitos: 6.3_

  - [ ]* 9.2 Escrever teste de propriedade para relatório de revisão
    - **Property 15: Relatório de revisão contém todos os itens pendentes**
    - **Validates: Requisito 6.3**

  - [ ]* 9.3 Escrever teste de propriedade para relatório de erro
    - **Property 16: Relatório de erro contém informações completas**
    - **Validates: Requisito 6.6**

- [x] 10. CLI de administração
  - Implementar `src/cli.py` usando `argparse` com subcomandos: `collect`, `curate`, `generate`, `approve <id>`, `reject <id> --motivo`, `edit <id>`, `run` (pipeline completo)
  - _Requisitos: 6.4, 6.5_

- [x] 11. Integração do pipeline completo
  - [x] 11.1 Implementar `src/pipeline.py` com função `run_pipeline()` que orquestra Coletor → Curador → Gerador → ReportWriter em sequência, capturando `PipelineError` por etapa e gerando relatório de erro ao final
    - _Requisitos: 6.6, 1.3_

  - [x]* 11.2 Escrever testes de integração em `tests/integration/test_pipeline.py`
    - Testar pipeline completo com fontes mock (coleta → curadoria → geração)
    - Testar pipeline com fonte indisponível (deve continuar e reportar erro)
    - Testar pipeline com item problemático na geração (deve continuar e reportar erro)
    - _Requisitos: 1.4, 4.6, 6.6_

- [x] 12. GitHub Actions e deploy
  - Criar `.github/workflows/pipeline.yml` com jobs `collect`, `curate`, `generate`, `deploy` e `report`; configurar `schedule` com cron diário e `workflow_dispatch` para acionamento manual; configurar deploy para GitHub Pages
  - Criar arquivos de configuração de deploy: `vercel.json` e `netlify.toml` com configurações mínimas para site estático
  - _Requisitos: 1.3, 4.3, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 13. Testes de smoke
  - Implementar `tests/smoke/test_config.py` verificando: configuração padrão contém fontes de todas as categorias exigidas, workflow do GitHub Actions contém cron diário e `workflow_dispatch`, site gerado não referencia servidor backend, dependências não incluem banco de dados em execução contínua, arquivos de deploy estão presentes
  - _Requisitos: 1.1, 4.3, 7.1, 7.2, 7.3_

- [x] 14. Checkpoint final — Garantir que todos os testes passem
  - Executar suite completa de testes (unit, property, integration, smoke). Perguntar ao usuário se há dúvidas antes de concluir.

## Notas

- Tarefas marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada tarefa referencia os requisitos específicos para rastreabilidade
- Os testes de propriedade usam `hypothesis` com `@settings(max_examples=100)`
- O armazenamento é inteiramente baseado em arquivos JSON/YAML — sem banco de dados
- O pipeline é stateless entre execuções; o estado persiste apenas nos arquivos de `data/`
