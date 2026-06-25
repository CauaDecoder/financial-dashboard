# ADR-005 - Integracao PDV via banco compartilhado vs API local

## Status

Aceita para a Fase 5.

## Contexto

O roadmap preve integracao com o PDV existente para ler produtos, categorias,
estoque e vendas. O documento original informa que o PDV tambem usa
Python/Tkinter/SQLite, mas o schema real ainda precisa ser validado.

## Decisao

Usar integracao leitura-only por banco SQLite compartilhado na Fase 5, com
contrato de tabelas ou views estaveis. O financeiro abre o banco do PDV em modo
read-only, grava snapshots locais e importa vendas pagas para receitas com
deduplicacao por identificador externo.

## Alternativas consideradas

- API local no PDV: melhor isolamento, mas exige alterar e publicar uma nova
  versao do PDV antes de validar valor de negocio.
- Importacao manual por CSV: mais simples, mas aumenta retrabalho e risco de
  dupla contagem.
- Escrita direta no PDV: rejeitada nesta fase por risco operacional.

## Consequencias

- A Fase 5 consegue avancar sem acoplar regras financeiras ao PDV.
- O contrato pode ser atendido por views se o schema real tiver outros nomes.
- Alteracoes futuras no PDV devem preservar as views ou incrementar o contrato.
- Uma API local pode substituir este adapter depois sem alterar as tabelas de
  snapshot nem o fluxo financeiro.
