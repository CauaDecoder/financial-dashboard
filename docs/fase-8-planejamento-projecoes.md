# Fase 8 - Planejamento, orcamento e projecoes

## Objetivo

Adicionar o primeiro bloco de recursos avancados de planejamento financeiro sem
introduzir dependencias externas, segredos em codigo ou automacoes irreversiveis.

## Entregue neste incremento

- Tabelas locais `budgets` e `categorization_rules`.
- Cadastro e atualizacao de orcamento mensal por categoria e centro de custo.
- Distribuicao de orcamento anual em 12 meses, com fechamento exato em centavos.
- Distribuicao sazonal de orcamento anual por pesos mensais positivos.
- Comparativo orcado vs realizado para o mes selecionado.
- Metas anuais por categoria e centro de custo com total realizado, variacao e
  barra de progresso.
- Grafico nativo Qt Charts de metas anuais, comparando meta vs realizado.
- Projecao diaria de fluxo de caixa com titulos a pagar e receber em aberto.
- Grafico nativo Qt Charts da projecao de caixa acumulada.
- Regras locais de categorizacao por palavra-chave, tipo de lancamento,
  categoria, centro de custo e prioridade.
- Aplicacao manual de sugestoes de categorizacao em lancamentos e titulos.
- Aplicacao assistida das mesmas regras no wizard de importacao quando categoria
  ou centro de custo vierem vazios na planilha.
- Relatorio CSV da pre-visualizacao de importacao separando categorizacao
  informada e sugerida.
- Dashboard avancado com rankings por categoria, resultado por centro de custo e
  alertas de vencimento.
- Graficos nativos Qt Charts no dashboard avancado para categorias e resultado
  por centro de custo.
- Perfis personalizados de dashboard com periodo, limite de linhas, janela de
  alertas e secoes visiveis.
- Tabelas locais `sensitive_operation_requests` e
  `sensitive_operation_approvals` para preparar operacoes sensiveis com
  aprovacao dupla.
- Servico local de solicitacao, aprovacao, rejeicao e cancelamento de operacoes
  sensiveis, ainda sem chamadas externas de escrita.
- Tela "Aprovacoes sensiveis" para listar, filtrar, detalhar, criar, aprovar,
  rejeitar e cancelar solicitacoes locais.
- Tabela local `sensitive_operation_executions` para registrar tentativas de
  execucao idempotente de solicitacoes aprovadas.
- Executor idempotente para escrita futura no Asaas, coberto por mocks,
  dependente de aprovacao dupla e desligado por padrao por configuracao.
- Historico de execucoes/tentativas exibido no detalhe da tela "Aprovacoes
  sensiveis".
- O detalhe da tela "Aprovacoes sensiveis" omite a resposta bruta da API e
  oferece exportacao de evidencia local pos-execucao sem credenciais.
- A mesma tela exporta pacote ZIP de homologacao Asaas com checklist,
  prontidao, evidencia e manifesto, sem chamada externa.
- Checagem local de prontidao de execucao exibida no detalhe da solicitacao,
  indicando bloqueios de configuracao, aprovacao ou tentativa ja registrada
  antes de qualquer chamada externa.
- Exportacao de prontidao local pela tela "Aprovacoes sensiveis", sem token e
  sem chamada externa.
- Comando administrativo `asaas-readiness --request-id` para exportar JSON local
  de prontidao da solicitacao Asaas, sem chamada externa e sem token.
- Transporte HTTP de escrita Asaas com HTTPS obrigatorio, metodo controlado e
  mensagens de erro sem token, usado apenas pelo comando administrativo.
- Execucao Sandbox pela tela "Aprovacoes sensiveis", com bloqueio de producao,
  confirmacao explicita digitando `SANDBOX`, auditoria e idempotencia pelo ID
  da solicitacao.
- Comando administrativo `asaas-execute --confirm-sandbox --request-id` para
  executar solicitacao Asaas aprovada em Sandbox opt-in, bloqueando producao e
  exportando apenas resumo local sem credenciais.
- Comando administrativo `asaas-execution-report --request-id` para exportar
  evidencia local pos-execucao sem token, payload da solicitacao ou resposta
  bruta da API.
- Comando administrativo `asaas-validation-package --request-id` para gerar um
  ZIP local de homologacao Sandbox com prontidao, evidencia, checklist e
  manifesto SHA-256.
- Comando administrativo `asaas-verify-package --package` para validar arquivos,
  hashes, flags de seguranca e marcadores proibidos do pacote Asaas.
- Comando administrativo `asaas-review-summary --package` para gerar resumo
  Markdown de aceite dos gates locais, sem chamar API nem expor dados sensiveis.
- Tela "Configuracoes" com diagnostico local de implantacao, indicando backend
  de banco, prontidao offline, pendencias para uso em rede/PostgreSQL e status
  seguro das integracoes sem exibir segredos.
- Exportacao local de prontidao de uso em rede pela tela "Configuracoes" e pelo
  comando `network-readiness`, bloqueando SQLite multi-instalacao e sem abrir
  conexao externa.
- Exportacao local de pacote ZIP de homologacao de rede pela tela
  "Configuracoes" e pelo comando `network-validation-package`, reunindo
  prontidao, checklist e manifesto SHA-256.
- Comando administrativo `network-verify-package --package` para validar
  arquivos, hashes, flags de seguranca e marcadores proibidos do pacote de rede.
- Comando administrativo `network-review-summary --package` para gerar resumo
  Markdown de aceite dos gates locais de rede, sem chamada externa.
- Botoes em "Configuracoes" para verificar pacote de rede e exportar resumo de
  aceite a partir do ZIP gerado localmente.
- Preflight local do banco SQLite em "Configuracoes", com versao de schema,
  `PRAGMA quick_check`, chaves estrangeiras, modo WAL e contagem de tabelas
  criticas antes de qualquer ensaio de migracao.
- Exportacao local de roteiro Markdown para ensaio de migracao SQLite ->
  PostgreSQL, gerado a partir do preflight e sem segredos.
- Exportacao local de inventario JSON de schema SQLite, contendo tabelas,
  colunas, indices, chaves estrangeiras e contagens criticas, sem linhas de
  dados financeiros.
- Exportacao local de relatorio Markdown de compatibilidade PostgreSQL, com
  achados sobre schema, integridade e campos monetarios em centavos.
- Exportacao local de plano JSON de carga PostgreSQL, ordenando tabelas por
  dependencias de chaves estrangeiras e sinalizando ciclos antes do adapter.
- Exportacao local de contrato JSON do adapter PostgreSQL, com mapeamento de
  colunas, tipos, chaves, indices, estrategia de insercao e checagens pos-carga.
- Exportacao local de plano JSON de execucao de homologacao PostgreSQL, com
  fases, operacoes estruturadas e parametros nomeados para o adapter futuro.
- Exportacao local de preflight JSON do runner PostgreSQL futuro, validando
  guardas de seguranca sem abrir conexao externa nem executar migracao.
- Configuracao `.env` separada para runner de homologacao PostgreSQL
  (`POSTGRES_REHEARSAL_DATABASE_URL` e
  `POSTGRES_REHEARSAL_ENABLE_EXECUTION=false` por padrao), sem trocar o
  `DATABASE_URL` operacional.
- Exportacao local de prontidao JSON do runner PostgreSQL opt-in, com motivos
  de bloqueio, URL alvo mascarada e flag de execucao desligada por padrao.
- Contrato de execucao PostgreSQL com transporte injetavel para homologacao,
  sem driver de rede embutido, sem UI de execucao e bloqueado em producao.
- Runner isolado de homologacao PostgreSQL para carregar linhas da SQLite em um
  alvo injetado, aplicar blueprint revisado, resetar identities e validar
  contagens, coberto por alvo fake sem rede.
- Alvo concreto SQLAlchemy para homologacao PostgreSQL, recebendo uma conexao ja
  aberta pelo ambiente opt-in, com inserts parametrizados, bloqueio de alvo nao
  vazio e reset de identity.
- Orquestrador opt-in SQLAlchemy para abrir a conexao de homologacao a partir do
  `.env` somente depois das travas de prontidao, executando o runner em
  transacao e retornando apenas URL mascarada e resumo tecnico.
- Acao administrativa local para executar a homologacao PostgreSQL opt-in e
  gravar relatorio Markdown com URL mascarada, tabelas carregadas, tabelas
  validadas e totais, sem expor linhas financeiras.
- Comando administrativo `postgres-rehearsal --confirm-disposable-target` para
  rodar a acao fora da UI comum, exigindo confirmacao explicita de alvo
  descartavel e mantendo credenciais apenas no `.env` local.
- Comando administrativo `postgres-readiness` para gerar a prontidao JSON local
  antes da homologacao, sem abrir conexao externa e sem criar usuario inicial.
- Checagem de prontidao do runner PostgreSQL para bloquear a execucao quando
  nenhum driver `psycopg`/`psycopg2` esta instalado no ambiente.
- Exportacao local de blueprint SQL PostgreSQL, com `CREATE TABLE`, chaves
  primarias, chaves estrangeiras e indices derivados do inventario de schema,
  sem linhas financeiras.
- Exportacao local de pacote ZIP de homologacao PostgreSQL, reunindo roteiro,
  inventario, compatibilidade, plano de carga, contrato do adapter, plano de
  execucao, blueprint e manifesto com hashes SHA-256.
- Comandos administrativos `postgres-verify-package --package` e
  `postgres-review-summary --package` para validar o pacote PostgreSQL e gerar
  resumo Markdown de aceite antes de qualquer ensaio externo.
- Botoes em "Configuracoes" para verificar pacote PostgreSQL e exportar resumo
  de aceite a partir do ZIP gerado localmente.
- Relatorio local de aceite da Fase 8 pela tela "Configuracoes" e pelo comando
  `phase8-acceptance-report`, consolidando evidencias locais e pendencias
  externas sem encerrar a fase automaticamente.
- Pacote ZIP local de evidencias da Fase 8 pela tela "Configuracoes" e pelo
  comando `phase8-evidence-package`, com aceite local, prontidoes e manifesto.
- Comandos administrativos `phase8-verify-package --package` e
  `phase8-review-summary --package` para validar hashes, flags e gerar resumo
  Markdown do pacote de evidencias da Fase 8.
- Comando administrativo `phase8-closure-readiness` para consolidar evidencias
  externas ja sanitizadas e impedir fechamento sem Sandbox Asaas e PostgreSQL
  descartavel aprovados.
- Comando administrativo `phase8-closeout-report` para gerar o Markdown final
  de encerramento somente a partir do gate de fechamento.
- Comando administrativo `phase8-closeout-package` para arquivar os artefatos
  finais com manifesto SHA-256.
- Comando administrativo `phase8-finalize` para gerar os tres artefatos finais
  em uma unica execucao.
- Comando administrativo `phase8-finalize-from-dir` para localizar os artefatos
  em uma pasta e acionar o fechamento final sem informar cada caminho.
- Roteiro seguro de validacao Sandbox Asaas documentado em
  `docs/fase-8-validacao-sandbox-asaas.md`.
- Tela "Planejamento" na aplicacao desktop.
- Auditoria para criacao/atualizacao de orcamentos, regras, dashboards e
  solicitacoes sensiveis.
- Testes automatizados para orcamento, projecao e regras.

## Decisoes de seguranca

- Nenhuma chave, token ou credencial foi adicionada ao codigo.
- A Fase 8 usa apenas o banco local existente.
- Regras de categorizacao sao sugestoes locais e nao enviam descricoes para APIs.
- Sugestoes nunca gravam lancamentos sozinhas; o operador precisa confirmar o
  formulario.
- Importacoes exibem a origem da categorizacao na pre-visualizacao antes de
  gravar qualquer linha.
- O relatorio de categorizacao e exportado localmente e nao envia dados para
  servicos externos.
- O dashboard avancado usa apenas dados locais ja persistidos no SQLite.
- Perfis personalizados de dashboard ficam no SQLite local e nao armazenam
  credenciais, chaves ou tokens.
- Pesos sazonais sao configuracao local de planejamento e nao acionam nenhuma
  automacao externa.
- Metas anuais sao calculadas a partir dos orcamentos locais ja auditados, sem
  nova fonte de dados sensiveis.
- Qt Charts renderiza somente agregacoes locais ja calculadas pelo servico de
  planejamento.
- A preparacao para escrita futura no Asaas e apenas local: nenhuma cobranca,
  cancelamento ou estorno e enviado para API neste incremento.
- Payloads de solicitacoes sensiveis rejeitam campos com nomes de token, segredo,
  senha, autorizacao ou chave de API.
- O solicitante nao pode aprovar a propria operacao e duas aprovacoes distintas
  sao exigidas antes de uma solicitacao ficar aprovada.
- A execucao de escrita no Asaas exige `ASAAS_ENABLE_WRITE_OPERATIONS=true` no
  `.env`; o valor padrao permanece `false`.
- O executor reutiliza a execucao local existente quando a solicitacao ja foi
  tentada, evitando nova chamada externa para o mesmo ID.
- A checagem de prontidao e somente-leitura, nao chama a API Asaas e nao exibe
  segredos; ela mostra apenas pendencias operacionais e a chave idempotente
  local quando aplicavel.
- O comando `asaas-readiness` usa a mesma checagem de prontidao, grava apenas
  metadados locais e nao executa cobranca, cancelamento ou estorno.
- O comando `asaas-execute` e restrito a `ASAAS_ENV=sandbox`, exige confirmacao
  explicita, nao aceita token por argumento e grava apenas status, IDs e chave
  idempotente local.
- O comando `asaas-execution-report` e somente-leitura, nao chama a API, nao
  reexecuta operacao e omite payload financeiro e resposta bruta armazenada.
- O comando `asaas-validation-package` consolida apenas artefatos sanitizados,
  nao abre conexao externa, nao executa escrita e adiciona hashes para conferir
  integridade antes da revisao.
- O comando `asaas-verify-package` e somente-leitura, recalcula hashes do ZIP e
  bloqueia a revisao quando encontra arquivo inesperado, flag insegura ou
  marcador proibido.
- A UI de aprovacoes sensiveis nao exibe resposta bruta da API; a revisao deve
  usar a evidencia local sanitizada.
- A exportacao de pacote pela UI usa os mesmos artefatos sanitizados do comando
  administrativo e nao aciona operacao externa.
- O transporte HTTP de escrita nao ecoa headers, token, corpo da requisicao ou
  resposta de erro em excecoes; falhas externas ficam registradas como status
  local `failed`.
- O diagnostico de implantacao mascara credenciais em URLs PostgreSQL e trata
  PostgreSQL como preparacao futura; o uso operacional continua em SQLite local
  ate existir adapter, migracao ensaiada e validacao de concorrencia.
- A prontidao de rede e somente-leitura, nao abre conexao externa, nao executa
  migracao, nao exporta linhas financeiras e bloqueia uso multi-instalacao
  enquanto o backend operacional continuar em SQLite.
- O pacote de homologacao de rede consolida apenas artefatos sanitizados, nao
  inclui dados financeiros, nao executa migracao e adiciona hashes para revisao
  tecnica antes de qualquer decisao multiusuario.
- O comando `network-verify-package` e somente-leitura, recalcula hashes do ZIP
  e bloqueia a revisao quando encontra arquivo inesperado, flag insegura ou
  marcador proibido.
- O comando `network-review-summary` apenas resume a verificacao local em
  Markdown, sem credenciais, sem linhas financeiras, sem conexao externa e sem
  executar migracao.
- O preflight de migracao e somente-leitura, usa apenas PRAGMAs locais do
  SQLite e nao exporta dados financeiros nem tenta conexao externa.
- O roteiro de ensaio exportado mascara URLs sensiveis, nao contem credenciais
  reais e serve apenas para homologacao em ambiente descartavel.
- O inventario de schema exportado e somente metadado tecnico e nao inclui
  linhas de lancamentos, titulos, usuarios, auditoria ou documentos.
- O relatorio de compatibilidade usa o inventario local e nao conecta em
  PostgreSQL; ele apenas aponta riscos antes de desenhar o adapter.
- O plano de carga PostgreSQL e derivado apenas das chaves estrangeiras do
  inventario local, nao contem `INSERT` e nao exporta linhas de nenhuma tabela.
- O contrato do adapter PostgreSQL descreve a estrategia futura de carga e
  validacao, mas nao executa comandos e nao contem credenciais nem linhas reais.
- O plano de execucao de homologacao PostgreSQL usa operacoes estruturadas e
  parametros nomeados; ele nao contem comandos `INSERT`, nao carrega dados e
  nao abre conexao externa.
- O preflight do runner PostgreSQL e offline, mascara eventual URL alvo,
  bloqueia backend operacional diferente de SQLite e serve apenas para revisao
  antes do runner real.
- O runner PostgreSQL opt-in exige `.env` local, flag explicita, ambiente nao
  produtivo, origem SQLite integra e transporte injetado; a aplicacao nao inclui
  credenciais, nao registra senha alvo e nao expoe botao de execucao nesta fase.
- A exportacao de prontidao do runner nao abre conexao, nao executa migracao e
  mostra apenas URL mascarada e motivos de bloqueio.
- O runner isolado de homologacao recebe o alvo por protocolo injetado, nao
  conhece URL nem senha, nao grava dump em disco e valida contagens antes de
  declarar sucesso.
- O alvo SQLAlchemy nao carrega credenciais por conta propria; ele opera apenas
  sobre uma conexao entregue pela camada de homologacao e usa parametros para
  valores de linha.
- O orquestrador SQLAlchemy so cria engine depois de validar ambiente, flag,
  URL de homologacao e origem SQLite; os testes usam engine fake e confirmam que
  a URL real nunca aparece no resultado.
- A acao administrativa de homologacao nao cria relatorio quando a prontidao
  bloqueia a execucao e o relatorio de sucesso contem apenas resumo tecnico,
  nunca linhas de dados nem URL sem mascara.
- O comando administrativo de homologacao exige
  `--confirm-disposable-target`, nao aceita credenciais por argumento e nao
  passa pela UI comum da secretaria.
- O comando administrativo de prontidao grava somente JSON de metadados, nao
  executa migracao, nao abre conexao PostgreSQL e nao inicializa usuario.
- A prontidao de homologacao bloqueia antes de criar engine quando o driver
  PostgreSQL nao esta instalado, evitando erro tardio ou tentativa parcial.
- O blueprint PostgreSQL e gerado como artefato de revisao tecnica, nao executa
  migracao, nao abre conexao externa e nao contem `INSERT` nem dados reais.
- O pacote de homologacao PostgreSQL consolida apenas artefatos locais seguros,
  marca explicitamente que nao contem dados financeiros nem credenciais e
  adiciona hashes para conferencia de integridade.
- O comando `postgres-verify-package` e somente-leitura, recalcula hashes do ZIP
  PostgreSQL e bloqueia revisao quando encontra arquivo inesperado, flag
  insegura ou marcador proibido.
- O comando `postgres-review-summary` apenas resume a verificacao local em
  Markdown, sem credenciais, sem linhas financeiras, sem conexao externa e sem
  executar migracao.
- A UI de "Configuracoes" usa os mesmos verificadores locais do pacote
  PostgreSQL; ela nao executa ensaio, nao abre conexao externa e nao le
  credenciais de homologacao.
- O relatorio local de aceite da Fase 8 nao chama APIs, nao abre PostgreSQL e
  nao declara a fase concluida sem evidencias reais de Sandbox Asaas e
  homologacao PostgreSQL descartavel.
- O pacote local de evidencias da Fase 8 contem apenas metadados, prontidoes e
  manifesto SHA-256; ele tambem nao chama APIs, nao abre PostgreSQL e nao
  encerra a fase.
- O comando `phase8-verify-package` valida tambem que o manifesto mantem
  `phase_complete=false`, evitando tratar evidencias locais como conclusao real.
- O comando `phase8-review-summary` apenas resume essa verificacao local em
  Markdown, sem credenciais, sem linhas financeiras e sem conexao externa.
- O comando `phase8-closure-readiness` e somente-leitura: nao chama APIs, nao
  abre PostgreSQL, nao executa migracao e exige artefatos externos sanitizados
  antes de marcar `ready_to_close_phase8=true`.
- O comando `phase8-closeout-report` tambem e somente-leitura; se o gate final
  ainda estiver pendente, o relatorio marca a fase como pendente e retorna
  codigo 1.
- O comando `phase8-closeout-package` apenas empacota arquivos locais ja
  gerados, sem abrir banco, API ou conexao externa.
- O comando `phase8-finalize` combina os tres passos finais e retorna codigo 1
  enquanto as evidencias externas ainda estiverem pendentes.
- O comando `phase8-finalize-from-dir` usa os nomes padrao exportados em
  `documents/exports` e escolhe a evidencia Asaas mais recente quando houver
  mais de uma.
- Os testes do executor usam transporte mockado e nao precisam de rede nem de
  chave real.
- Valores monetarios continuam armazenados em centavos inteiros.

## Como validar manualmente

1. Abrir a aplicacao e acessar "Planejamento".
2. Criar categorias e centros de custo, se necessario.
3. Criar um orcamento mensal para uma categoria.
4. Criar um orcamento anual linear e conferir a distribuicao dos 12 meses.
5. Criar um orcamento anual sazonal com pesos mensais diferentes e conferir os
   meses reforcados no comparativo.
6. Registrar lancamentos reais na mesma categoria e mes.
7. Voltar em "Planejamento" e conferir o comparativo orcado vs realizado.
8. Conferir a secao "Metas anuais", a barra de avanco acumulado do ano e o
   grafico meta vs realizado.
9. Criar titulos em aberto e conferir a tabela e o grafico da projecao dos
   proximos 30 dias.
10. Cadastrar uma regra de categorizacao.
11. Criar lancamento ou titulo, preencher descricao e usar "Sugerir categoria".
12. Importar CSV/XLSX com categoria em branco e conferir a origem "sugerida" na
    pre-visualizacao.
13. Na pre-visualizacao, usar "Exportar categorizacao CSV" e revisar origens.
14. Abrir "Dashboard avancado", ajustar o periodo e conferir categorias, centros
    de custo, alertas e graficos nativos.
15. Usar "Salvar painel" para criar um dashboard personalizado, aplicar o painel
    salvo e confirmar que somente as secoes escolhidas aparecem.
16. Criar uma solicitacao sensivel via servico local, aprovar com dois usuarios
    distintos e conferir que a auditoria registra criacao e aprovacoes.
17. Tentar aprovar a propria solicitacao ou incluir campo sensivel no payload e
    confirmar que a operacao e rejeitada.
18. Abrir "Aprovacoes sensiveis", criar uma solicitacao com payload JSON local,
    revisar o detalhe e registrar aprovacoes ou rejeicao pela tela.
19. Validar em teste local que o executor recusa execucao com escrita Asaas
    desligada e que uma segunda chamada para a mesma solicitacao reaproveita a
    execucao registrada.
20. Abrir o detalhe da solicitacao em "Aprovacoes sensiveis" e conferir o
    historico de execucoes ou a mensagem de ausencia de tentativas.
21. Conferir no mesmo detalhe a secao "Prontidao de execucao" antes de qualquer
    validacao Sandbox.
22. Exportar a mesma prontidao pelo comando
    `uv run python -m basilica_financeiro asaas-readiness --request-id <id> --output documents/exports/prontidao-asaas-<id>.json`
    e confirmar que o JSON nao contem token nem chamada externa.
23. Quando houver chave Sandbox real no `.env`, executar em ambiente controlado:
    `uv run python -m basilica_financeiro asaas-execute --request-id <id> --confirm-sandbox --output documents/exports/execucao-asaas-<id>.json`
    e confirmar que o JSON local nao contem token nem payload financeiro.
24. Exportar a evidencia local pos-execucao:
    `uv run python -m basilica_financeiro asaas-execution-report --request-id <id> --output documents/exports/evidencia-asaas-<id>.json`
    e confirmar que ela nao contem token, payload da solicitacao ou resposta
    bruta da API.
25. Gerar o pacote ZIP local:
    `uv run python -m basilica_financeiro asaas-validation-package --request-id <id> --output documents/exports/pacote-homologacao-asaas-<id>.zip`
    e conferir o manifesto com hashes SHA-256.
26. Verificar o pacote ZIP local:
    `uv run python -m basilica_financeiro asaas-verify-package --package documents/exports/pacote-homologacao-asaas-<id>.zip --output documents/exports/verificacao-pacote-asaas-<id>.json`
    e confirmar `ready_for_review=true`.
27. Gerar o resumo Markdown de aceite:
    `uv run python -m basilica_financeiro asaas-review-summary --package documents/exports/pacote-homologacao-asaas-<id>.zip --output documents/exports/resumo-aceite-asaas-<id>.md`
    e anexar o arquivo a revisao tecnica da homologacao Sandbox.
28. Abrir "Configuracoes" e revisar o diagnostico de implantacao, confirmando
    SQLite local/offline como modo atual e pendencias para rede/PostgreSQL.
29. No mesmo painel, conferir que schema, integridade SQLite, chaves
    estrangeiras e WAL aparecem como prontos antes de ensaiar migracao.
30. Usar "Exportar roteiro de migracao" e revisar o Markdown gerado em
    `documents/exports`, sem inserir credenciais no arquivo.
31. Usar "Exportar prontidao de rede" ou o comando
    `uv run python -m basilica_financeiro network-readiness --output documents/exports/prontidao-uso-em-rede.json`
    e confirmar que `ready_for_network_use=false` enquanto SQLite for o backend
    operacional.
32. Usar "Exportar pacote de rede" ou o comando
    `uv run python -m basilica_financeiro network-validation-package --output documents/exports/pacote-homologacao-rede.zip`
    e conferir o manifesto SHA-256 antes da revisao tecnica.
33. Verificar o pacote de rede:
    `uv run python -m basilica_financeiro network-verify-package --package documents/exports/pacote-homologacao-rede.zip --output documents/exports/verificacao-pacote-rede.json`
    e confirmar `ready_for_review=true` antes de anexar a revisao tecnica.
34. Gerar o resumo Markdown de aceite da rede:
    `uv run python -m basilica_financeiro network-review-summary --package documents/exports/pacote-homologacao-rede.zip --output documents/exports/resumo-aceite-rede.md`
    e anexar junto com o JSON de verificacao.
35. Opcionalmente, usar os botoes "Verificar pacote de rede" e "Exportar resumo
    de rede" em "Configuracoes" para gerar os mesmos artefatos pela UI.
36. Usar "Exportar inventario de schema" e revisar o JSON gerado, confirmando
    que contem apenas metadados e contagens.
37. Usar "Exportar compatibilidade PostgreSQL" e revisar se ha achados
    bloqueantes antes de criar qualquer banco de homologacao.
38. Usar "Exportar plano de carga PostgreSQL" e conferir ordem das tabelas,
    dependencias e eventuais ciclos antes de implementar o adapter.
39. Usar "Exportar contrato adapter PostgreSQL" e revisar estrategia de
    insercao, tipos e checagens pos-carga.
40. Usar "Exportar plano de execucao PostgreSQL" e revisar fases,
    operacoes parametrizadas e validacoes antes do adapter real.
41. Usar "Exportar preflight runner PostgreSQL" e conferir que o arquivo marca
    modo offline, sem conexao externa, sem migracao e sem credenciais.
42. Usar "Exportar prontidao runner PostgreSQL" e confirmar que a execucao
    permanece bloqueada ate configurar `.env` local e transporte homologado.
43. Instalar `psycopg` ou `psycopg2` apenas no ambiente descartavel de
    homologacao e repetir a exportacao de prontidao, conferindo
    `postgresql_driver_available`.
44. Em ambiente tecnico, repetir a prontidao pelo comando
    `uv run python -m basilica_financeiro postgres-readiness --output documents/exports/prontidao-runner-homologacao-postgresql.json`
    antes de qualquer tentativa real.
45. Exportar o aceite local da Fase 8 pela tela "Configuracoes" ou pela CLI:
    `uv run python -m basilica_financeiro phase8-acceptance-report --output documents/exports/aceite-local-fase-8.md`
    e confirmar que ele marca as homologacoes externas como pendentes.
46. Exportar o pacote local de evidencias da Fase 8 pela tela "Configuracoes"
    ou pela CLI:
    `uv run python -m basilica_financeiro phase8-evidence-package --output documents/exports/pacote-evidencias-fase-8.zip`
    e conferir o manifesto antes da revisao tecnica.
47. Verificar o pacote local de evidencias da Fase 8:
    `uv run python -m basilica_financeiro phase8-verify-package --package documents/exports/pacote-evidencias-fase-8.zip --output documents/exports/verificacao-pacote-fase-8.json`
    e confirmar `ready_for_review=true` e `phase_completion_guard_valid=true`.
48. Gerar o resumo Markdown do pacote local de evidencias da Fase 8:
    `uv run python -m basilica_financeiro phase8-review-summary --package documents/exports/pacote-evidencias-fase-8.zip --output documents/exports/resumo-aceite-fase-8.md`
    e anexar junto com o JSON de verificacao.
49. Opcionalmente, usar os botoes "Verificar pacote Fase 8" e "Exportar resumo
    Fase 8" em "Configuracoes" para gerar os mesmos artefatos pela UI.
50. Gerar o pacote PostgreSQL pela CLI quando necessario:
    `uv run python -m basilica_financeiro postgres-validation-package --output documents/exports/pacote-homologacao-postgresql.zip`
51. Verificar o pacote PostgreSQL antes da revisao tecnica:
    `uv run python -m basilica_financeiro postgres-verify-package --package documents/exports/pacote-homologacao-postgresql.zip --output documents/exports/verificacao-pacote-postgresql.json`
    e confirmar `ready_for_review=true`.
52. Gerar o resumo Markdown de aceite PostgreSQL:
    `uv run python -m basilica_financeiro postgres-review-summary --package documents/exports/pacote-homologacao-postgresql.zip --output documents/exports/resumo-aceite-postgresql.md`
    e anexar junto com o JSON de verificacao.
53. Opcionalmente, usar os botoes "Verificar pacote PostgreSQL" e "Exportar
    resumo PostgreSQL" em "Configuracoes" para gerar os mesmos artefatos pela UI.
54. Em ambiente de desenvolvimento, validar o runner isolado com alvo fake ou
    ambiente descartavel, confirmando ordem de carga, reset de identity e
    contagens sem expor credenciais.
55. Validar o alvo SQLAlchemy apenas com banco PostgreSQL descartavel e URL no
    `.env` local, confirmando que o alvo vazio e exigido antes da carga.
56. Validar o orquestrador opt-in em ambiente descartavel, confirmando que a
    engine so e criada depois das travas e que o resultado mascara a URL alvo.
57. Executar a acao administrativa de homologacao somente em ambiente
    descartavel pelo comando
    `uv run python -m basilica_financeiro postgres-rehearsal --confirm-disposable-target`
    e revisar o relatorio Markdown local antes de qualquer decisao operacional.
58. Usar "Exportar blueprint PostgreSQL" e revisar o SQL em ambiente tecnico
    antes de implementar o adapter ou criar banco de homologacao.
59. Usar "Exportar pacote de homologacao PostgreSQL" e conferir o manifesto
    antes de enviar para revisao tecnica.
60. Quando houver chave Sandbox real, seguir
    `docs/fase-8-validacao-sandbox-asaas.md` sem versionar credenciais.
61. Depois das validacoes externas reais, consolidar os gates finais:
    `uv run python -m basilica_financeiro phase8-closure-readiness --asaas-verification documents/exports/verificacao-pacote-asaas-<id>.json --asaas-summary documents/exports/resumo-aceite-asaas-<id>.md --postgres-package-verification documents/exports/verificacao-pacote-postgresql.json --postgres-report documents/exports/relatorio-homologacao-postgresql.md --phase8-package-verification documents/exports/verificacao-pacote-fase-8.json --output documents/exports/prontidao-fechamento-fase-8.json`
    e confirmar `ready_to_close_phase8=true` antes de registrar o encerramento
    operacional da fase.
62. Gerar o relatorio final:
    `uv run python -m basilica_financeiro phase8-closeout-report --closure-readiness documents/exports/prontidao-fechamento-fase-8.json --output documents/exports/encerramento-fase-8.md`
    e anexar junto com os artefatos externos aprovados.
63. Gerar o ZIP final:
    `uv run python -m basilica_financeiro phase8-closeout-package --closure-readiness documents/exports/prontidao-fechamento-fase-8.json --closeout-report documents/exports/encerramento-fase-8.md --output documents/exports/pacote-encerramento-fase-8.zip`
    e arquivar com a decisao operacional assinada.
64. Alternativa recomendada: executar tudo em um unico comando:
    `uv run python -m basilica_financeiro phase8-finalize --asaas-verification documents/exports/verificacao-pacote-asaas-<id>.json --asaas-summary documents/exports/resumo-aceite-asaas-<id>.md --postgres-package-verification documents/exports/verificacao-pacote-postgresql.json --postgres-report documents/exports/relatorio-homologacao-postgresql.md --phase8-package-verification documents/exports/verificacao-pacote-fase-8.json --output-dir documents/exports`
    e arquivar os tres artefatos gerados.
65. Com todos os artefatos na pasta padrao, usar o atalho:
    `uv run python -m basilica_financeiro phase8-finalize-from-dir --input-dir documents/exports --output-dir documents/exports`
66. Opcionalmente, usar o botao "Finalizar Fase 8" em "Configuracoes" para
    selecionar os mesmos artefatos externos e gerar os tres arquivos finais.

## Proximos passos da Fase 8

- Revisar com a equipe financeira as categorias e centros usados no orcamento.
- Refinar graficos nativos com filtros e estados vazios conforme uso real da
  equipe.
- Validar a tela "Aprovacoes sensiveis" com os perfis que poderao aprovar
  operacoes no uso real.
- Validar o comando `asaas-execute` contra Sandbox Asaas com chave real apenas
  no `.env` local, seguindo o roteiro seguro antes de qualquer uso real.
- Executar `phase8-closure-readiness` somente apos anexar os artefatos reais de
  Asaas Sandbox, pacote PostgreSQL, relatorio PostgreSQL e pacote local da Fase 8.
- Gerar `phase8-closeout-report` quando o gate final retornar
  `ready_to_close_phase8=true`.
- Gerar `phase8-closeout-package` para arquivar o pacote final da fase.
- Preferir `phase8-finalize` quando os artefatos externos ja estiverem prontos.
- Usar `phase8-finalize-from-dir` quando todos os artefatos estiverem em
  `documents/exports`.
- Adicionar UI de execucao somente depois da validacao com Sandbox e da decisao
  operacional sobre quais perfis poderao executar.
- Evoluir o diagnostico de implantacao para um adapter real PostgreSQL apenas
  depois de estabilizar o uso local, os fluxos de permissao e a governanca de
  operacoes sensiveis.

## Memoria de diagnostico de front-end

### Prioridade 1 - Quebras estruturais

- Corrigir o layout base para janelas menores, especialmente a combinacao de
  sidebar fixa, pagina principal larga e blocos horizontais sem quebra.
- Tratar scroll e overflow de forma consistente nas paginas com muito conteudo,
  evitando que a navegacao dependa apenas de ampliacao horizontal implícita.
- Reduzir a dependencia de `QHBoxLayout` para areas de filtros, tabs e dashboards
  que hoje acumulam muitos elementos na mesma linha.
- Criar um padrao de empilhamento responsivo para o shell principal e para
  paginas com alta densidade de widgets.

### Prioridade 2 - Componentes datados

- Refatorar os controles de input para um padrao unico de largura, altura e
  estados de foco.
- Melhorar `QComboBox`, `QDateEdit` e `QLineEdit` usados em formularios longos,
  mapping de importacao, filtros e dialogs de operacao.
- Revisar o estilo e a semantica dos botões secundarios, ghost, tabs e filtros
  em pill para evitar excesso de variantes visuais sem consistencia.
- Padronizar labels de formularios, campos obrigatorios e feedback de erro.

### Prioridade 3 - Tabelas e dados reais

- Criar um container responsivo para tabelas com fallback de scroll horizontal e
  colunas prioritarias.
- Tratar estados vazios de tabelas com componente dedicado, em vez de depender
  apenas de uma linha simples.
- Lidar melhor com valores longos, descricoes extensas e muitas linhas sem
  esmagar o conteudo.
- Revisar tabelas de importacao, lancamentos, dashboards, conciliacao e compras
  para reduzir a densidade extrema.

### Prioridade 4 - Dashboard avancado

- Reorganizar cards KPI e blocos analiticos para que tenham comportamento mais
  previsivel em larguras intermediarias.
- Criar containers especificos para graficos e tabelas do dashboard avancado,
  com empilhamento em telas menores.
- Adicionar estados vazios mais claros para graficos e rankings sem dados.
- Preparar uma composicao visual mais compacta para resumo, comparativo e
  projecoes.

### Prioridade 5 - Polimento visual

- Ajustar bordas, sombras e contraste dos cards e paineis.
- Refinar hover e focus dos controles para melhorar percepcao de interacao.
- Revisar espacos verticais e horizontais para reduzir areas “soltas” e
  inconsistencias entre seções.
- Melhorar a hierarquia visual entre titulos, captions, metricas e tabelas.

### Problemas ja identificados

- Sidebar fixa em `220px` e janela inicial grande, com pouca adaptacao para
  resolucoes menores.
- Varios grupos de filtros, tabs e acoes montados em linha unica, sem quebra.
- Dashboard avancado usa varios `QHBoxLayout` para graficos e tabelas, o que
  tende a comprimir a interface.
- Tabelas com muitas colunas usam `Stretch` de forma uniforme, piorando leitura
  quando o conteudo e longo.
- Formularios e dialogs longos, como mapeamento de importacao e pesos mensais,
  precisam de melhor agrupamento e espacamento.
- `QDateEdit`, `QComboBox` e `QLineEdit` estao visualmente padronizados, mas
  ainda sem estrategia responsiva de largura minima e empilhamento.
- Os componentes de KPI, badges e tabelas estao corretos funcionalmente, mas
  ainda faltam variantes mais compactas e orientadas a densidade.
