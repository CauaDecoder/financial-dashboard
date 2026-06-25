# ADR-006 - Compras e entrada de estoque

## Status

Aceita para o primeiro incremento da Fase 6.

## Contexto

O roadmap da Fase 6 pede fornecedores, fluxo completo de compras, recebimento
parcial, entrada no estoque integrada ao PDV e geracao automatica de conta a
pagar. A Fase 5 iniciou a integracao com o PDV em modo leitura-only, e o schema
real do PDV ainda precisa ser validado.

## Decisao

Registrar a entrada no estoque como uma etapa auditavel do pedido de compra,
sem escrever no banco do PDV neste incremento. A conta a pagar so pode ser
gerada depois da etapa `stock_entered`.

## Alternativas consideradas

- Escrever diretamente no banco do PDV: rejeitado por risco de corromper estoque
  sem contrato real validado.
- Criar estoque duplicado no financeiro: rejeitado porque geraria duas fontes de
  verdade.
- Bloquear a Fase 6 ate o PDV real estar disponivel: rejeitado porque fornecedores
  e contas a pagar ja agregam valor sem essa escrita.

## Consequencias

- O financeiro controla o fluxo de compra e a obrigacao a pagar com seguranca.
- A entrada no estoque fica pronta para ser conciliada com o PDV depois.
- O proximo incremento deve mapear itens do pedido para produtos do PDV antes de
  qualquer escrita em estoque.
