# Fase 4 - Integracao Asaas leitura-only

## Inicio implementado

Esta fase foi iniciada com integracao somente leitura para cobrancas do Asaas,
mantendo a chave de API fora do codigo e usando snapshots locais para apoiar
conciliacao.

Implementado ate aqui:

- Configuracao `ASAAS_API_KEY` carregada apenas do `.env`.
- Ambientes `sandbox` e `production` via `ASAAS_ENV`.
- Cliente Asaas isolado em `services/asaas.py`.
- Uso de `GET /v3/payments` para listar cobrancas de forma paginada.
- Transporte HTTP injetavel para testes sem rede.
- Tabela local `asaas_payments` para snapshots de cobrancas.
- Tabela local `asaas_reconciliations` para aceite manual auditavel.
- Migracao Alembic `0006_asaas_payments`.
- Migracao Alembic `0007_asaas_reconciliations`.
- Sincronizacao manual com auditoria de lote.
- Degradacao amigavel quando a chave nao esta configurada ou o Asaas esta indisponivel.
- Tela PySide6 "Asaas" com status, botao de sincronizacao, snapshots e sugestoes.
- Filtros locais por status, texto e periodo na tela Asaas.
- Sugestao de conciliacao obvia por mesmo valor e mesma data de recebimento.
- Botao para aceitar conciliacao selecionada, sem alterar valores nem saldo.
- Lista de conciliacoes aceitas.
- Botao para desconciliar manualmente preservando historico.
- Testes com mock para cliente, sincronizacao, snapshots e conciliacao.

## Regras preservadas

- Nenhuma chave de API entra no codigo, nos testes de producao ou na interface.
- A integracao nao cria cobrancas, nao paga contas e nao executa transferencias.
- A sincronizacao nao altera saldo de contas financeiras automaticamente.
- Nenhuma sugestao vira conciliacao definitiva sem aceite manual do usuario.
- Desconciliacao cancela o vinculo sem apagar o registro original.
- A chave nao aparece nas mensagens de erro, auditoria ou tabelas da interface.
- As chamadas usam HTTPS e endpoints oficiais por ambiente.
- A Fase 4 usa polling manual conforme ADR-004.

## Referencias oficiais consultadas

- Comece por aqui: https://docs.asaas.com/reference/comece-por-aqui
- Chaves de API: https://docs.asaas.com/docs/chaves-de-api.md
- Listar cobrancas: https://docs.asaas.com/reference/listar-cobrancas.md

## Proximos passos da Fase 4

- Validar no Sandbox real do Asaas com uma chave configurada no `.env` local.
- Ajustar valores padrao dos filtros conforme o uso real dos dizimos e cobrancas.
- Melhorar filtros visuais de cobrancas, sugestoes e conciliacoes aceitas.
- Validar com a equipe se sincronizacao agendada deve entrar em fase futura.

## Passos para seguir para o proximo bloco

1. Criar ou acessar conta Sandbox do Asaas.
2. Configurar `ASAAS_API_KEY` apenas no `.env` local.
3. Sincronizar cobrancas pela tela Asaas.
4. Aplicar filtros por status, texto e periodo.
5. Conferir se os matches obvios aparecem com as receitas ja registradas.
6. Aceitar manualmente uma conciliacao e revisar a trilha de auditoria.
7. Desconciliar manualmente e confirmar que a sugestao volta a aparecer.
