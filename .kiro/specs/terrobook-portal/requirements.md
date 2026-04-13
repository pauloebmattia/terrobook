# Documento de Requisitos

## Introdução

O Terrobook é um portal de curadoria de notícias voltado para amantes da literatura de terror, suspense, thriller, mistério, weird fiction e true crime. O foco principal é manter os leitores atualizados sobre lançamentos em português — traduções em andamento, edições nacionais previstas, novos autores brasileiros em destaque e autores internacionais que ganham edições no Brasil. O portal automatiza a varredura de fontes relevantes, aplica critérios de curadoria para filtrar o conteúdo pertinente ao nicho e publica as notícias em um site estático hospedado gratuitamente.

## Glossário

- **Portal**: O site público do Terrobook acessível pelos leitores.
- **Coletor**: Componente responsável por varrer fontes externas e extrair notícias brutas.
- **Curador**: Componente (automatizado ou assistido) responsável por avaliar se uma notícia se enquadra no escopo do Terrobook.
- **Notícia**: Artigo, post ou anúncio coletado de uma fonte externa.
- **Item_Curado**: Notícia aprovada pelo Curador e publicada no Portal.
- **Fonte**: Portal, blog, editora ou rede social monitorada pelo Coletor.
- **Escopo**: Conjunto de gêneros literários cobertos — terror, suspense, thriller, mistério, weird fiction e true crime.
- **Lançamento_PT**: Livro publicado ou previsto em língua portuguesa (tradução ou obra nacional).
- **Administrador**: Usuário responsável por configurar fontes, revisar curadoria e publicar conteúdo.
- **Leitor**: Usuário final que consome o conteúdo publicado no Portal.
- **Feed_Estático**: Arquivo gerado (JSON/RSS) que representa os itens curados mais recentes.
- **Site_Estático**: Conjunto de arquivos HTML/CSS/JS gerados a partir do Feed_Estático e publicados em plataforma de hospedagem gratuita.

---

## Requisitos

### Requisito 1: Varredura de Fontes de Notícias

**User Story:** Como Administrador, quero que o Coletor varra automaticamente fontes relevantes, para que eu não precise buscar manualmente notícias sobre lançamentos no nicho.

#### Critérios de Aceitação

1. THE Coletor SHALL monitorar ao menos as seguintes categorias de fontes: editoras brasileiras especializadas (ex: Darkside Books, Intrínseca, Aleph, Novo Século), portais de resenhas literárias (ex: Goodreads, Skoob, Leitores.com.br), blogs e canais especializados em terror/suspense, perfis e páginas oficiais de editoras em redes sociais, e agregadores internacionais como Publishers Weekly e Tor.com.
2. WHEN a varredura é iniciada, THE Coletor SHALL consultar cada Fonte cadastrada e extrair título, data de publicação, URL de origem e texto resumido de cada Notícia encontrada.
3. THE Coletor SHALL executar a varredura de forma agendada com frequência mínima de uma vez por dia.
4. IF uma Fonte estiver indisponível durante a varredura, THEN THE Coletor SHALL registrar o erro, pular a Fonte e continuar a varredura nas demais Fontes.
5. THE Coletor SHALL suportar ao menos dois mecanismos de coleta: leitura de feeds RSS/Atom e raspagem de páginas HTML via seletores configuráveis.
6. WHEN uma Notícia já coletada anteriormente é encontrada novamente, THE Coletor SHALL ignorá-la para evitar duplicatas, usando a URL de origem como identificador único.

---

### Requisito 2: Curadoria e Avaliação de Relevância

**User Story:** Como Administrador, quero que o Curador avalie automaticamente cada Notícia coletada, para que apenas conteúdo dentro do Escopo seja publicado no Portal.

#### Critérios de Aceitação

1. WHEN uma Notícia é coletada, THE Curador SHALL avaliá-la contra os critérios de Escopo antes de qualquer publicação.
2. THE Curador SHALL classificar uma Notícia como relevante se ela mencionar ao menos um dos seguintes elementos: lançamento ou previsão de lançamento de livro em português dentro do Escopo, tradução em andamento ou anunciada para o português, novo autor brasileiro de terror/suspense/thriller/mistério/weird fiction/true crime ganhando destaque, ou autor internacional com nova edição em português.
3. THE Curador SHALL classificar uma Notícia como irrelevante se o conteúdo tratar exclusivamente de gêneros fora do Escopo (ex: romance, autoajuda, ficção científica sem elementos de terror/suspense) ou de lançamentos exclusivamente em idioma estrangeiro sem menção a edição em português.
4. WHEN o Curador classifica uma Notícia como relevante, THE Curador SHALL atribuir ao menos uma categoria dentre: "Tradução Anunciada", "Lançamento Previsto", "Novo Autor Nacional", "Autor Internacional em Português" ou "Notícia Geral do Gênero".
5. WHERE a avaliação automática apresentar baixa confiança (pontuação abaixo do limiar configurado), THE Curador SHALL marcar a Notícia para revisão manual pelo Administrador antes da publicação.
6. THE Curador SHALL utilizar uma lista de palavras-chave configurável por gênero e por tipo de evento (lançamento, tradução, autor) para calcular a pontuação de relevância.
7. IF uma Notícia for marcada como irrelevante pelo Curador, THEN THE Curador SHALL armazená-la em fila de descartados com o motivo da rejeição, permitindo auditoria posterior pelo Administrador.

---

### Requisito 3: Tipos de Conteúdo Publicado

**User Story:** Como Leitor, quero encontrar diferentes tipos de notícias sobre o nicho, para que eu possa me manter atualizado sobre traduções, lançamentos e autores relevantes.

#### Critérios de Aceitação

1. THE Portal SHALL exibir itens das seguintes categorias de conteúdo: traduções em andamento ou anunciadas para o português, lançamentos previstos com data confirmada ou estimada, novos autores nacionais em destaque dentro do Escopo, autores internacionais com nova edição em português, e notícias gerais do gênero (prêmios, eventos, adaptações).
2. WHEN um Item_Curado é do tipo "Tradução Anunciada", THE Portal SHALL exibir título original, autor, editora responsável pela tradução e previsão de lançamento quando disponível.
3. WHEN um Item_Curado é do tipo "Lançamento Previsto", THE Portal SHALL exibir título em português, autor, editora, data prevista e sinopse quando disponível.
4. WHEN um Item_Curado é do tipo "Novo Autor Nacional" ou "Autor Internacional em Português", THE Portal SHALL exibir nome do autor, gênero literário principal e ao menos um título associado.
5. THE Portal SHALL permitir ao Leitor filtrar os itens exibidos por categoria de conteúdo.
6. THE Portal SHALL permitir ao Leitor filtrar os itens exibidos por gênero literário (terror, suspense, thriller, mistério, weird fiction, true crime).

---

### Requisito 4: Geração do Site Estático

**User Story:** Como Administrador, quero que o Portal seja gerado como um site estático, para que eu possa hospedá-lo gratuitamente sem necessidade de servidor backend em execução contínua.

#### Critérios de Aceitação

1. THE Portal SHALL ser gerado como um conjunto de arquivos estáticos (HTML, CSS, JavaScript) a partir dos itens curados armazenados.
2. WHEN novos itens são aprovados pelo Curador, THE Portal SHALL regenerar os arquivos estáticos afetados sem necessidade de reconstruir o site inteiro.
3. THE Portal SHALL ser compatível com hospedagem gratuita nas plataformas GitHub Pages, Vercel e Netlify sem configuração adicional de servidor.
4. THE Portal SHALL gerar um arquivo RSS/Atom atualizado a cada ciclo de publicação, permitindo que Leitores assinem o feed em leitores externos.
5. THE Portal SHALL gerar um arquivo JSON público com os itens curados mais recentes, servindo como API de leitura para integrações futuras.
6. IF a geração do site falhar por erro em um Item_Curado específico, THEN THE Portal SHALL ignorar o item problemático, registrar o erro e concluir a geração com os demais itens.

---

### Requisito 5: Interface Visual do Portal

**User Story:** Como Leitor, quero uma interface clara e temática, para que a experiência de navegação seja agradável e coerente com o universo da literatura de terror/suspense.

#### Critérios de Aceitação

1. THE Portal SHALL adotar uma paleta de cores escura como padrão, com cores de destaque que remetam ao universo do terror e suspense (ex: tons de vermelho escuro, âmbar ou verde musgo sobre fundo escuro).
2. THE Portal SHALL exibir na página inicial os itens curados mais recentes em ordem cronológica decrescente, com no mínimo título, categoria, data e trecho resumido visíveis sem necessidade de clique.
3. THE Portal SHALL ser responsivo, adaptando o layout para dispositivos móveis, tablets e desktops sem perda de funcionalidade.
4. THE Portal SHALL exibir uma página de detalhe para cada Item_Curado contendo todas as informações disponíveis e link para a Fonte original.
5. THE Portal SHALL incluir uma seção de navegação por categoria e por gênero acessível a partir de qualquer página.
6. WHEN o Leitor acessa a página de um Item_Curado, THE Portal SHALL exibir itens relacionados da mesma categoria ou gênero ao final da página.
7. THE Portal SHALL carregar a página inicial em menos de 3 segundos em conexão de 10 Mbps, dado que o conteúdo é estático.

---

### Requisito 6: Administração e Configuração

**User Story:** Como Administrador, quero gerenciar fontes, revisar curadoria e publicar conteúdo, para que eu tenha controle sobre o que é exibido no Portal.

#### Critérios de Aceitação

1. THE Administrador SHALL ser capaz de adicionar, editar e remover Fontes monitoradas pelo Coletor por meio de um arquivo de configuração versionável.
2. THE Administrador SHALL ser capaz de ajustar a lista de palavras-chave e o limiar de confiança do Curador por meio de arquivo de configuração.
3. WHEN há itens pendentes de revisão manual, THE Administrador SHALL ser notificado por meio de relatório gerado ao final de cada ciclo de varredura.
4. THE Administrador SHALL ser capaz de aprovar, rejeitar ou editar manualmente qualquer Item_Curado antes da publicação.
5. THE Administrador SHALL ser capaz de acionar manualmente a varredura, a curadoria e a geração do site sem aguardar o agendamento automático.
6. IF o ciclo automatizado falhar em qualquer etapa, THEN THE Administrador SHALL receber um relatório de erro detalhado com a etapa, a Fonte e a mensagem de falha.

---

### Requisito 7: Hospedagem e Publicação

**User Story:** Como Administrador, quero publicar o Portal em uma plataforma gratuita, para que o site fique disponível publicamente sem custo de infraestrutura.

#### Critérios de Aceitação

1. THE Portal SHALL ser publicável via GitHub Actions em repositório público ou privado, com deploy automático para GitHub Pages, Vercel ou Netlify a cada ciclo de geração.
2. THE Portal SHALL funcionar integralmente sem banco de dados em execução contínua, utilizando arquivos JSON ou YAML como armazenamento dos itens curados.
3. THE Portal SHALL operar dentro dos limites gratuitos das plataformas de hospedagem suportadas (GitHub Pages: sem limite de banda para sites estáticos; Vercel/Netlify: tier gratuito).
4. WHEN o deploy é concluído com sucesso, THE Portal SHALL estar acessível publicamente em menos de 5 minutos após o término da geração dos arquivos estáticos.
5. THE Portal SHALL suportar domínio personalizado configurado pelo Administrador nas plataformas suportadas, sem alteração no processo de geração.
