# Fase 8 - Roteiro de validacao Sandbox Asaas

## Objetivo

Validar o executor idempotente de escrita no Asaas em ambiente Sandbox, sem
versionar credenciais e sem habilitar operacoes reais por acidente.

## Pre-condicoes

- Solicitar uma chave Sandbox diretamente no painel Asaas.
- Salvar a chave somente no `.env` local, nunca em codigo, docs ou testes.
- Usar uma base local descartavel ou backup recente antes da validacao.
- Criar usuarios distintos para solicitante e dois aprovadores.

## Configuracao local

No `.env` local:

```env
ASAAS_ENV=sandbox
ASAAS_API_KEY=preencher-apenas-no-ambiente-local
ASAAS_ENABLE_WRITE_OPERATIONS=true
```

Ao encerrar a validacao, voltar:

```env
ASAAS_ENABLE_WRITE_OPERATIONS=false
```

## Fluxo de validacao

1. Criar uma solicitacao em "Aprovacoes sensiveis" para `asaas_create_charge`.
2. Usar payload minimo de Sandbox, sem chave nem token:

```json
{
  "customer_id": "preencher-id-cliente-sandbox",
  "description": "Validacao Sandbox Basilica Financeiro",
  "value_cents": 1000
}
```

3. Aprovar com dois usuarios distintos.
4. Abrir o detalhe da solicitacao e confirmar que "Prontidao de execucao"
   informa que a operacao esta pronta para Sandbox controlado.
5. Exportar a mesma prontidao pela tela "Aprovacoes sensiveis" no botao
   "Exportar prontidao" ou por CLI, sem chamar API e sem expor token:

```powershell
uv run python -m basilica_financeiro asaas-readiness --request-id <id> --output documents/exports/prontidao-asaas-<id>.json
```

6. Revisar o JSON gerado e confirmar `contains_credentials=false`,
   `opens_external_connection=false` e `executes_write_operation=false`.
7. Executar o executor idempotente em ambiente controlado pela tela
   "Aprovacoes sensiveis" no botao "Executar Sandbox" ou por CLI, usando
   somente `ASAAS_ENV=sandbox` e a flag explicita:

```powershell
uv run python -m basilica_financeiro asaas-execute --request-id <id> --confirm-sandbox --output documents/exports/execucao-asaas-<id>.json
```

   O comando bloqueia ambiente de producao, nao recebe token por argumento e
   grava apenas resumo local sem credenciais. A UI tambem bloqueia producao,
   exige confirmacao digitando `SANDBOX` e registra a tentativa localmente.
8. Conferir no painel Sandbox se a cobranca foi criada.
9. Exportar a evidencia local pos-execucao:

```powershell
uv run python -m basilica_financeiro asaas-execution-report --request-id <id> --output documents/exports/evidencia-asaas-<id>.json
```

   Revisar que o arquivo marca `contains_credentials=false`,
   `contains_request_payload=false`, `contains_api_response=false`,
   `opens_external_connection=false` e `executes_write_operation=false`.
   A mesma evidencia tambem pode ser exportada pela tela "Aprovacoes
   sensiveis" no botao "Exportar evidencia".
10. Gerar o pacote local de homologacao para revisao tecnica:

```powershell
uv run python -m basilica_financeiro asaas-validation-package --request-id <id> --output documents/exports/pacote-homologacao-asaas-<id>.zip
```

   O pacote contem checklist, prontidao, evidencia e manifesto SHA-256; ele nao
   chama a API e nao inclui token, payload da solicitacao ou resposta bruta.
   A mesma exportacao tambem esta disponivel pela tela "Aprovacoes sensiveis"
   no botao "Exportar pacote".
11. Conferir o pacote local antes de revisao:

```powershell
uv run python -m basilica_financeiro asaas-verify-package --package documents/exports/pacote-homologacao-asaas-<id>.zip --output documents/exports/verificacao-pacote-asaas-<id>.json
```

   Revisar que `ready_for_review=true`, `hashes_valid=true`,
   `safe_flags_valid=true` e `contains_disallowed_markers=false`.
12. Gerar o resumo Markdown de aceite para revisao tecnica:

```powershell
uv run python -m basilica_financeiro asaas-review-summary --package documents/exports/pacote-homologacao-asaas-<id>.zip --output documents/exports/resumo-aceite-asaas-<id>.md
```

   O resumo e derivado da verificacao local, nao chama API e nao inclui
   token, payload financeiro ou resposta bruta.
   A mesma exportacao tambem esta disponivel pela tela "Aprovacoes sensiveis"
   no botao "Exportar resumo"; a UI gera o pacote ZIP seguro junto do resumo.
13. Abrir o detalhe da solicitacao e conferir:
   - status da solicitacao como `executed`;
   - execucao com status `succeeded`;
   - chave idempotente iniciando com `basilica-sensitive-operation-`;
   - ID externo preenchido.
14. Rodar a mesma execucao uma segunda vez e confirmar que nenhuma nova cobranca
   e criada; o sistema deve reaproveitar a execucao local.
15. Desligar `ASAAS_ENABLE_WRITE_OPERATIONS` ao final.

## Criterios de aceite

- Nenhum segredo aparece em logs, docs, auditoria ou payload de solicitacao.
- O JSON de prontidao exportado nao contem token e nao executa chamada externa.
- O JSON de execucao exportado nao contem token nem payload financeiro.
- A evidencia pos-execucao nao contem token, payload da solicitacao nem resposta
  bruta da API.
- O pacote ZIP de homologacao contem manifesto com hashes e apenas artefatos
  sanitizados.
- A verificacao do pacote confirma hashes, arquivos esperados e flags de
  seguranca antes da revisao.
- O resumo de aceite Markdown consolida os gates locais sem segredos.
- A solicitacao so executa apos duas aprovacoes distintas.
- Repetir a execucao nao gera segunda chamada nem segunda cobranca.
- Falha do Asaas registra tentativa como `failed` sem marcar a solicitacao como
  executada.
- O executavel continua iniciando com `ASAAS_ENABLE_WRITE_OPERATIONS=false`.

## Nao fazer

- Nao usar chave de producao nesta etapa.
- Nao colar a chave em prints, documentos ou commits.
- Nao passar chave Asaas por argumento de terminal.
- Nao habilitar escrita em maquina compartilhada sem backup e supervisao.
