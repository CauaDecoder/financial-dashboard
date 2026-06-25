# Basilica Financeiro

Aplicativo desktop local para gestao financeira da Basilica Menor Nossa Senhora das Dores.

## Fase Atual

Fase 1: fundacao tecnica concluida.

Fase 2: financeiro basico implementado e pronto para revisao manual dos fluxos.

Fase 3: importacoes iniciada com templates CSV/XLSX, mapeamento visual,
pre-visualizacao tabular, relatorio de erros e importacao validada de
movimentacoes financeiras e titulos previstos.

Fase 4: integracao Asaas leitura-only iniciada com snapshots locais,
sincronizacao manual, sugestoes de conciliacao e aceite manual auditavel.

Fase 5: integracao PDV/estoque iniciada com contrato leitura-only,
snapshots locais e importacao idempotente de vendas pagas como receitas.

Fase 6: compras e fornecedores iniciada com cadastro de fornecedores, fluxo
auditavel de pedidos, recebimentos e geracao de contas a pagar.

Fase 7: documentos e Google Sheets iniciada com anexos locais, hash SHA-256 e
configuracao segura por `.env`.

Fase 8: planejamento financeiro iniciada com orcamento mensal/anual,
comparativo orcado vs realizado, projecao de fluxo de caixa e regras locais
de categorizacao, alem da preparacao local para aprovacao dupla de operacoes
sensiveis futuras.

Incluido neste marco inicial:

- Estrutura de diretorios do projeto.
- Configuracao por `.env`, com `.gitignore` protegendo segredos e dados locais.
- Banco SQLite local com schema inicial.
- Perfis e permissoes iniciais.
- Trilha Alembic/SQLAlchemy para migracoes.
- Autenticacao local com hash Argon2id.
- Bloqueio temporario apos 5 tentativas falhas.
- Auditoria de operacoes sensiveis.
- Backup manual criptografado.
- UI desktop inicial em PySide6 com login e janela principal.
- UI inicial com consulta de usuarios, auditoria e backup manual.
- Nucleo financeiro inicial com valores monetarios em centavos.
- Formularios iniciais para contas, categorias, centros de custo e lancamentos.
- Contas a pagar e receber com vencimentos, status e baixa parcial ou total.
- Parcelamento e recorrencia mensal para lancamentos e titulos.
- Filtros operacionais por tipo, categoria e centro de custo.
- Dashboard financeiro com saldo, fluxo do mes e pendencias.
- Exportacao XLSX e PDF de relatorio financeiro.
- Backup automatico diario configuravel.
- Cancelamento logico de lancamentos e titulos.
- Templates CSV/XLSX de importacao financeira.
- Importacao CSV/XLSX com validacao, duplicidade e auditoria de lote.
- Templates CSV/XLSX de contas a pagar/receber previstas.
- Importacao de titulos previstos sem alterar saldo antes da baixa.
- Mapeamento visual de colunas para planilhas fora do template.
- Pre-visualizacao tabular antes de gravar importacoes.
- Relatorio CSV exportavel para erros de importacao.
- Mapeamento simples de colunas alternativas no servico de importacao.
- Exportacao CSV de relatorio financeiro com formatacao brasileira.
- Cliente Asaas leitura-only com chave somente via `.env`.
- Snapshots locais de cobrancas Asaas e sugestoes de conciliacao obvias.
- Aceite manual auditavel de conciliacoes Asaas.
- Desconciliacao manual preservando historico.
- Filtros locais da tela Asaas e ADR-004 sobre polling manual.
- Contrato de integracao PDV via tabelas/views leitura-only.
- Snapshots locais de categorias, produtos, estoque e vendas do PDV.
- Importacao idempotente de vendas pagas do PDV para receitas financeiras.
- Tela "PDV e estoque" com resumo, produtos, vendas e importacao.
- Cadastro de fornecedores e pedidos de compra.
- Avanco controlado de etapas de compra ate entrada no estoque.
- Recebimento parcial ou total de pedidos de compra.
- Geracao automatica de conta a pagar a partir da compra conferida.
- Anexos de documentos/PDFs com copia controlada e SHA-256.
- Vinculo de documentos a lancamentos, titulos, fornecedores e compras.
- Tela "Documentos" com anexos, abertura do arquivo armazenado e status Google Sheets.
- Configuracao local de credenciais Google sem versionar segredos.
- Tela "Planejamento" para orcamento mensal e projecao de caixa.
- Distribuicao de orcamento anual em 12 meses com fechamento em centavos.
- Distribuicao sazonal de orcamento anual por pesos mensais.
- Comparativo orcado vs realizado por categoria e centro de custo.
- Metas anuais com realizado acumulado, variacao e barra de avanco.
- Grafico nativo Qt Charts de metas anuais.
- Grafico nativo Qt Charts de projecao de caixa acumulada.
- Regras locais de categorizacao por palavra-chave, tipo e prioridade.
- Sugestao manual de categoria/centro em lancamentos e titulos.
- Sugestao assistida no wizard de importacao quando categoria ou centro vierem vazios.
- Relatorio CSV de categorizacao da pre-visualizacao de importacao.
- Dashboard avancado com categorias, centros de custo e alertas de vencimento.
- Graficos nativos Qt Charts no dashboard avancado.
- Perfis personalizados para o dashboard avancado.
- Solicitacoes locais de operacoes sensiveis com duas aprovacoes distintas antes
  de qualquer execucao futura.
- Tela "Aprovacoes sensiveis" para criacao, detalhamento, aprovacao, rejeicao e
  cancelamento dessas solicitacoes.
- Executor idempotente para escrita futura no Asaas, desligado por padrao e
  validado com transporte mockado.
- Historico de tentativas de execucao no detalhe das aprovacoes sensiveis.
- Checagem local de prontidao de execucao no detalhe das aprovacoes sensiveis,
  sem chamada externa e sem expor credenciais.
- Exportacao de prontidao pela tela "Aprovacoes sensiveis", usando JSON local
  sem token e sem chamada externa.
- Execucao Sandbox pela tela "Aprovacoes sensiveis", bloqueada fora de
  `ASAAS_ENV=sandbox`, com confirmacao explicita, digitacao de `SANDBOX` e
  registro idempotente.
- Exportacao de evidencia pos-execucao pela tela "Aprovacoes sensiveis", sem
  token, payload da solicitacao ou resposta bruta da API.
- Exportacao de pacote ZIP de homologacao Asaas pela tela "Aprovacoes
  sensiveis", com checklist, prontidao, evidencia e manifesto SHA-256.
- Exportacao de resumo Markdown de aceite pela tela "Aprovacoes sensiveis",
  consolidando os gates locais do pacote Asaas sem dados sensiveis.
- Comando administrativo `asaas-readiness --request-id` para exportar JSON de
  prontidao de solicitacao Asaas sem chamar API nem expor token.
- Comando administrativo `asaas-execute --confirm-sandbox --request-id` para
  disparar solicitacao Asaas aprovada apenas no Sandbox, com resumo local sem
  credenciais e idempotencia pelo ID da solicitacao.
- Comando administrativo `asaas-execution-report --request-id` para exportar
  evidencia local pos-execucao, sem payload da solicitacao nem resposta bruta
  da API.
- Comando administrativo `asaas-validation-package --request-id` para gerar ZIP
  local de homologacao Sandbox com prontidao, evidencia, checklist e manifesto
  SHA-256, sem chamada externa.
- Comando administrativo `asaas-verify-package --package` para conferir arquivos,
  hashes, flags de seguranca e marcadores proibidos do ZIP de homologacao Asaas.
- Comando administrativo `asaas-review-summary --package` para exportar resumo
  Markdown de aceite dos gates locais, sem chamar API nem expor dados sensiveis.
- Diagnostico de implantacao em "Configuracoes" com modo SQLite/offline atual e
  pendencias explicitas para rede/PostgreSQL.
- Exportacao local de prontidao de uso em rede em "Configuracoes" e por CLI,
  bloqueando multi-instalacao sobre SQLite e sem abrir conexao externa.
- Exportacao local de pacote ZIP de homologacao de rede, com prontidao,
  checklist e manifesto SHA-256, sem dados financeiros nem credenciais.
- Verificacao e resumo Markdown do pacote de rede tambem pela tela
  "Configuracoes", para revisao tecnica sem linha de comando.
- Preflight local de migracao em "Configuracoes" com schema, integridade SQLite,
  chaves estrangeiras, WAL e contagem de tabelas criticas.
- Exportacao local de roteiro Markdown para ensaio SQLite -> PostgreSQL, sem
  credenciais e sem conexao externa.
- Exportacao local de inventario JSON do schema SQLite, apenas com metadados
  tecnicos e contagens criticas.
- Exportacao local de relatorio Markdown de compatibilidade PostgreSQL para
  revisar riscos de schema antes do adapter real.
- Exportacao local de plano JSON de carga PostgreSQL para revisar ordem de
  tabelas, dependencias e ciclos antes de qualquer migracao.
- Exportacao local de contrato JSON do adapter PostgreSQL para revisar tipos,
  chaves, indices, estrategia de insercao e checagens pos-carga.
- Exportacao local de plano JSON de execucao de homologacao PostgreSQL com
  fases, operacoes estruturadas e parametros nomeados para o adapter futuro.
- Exportacao local de preflight JSON do runner PostgreSQL futuro, com guardas
  offline, sem conexao externa, sem migracao e sem credenciais.
- Exportacao local de prontidao JSON do runner PostgreSQL opt-in, usando URL
  alvo mascarada e execucao desligada por padrao via `.env`.
- Runner isolado de homologacao PostgreSQL com alvo injetado para carga,
  reset de identities e validacao de contagens sem driver ou credencial no codigo.
- Alvo SQLAlchemy de homologacao PostgreSQL com bloqueio de banco nao vazio,
  inserts parametrizados e reset de identity sobre conexao entregue pelo ambiente.
- Orquestrador SQLAlchemy opt-in para homologacao, criando engine somente depois
  das travas de prontidao e retornando URL alvo mascarada.
- Acao administrativa de homologacao PostgreSQL que grava relatorio Markdown
  local com resumo tecnico, sem linhas financeiras nem credenciais.
- Comando administrativo `postgres-rehearsal --confirm-disposable-target` para
  executar a homologacao opt-in fora da UI comum e gravar o relatorio local.
- Comando administrativo `postgres-readiness` para exportar o JSON de prontidao
  do runner sem abrir conexao externa nem criar usuario inicial.
- Comando administrativo `network-readiness` para exportar JSON local de
  prontidao de rede, sem credenciais, sem linhas financeiras e sem migracao.
- Comando administrativo `network-validation-package` para gerar ZIP local de
  revisao de rede com checklist e manifesto de hashes.
- Comando administrativo `network-verify-package --package` para conferir
  arquivos, hashes, flags de seguranca e marcadores proibidos do ZIP de rede.
- Comando administrativo `network-review-summary --package` para gerar resumo
  Markdown de aceite dos gates locais de rede.
- Prontidao do runner PostgreSQL agora verifica se ha driver `psycopg` ou
  `psycopg2` instalado antes de tentar abrir engine SQLAlchemy.
- Exportacao local de blueprint SQL PostgreSQL para revisar tabelas, chaves e
  indices antes de qualquer adapter ou migracao real.
- Exportacao local de pacote ZIP de homologacao PostgreSQL com roteiro,
  inventario, compatibilidade, plano de carga, contrato, plano de execucao,
  blueprint e manifesto com hashes.
- Comandos administrativos `postgres-verify-package --package` e
  `postgres-review-summary --package` para conferir o pacote PostgreSQL e gerar
  resumo Markdown de aceite sem abrir conexao externa.
- Verificacao e resumo Markdown do pacote PostgreSQL tambem pela tela
  "Configuracoes", a partir do ZIP local ja gerado.
- Relatorio local de aceite da Fase 8 por CLI e pela tela "Configuracoes",
  deixando explicitas as evidencias locais e as pendencias externas.
- Pacote ZIP local de evidencias da Fase 8 por CLI e pela tela "Configuracoes",
  com aceite local, prontidoes e manifesto SHA-256.
- Verificacao e resumo Markdown do pacote de evidencias da Fase 8 por CLI e
  pela tela "Configuracoes", mantendo `phase_complete=false`.
- Comando administrativo `phase8-closure-readiness` para consolidar evidencias
  externas ja sanitizadas e indicar se a Fase 8 pode ser fechada.
- Comando administrativo `phase8-closeout-report` para gerar o Markdown final
  de encerramento a partir do gate aprovado.
- Comando administrativo `phase8-closeout-package` para empacotar o gate,
  relatorio final e manifesto SHA-256 de encerramento.
- Comando administrativo `phase8-finalize` para gerar prontidao, relatorio e
  pacote final em uma unica execucao.
- Comando administrativo `phase8-finalize-from-dir` para localizar os
  artefatos em `documents/exports` e finalizar sem informar cada arquivo.

## Instalacao de desenvolvimento

```powershell
uv sync
Copy-Item .env.example .env
# Edite .env e preencha APP_SECRET_KEY, DEFAULT_ADMIN_PASSWORD e BACKUP_ENCRYPTION_KEY.
uv run python -m basilica_financeiro
```

## Verificacoes

```powershell
uv run pytest
uv run ruff check .
uv run mypy src
```

## Seguranca

Nenhum segredo deve ser escrito no codigo. Chaves de API, senhas, tokens e caminhos
sensiveis devem ficar apenas no `.env` local ou em cofre do sistema operacional em
fases futuras.

Operacoes de escrita no Asaas permanecem desligadas por padrao. Para qualquer
validacao controlada em Sandbox, use `ASAAS_ENABLE_WRITE_OPERATIONS=true` apenas
no `.env` local e nunca versionado.
O comando administrativo de execucao Asaas bloqueia `ASAAS_ENV=production` e
exige `--confirm-sandbox`, mantendo a chave somente no `.env`.

O roteiro seguro para Sandbox fica em
`docs/fase-8-validacao-sandbox-asaas.md`.

PostgreSQL e uso em rede permanecem como preparacao de Fase 8. A tela
"Configuracoes" mostra a prontidao atual, mascara credenciais em URLs e nao
habilita migracao sem adapter, backup validado e testes de concorrencia.
O preflight local apenas le metadados do SQLite e nao envia dados para servicos
externos.
O roteiro de migracao exportado e um guia de homologacao; ele nao executa
migracao nem substitui o adapter PostgreSQL futuro.
O inventario JSON de schema nao contem linhas financeiras, usuarios ou
documentos; ele serve para desenhar e revisar o adapter de migracao.
O relatorio de compatibilidade tambem e local e nao abre conexao PostgreSQL.
O plano de carga PostgreSQL e derivado apenas das chaves estrangeiras do schema
local e nao contem `INSERT` nem dados reais.
O contrato do adapter PostgreSQL descreve a carga futura, mas nao executa
migracao, nao abre conexao externa e nao contem linhas reais.
O plano de execucao de homologacao PostgreSQL usa operacoes estruturadas e
parametros nomeados; ele nao contem `INSERT` nem carrega dados.
O preflight do runner PostgreSQL e apenas uma validacao offline do artefato
futuro: mascara eventual URL alvo e nao abre conexao nem executa migracao.
O runner PostgreSQL opt-in exige `POSTGRES_REHEARSAL_DATABASE_URL` e
`POSTGRES_REHEARSAL_ENABLE_EXECUTION=true` apenas no `.env` local; nesta fase a
UI exporta prontidao, mas nao oferece botao de execucao operacional.
Essa prontidao tambem exige driver PostgreSQL (`psycopg` ou `psycopg2`)
instalado no ambiente de homologacao antes de qualquer engine SQLAlchemy.
O nucleo isolado do runner recebe um alvo por protocolo, nao conhece senha/URL
e foi testado com destino fake para evitar rede e vazamento de dados.
O alvo SQLAlchemy tambem nao le credenciais diretamente: a conexao deve ser
aberta somente em homologacao opt-in, com URL no `.env` local.
O orquestrador SQLAlchemy so cria a engine apos validar flag, ambiente, origem
SQLite e URL de homologacao; os testes usam engine fake para evitar rede.
A acao administrativa de homologacao grava apenas relatorio local com URL
mascarada e nao cria arquivo quando a prontidao bloqueia a execucao.
O blueprint SQL PostgreSQL e apenas um artefato tecnico de revisao: nao contem
`INSERT`, nao inclui segredos e nao deve ser executado fora de homologacao.
O pacote ZIP de homologacao apenas consolida esses artefatos locais e inclui
manifesto SHA-256 para conferencia de integridade.
Os comandos de verificacao e resumo do pacote PostgreSQL recalculam hashes,
validam flags de seguranca e bloqueiam revisao quando encontram arquivo
inesperado ou marcador sensivel.
O diagnostico de rede e somente-leitura: ele deixa explicito que SQLite nao deve
ser compartilhado por varias instalacoes escrevendo ao mesmo tempo e que o uso
em rede segue bloqueado ate adapter PostgreSQL, backup restaurado e testes de
concorrencia.

## Prontidao de rede

Gere o JSON local antes de qualquer decisao sobre multiplas instalacoes:

```powershell
uv run python -m basilica_financeiro network-readiness --output documents/exports/prontidao-uso-em-rede.json
```

O arquivo nao abre conexao externa, nao executa migracao e nao contem
credenciais nem linhas financeiras.

Para consolidar a revisao em um pacote local:

```powershell
uv run python -m basilica_financeiro network-validation-package --output documents/exports/pacote-homologacao-rede.zip
```

O ZIP inclui prontidao, checklist manual e manifesto SHA-256; ele continua sem
dados financeiros, segredos, conexao externa ou migracao.

Para conferir o pacote antes da revisao tecnica:

```powershell
uv run python -m basilica_financeiro network-verify-package --package documents/exports/pacote-homologacao-rede.zip --output documents/exports/verificacao-pacote-rede.json
```

Para gerar um resumo Markdown de aceite:

```powershell
uv run python -m basilica_financeiro network-review-summary --package documents/exports/pacote-homologacao-rede.zip --output documents/exports/resumo-aceite-rede.md
```

## Homologacao PostgreSQL administrativa

Para consolidar o estado local da Fase 8 antes das homologacoes externas:

```powershell
uv run python -m basilica_financeiro phase8-acceptance-report --output documents/exports/aceite-local-fase-8.md
```

O relatorio nao encerra a fase sozinho; ele registra que ainda faltam evidencias
reais de Sandbox Asaas e homologacao PostgreSQL descartavel. A tela
"Configuracoes" tambem oferece "Exportar aceite local Fase 8".

Para reunir as evidencias locais em um pacote ZIP com manifesto:

```powershell
uv run python -m basilica_financeiro phase8-evidence-package --output documents/exports/pacote-evidencias-fase-8.zip
```

O pacote inclui apenas metadados locais, prontidoes e hashes; ele nao contem
linhas financeiras nem substitui os gates externos da fase.
A tela "Configuracoes" tambem oferece "Exportar pacote Fase 8".

Para conferir manifesto, hashes e o guard de conclusao pendente:

```powershell
uv run python -m basilica_financeiro phase8-verify-package --package documents/exports/pacote-evidencias-fase-8.zip --output documents/exports/verificacao-pacote-fase-8.json
```

Para gerar um resumo Markdown de aceite local:

```powershell
uv run python -m basilica_financeiro phase8-review-summary --package documents/exports/pacote-evidencias-fase-8.zip --output documents/exports/resumo-aceite-fase-8.md
```

A tela "Configuracoes" tambem oferece "Verificar pacote Fase 8" e
"Exportar resumo Fase 8".

Depois das validacoes reais de Sandbox Asaas e PostgreSQL descartavel, consolide
os artefatos externos em um gate final:

```powershell
uv run python -m basilica_financeiro phase8-closure-readiness --asaas-verification documents/exports/verificacao-pacote-asaas-<id>.json --asaas-summary documents/exports/resumo-aceite-asaas-<id>.md --postgres-package-verification documents/exports/verificacao-pacote-postgresql.json --postgres-report documents/exports/relatorio-homologacao-postgresql.md --phase8-package-verification documents/exports/verificacao-pacote-fase-8.json --output documents/exports/prontidao-fechamento-fase-8.json
```

Esse comando nao chama API, nao abre PostgreSQL e nao executa migracao; ele
apenas le os arquivos informados, confere flags, sucesso e marcadores
sensiveis, e so marca `ready_to_close_phase8=true` quando todos os gates passam.

Com `ready_to_close_phase8=true`, gere o relatorio final de encerramento:

```powershell
uv run python -m basilica_financeiro phase8-closeout-report --closure-readiness documents/exports/prontidao-fechamento-fase-8.json --output documents/exports/encerramento-fase-8.md
```

Se o gate ainda estiver pendente, o relatorio sera gerado como pendente e o
comando retornara codigo 1.

Para arquivar os artefatos finais em ZIP:

```powershell
uv run python -m basilica_financeiro phase8-closeout-package --closure-readiness documents/exports/prontidao-fechamento-fase-8.json --closeout-report documents/exports/encerramento-fase-8.md --output documents/exports/pacote-encerramento-fase-8.zip
```

Atalho recomendado para a fase final:

```powershell
uv run python -m basilica_financeiro phase8-finalize --asaas-verification documents/exports/verificacao-pacote-asaas-<id>.json --asaas-summary documents/exports/resumo-aceite-asaas-<id>.md --postgres-package-verification documents/exports/verificacao-pacote-postgresql.json --postgres-report documents/exports/relatorio-homologacao-postgresql.md --phase8-package-verification documents/exports/verificacao-pacote-fase-8.json --output-dir documents/exports
```

Ele gera `prontidao-fechamento-fase-8.json`, `encerramento-fase-8.md` e
`pacote-encerramento-fase-8.zip` no mesmo diretorio.
A tela "Configuracoes" tambem oferece "Finalizar Fase 8" para gerar esses
artefatos a partir dos arquivos externos ja aprovados.

Se os artefatos estiverem em `documents/exports`, use o atalho:

```powershell
uv run python -m basilica_financeiro phase8-finalize-from-dir --input-dir documents/exports --output-dir documents/exports
```

Use primeiro o comando de prontidao para gerar um JSON local sem conexao externa:

```powershell
uv run python -m basilica_financeiro postgres-readiness --output documents/exports/prontidao-runner-homologacao-postgresql.json
```

Para consolidar os artefatos tecnicos locais em ZIP:

```powershell
uv run python -m basilica_financeiro postgres-validation-package --output documents/exports/pacote-homologacao-postgresql.zip
```

Para conferir manifesto, hashes e flags antes da revisao:

```powershell
uv run python -m basilica_financeiro postgres-verify-package --package documents/exports/pacote-homologacao-postgresql.zip --output documents/exports/verificacao-pacote-postgresql.json
```

Para gerar um resumo Markdown de aceite:

```powershell
uv run python -m basilica_financeiro postgres-review-summary --package documents/exports/pacote-homologacao-postgresql.zip --output documents/exports/resumo-aceite-postgresql.md
```

A tela "Configuracoes" tambem oferece "Verificar pacote PostgreSQL" e
"Exportar resumo PostgreSQL" para gerar os mesmos artefatos sem linha de comando.

Depois use a homologacao apenas em ambiente tecnico, com PostgreSQL vazio e descartavel.
Configure `POSTGRES_REHEARSAL_DATABASE_URL` e
`POSTGRES_REHEARSAL_ENABLE_EXECUTION=true` somente no `.env` local; nunca passe
credenciais pela linha de comando.
Instale um driver PostgreSQL apenas no ambiente de homologacao descartavel,
por exemplo `psycopg`/`psycopg2`, antes de habilitar o runner.

```powershell
uv run python -m basilica_financeiro postgres-rehearsal --confirm-disposable-target
```

Opcionalmente, defina um caminho local para o relatorio:

```powershell
uv run python -m basilica_financeiro postgres-rehearsal --confirm-disposable-target --output documents/exports/relatorio-homologacao-postgresql.md
```

## Prontidao Sandbox Asaas

Antes de qualquer validacao real no Sandbox, gere um JSON local de prontidao
para a solicitacao sensivel. O comando nao chama a API, nao executa cobranca e
nao grava token no arquivo:

```powershell
uv run python -m basilica_financeiro asaas-readiness --request-id 1 --output documents/exports/prontidao-asaas-1.json
```

Quando a solicitacao ja estiver aprovada por dois usuarios e a prontidao indicar
que esta pronta, execute somente em Sandbox:

```powershell
uv run python -m basilica_financeiro asaas-execute --request-id 1 --confirm-sandbox --output documents/exports/execucao-asaas-1.json
```

O arquivo de saida contem apenas status, ID local de execucao, ID externo quando
retornado e chave idempotente; ele nao contem token nem payload financeiro.
A mesma execucao tambem esta disponivel pela tela "Aprovacoes sensiveis" no
botao "Executar Sandbox", mantendo a chave apenas no `.env` local.

Depois da execucao, exporte a evidencia local para revisao:

```powershell
uv run python -m basilica_financeiro asaas-execution-report --request-id 1 --output documents/exports/evidencia-asaas-1.json
```

Esse relatorio nao chama a API e nao inclui resposta bruta do Asaas nem payload
da solicitacao.

Para reunir os artefatos seguros da homologacao em um unico ZIP local:

```powershell
uv run python -m basilica_financeiro asaas-validation-package --request-id 1 --output documents/exports/pacote-homologacao-asaas-1.zip
```

O pacote inclui checklist, prontidao, evidencia e manifesto com hashes SHA-256;
ele nao contem credenciais nem resposta bruta da API.

Para conferir o manifesto e os hashes do pacote:

```powershell
uv run python -m basilica_financeiro asaas-verify-package --package documents/exports/pacote-homologacao-asaas-1.zip --output documents/exports/verificacao-pacote-asaas-1.json
```

Para gerar um resumo Markdown de aceite para revisao tecnica:

```powershell
uv run python -m basilica_financeiro asaas-review-summary --package documents/exports/pacote-homologacao-asaas-1.zip --output documents/exports/resumo-aceite-asaas-1.md
```
