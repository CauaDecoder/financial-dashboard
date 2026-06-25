# ADR-010 - Executor idempotente para escrita no Asaas

## Status

Aceita.

## Contexto

A Fase 8 preve operacoes de escrita no Asaas, mas essas operacoes so podem
ocorrer depois de aprovacao dupla e com protecoes contra repeticao acidental.
Tambem e necessario manter a aplicacao segura por padrao, sem acionar API
externa apenas porque uma solicitacao foi aprovada.

## Decisao

Implementar um executor local para solicitacoes sensiveis aprovadas, mantendo a
execucao real desabilitada por padrao por `ASAAS_ENABLE_WRITE_OPERATIONS=false`.
O executor so aceita solicitacoes com status `approved`, exige `ASAAS_API_KEY`
configurada via `.env`, usa uma chave idempotente derivada do ID da solicitacao
e registra a tentativa em `sensitive_operation_executions`.

Se ja existir execucao para uma solicitacao, o executor retorna o registro local
existente e nao chama o transporte novamente. Em sucesso, a solicitacao passa
para `executed`. Em falha, a tentativa fica registrada como `failed` e a
solicitacao permanece aprovada para analise manual.

Neste incremento, a execucao foi coberta por transporte mockado em testes. A
habilitacao real em ambiente de producao ainda exige validacao com Sandbox,
revisao dos payloads esperados pela API Asaas e decisao operacional explicita.

## Consequencias

- Escrita externa continua bloqueada por padrao.
- Aprovacao dupla e pre-condicao tecnica para qualquer execucao.
- A chave idempotente evita repeticao silenciosa da mesma solicitacao.
- Falhas ficam auditaveis sem transformar a solicitacao em executada.
- Testes conseguem validar o fluxo sem rede e sem chaves reais.
- A UI de execucao real deve ser adicionada somente depois de validar o fluxo
  com a equipe e com o Sandbox do Asaas.
