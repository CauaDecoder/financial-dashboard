# Fase 6 - Compras e fornecedores

Esta fase foi iniciada com um fluxo local e auditavel para fornecedores,
pedidos de compra, recebimentos e geracao de contas a pagar. A entrada de
estoque fica registrada como etapa operacional do pedido, mas o sistema ainda
nao escreve no banco do PDV.

## Entregue nesta etapa

- Cadastro de fornecedores com contato, documento e status ativo/inativo.
- Pedidos de compra com fornecedor, descricao, valor total e data prevista.
- Fluxo controlado de etapas:
  - solicitacao (`requested`)
  - cotacao (`quoted`)
  - aprovacao (`approved`)
  - pedido enviado (`ordered`)
  - recebimento parcial (`partially_received`)
  - recebido (`received`)
  - conferido (`checked`)
  - entrada no estoque (`stock_entered`)
  - conta a pagar gerada (`payable_generated`)
  - encerrado (`closed`)
- Recebimento parcial ou total com controle para nao exceder o valor da compra.
- Geracao automatica de conta a pagar a partir de compra com entrada no estoque.
- Auditoria para criacao de fornecedor, criacao/avanco/recebimento de compra e
  geracao de titulo financeiro.
- Tela PySide6 "Compras" com fornecedores, pedidos, avancar etapa, recebimento
  e geracao de conta a pagar.
- Testes automatizados cobrindo fluxo feliz, transicoes invalidas, recebimento
  acima do total e bloqueio de duplicidade na conta a pagar.

## Seguranca e integridade

- Nao ha segredos ou credenciais neste modulo.
- Fornecedores podem ser inativados, nao apagados fisicamente.
- Pedidos cancelados permanecem no historico.
- Toda geracao financeira passa pelo modulo existente de contas a pagar.
- Valores monetarios permanecem em centavos inteiros.

## Limitacoes atuais

- Nao ha itens detalhados por produto no pedido; o pedido registra valor total.
- A etapa "entrada no estoque" ainda e operacional, sem escrita no PDV.
- Anexos de NF, comprovantes e contratos entram na Fase 7.
- Ainda nao ha aprovacao dupla nem perfis dedicados para compras.

## Proximos passos

1. Validar com a equipe se o fluxo de etapas cobre o processo real de compras.
2. Definir quais campos de fornecedor sao obrigatorios na rotina da Basilica.
3. Mapear produtos do pedido para produtos do PDV quando o contrato real do PDV
   estiver validado.
4. Evoluir pedidos para itens por produto, quantidade e preco unitario.
5. Na Fase 7, anexar NF, comprovantes e contratos aos fornecedores e compras.
