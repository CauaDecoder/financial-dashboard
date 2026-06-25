# ADR-004 - Asaas polling vs webhooks

## Status

Aceita inicialmente.

## Contexto

A Fase 4 precisa integrar cobrancas do Asaas em modo leitura-only, mantendo o
aplicativo desktop funcional offline e sem servidor remoto. Webhooks exigiriam
endpoint publico, gerenciamento de disponibilidade e validacao de eventos
recebidos fora da maquina local.

## Decisao

Usar sincronizacao manual por polling na Fase 4. O sistema consulta a API do
Asaas quando o operador aciona a sincronizacao, grava snapshots locais e permite
conciliacao manual auditavel. Webhooks ficam adiados ate existir arquitetura com
servidor ou servico confiavel para receber eventos.

## Consequencias

- Mantem o aplicativo desktop simples e sem porta publica exposta.
- Preserva funcionamento offline com degradacao amigavel quando a internet falha.
- Reduz risco de segredo/API em infraestrutura externa prematura.
- A sincronizacao nao e em tempo real; o operador precisa acionar ou, em fase
  futura, autorizar uma rotina agendada.
- Antes de webhooks, sera necessario definir validacao de assinatura/eventos,
  retentativas, idempotencia e monitoramento.
