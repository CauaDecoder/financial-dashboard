# Fase 5 - Estoque e PDV

Esta fase foi iniciada com uma integracao leitura-only com o banco SQLite do PDV.
O financeiro nao altera o banco de origem: ele le tabelas ou views de contrato,
grava snapshots locais e importa vendas pagas como receitas idempotentes.

## Entregue nesta etapa

- Configuracao `PDV_DATABASE_URL` lida somente do `.env`.
- Tabelas locais `pdv_categories`, `pdv_products` e `pdv_sales`.
- Cliente de leitura SQLite em modo read-only (`mode=ro`).
- Sincronizacao de categorias, produtos, estoque e vendas.
- Importacao de vendas pagas como receitas financeiras.
- Deduplicacao por `external_id = pdv:sale:{id}`.
- Tela PySide6 "PDV e estoque" com resumo, produtos, vendas e importacao.
- Testes com banco PDV fake para validar contrato, snapshots e idempotencia.
- ADR-005 documentando banco compartilhado vs API local.

## Contrato esperado do PDV

O financeiro espera que o PDV exponha as seguintes tabelas ou views estaveis:

### `pdv_categories`

| Campo | Tipo esperado | Observacao |
|---|---|---|
| `id` | texto ou inteiro | Identificador unico no PDV |
| `name` | texto | Nome da categoria |

### `pdv_products`

| Campo | Tipo esperado | Observacao |
|---|---|---|
| `id` | texto ou inteiro | Identificador unico no PDV |
| `category_id` | texto, inteiro ou nulo | Referencia para `pdv_categories.id` |
| `sku` | texto ou nulo | Codigo interno |
| `name` | texto | Nome do produto |
| `price_cents` | inteiro | Preco em centavos |
| `stock_quantity` | numero | Quantidade atual |
| `stock_value_cents` | inteiro | Valor total do estoque em centavos |
| `is_active` | inteiro/bool | 1 para ativo, 0 para inativo |

### `pdv_sales`

| Campo | Tipo esperado | Observacao |
|---|---|---|
| `id` | texto ou inteiro | Identificador unico da venda |
| `sold_at` | texto ISO | Data/hora da venda |
| `total_cents` | inteiro | Total em centavos |
| `payment_method` | texto ou nulo | Forma de pagamento |
| `status` | texto | `paid`, `completed`, `closed`, `finalizada` ou `concluida` importam receita |

## Seguranca

- O caminho do PDV fica apenas no `.env`.
- O banco do PDV e aberto em modo somente leitura.
- Nenhuma credencial ou chave e armazenada no codigo.
- O snapshot local preserva `raw_json` para auditoria tecnica.
- A importacao para receitas e idempotente por identificador externo.

## Limitacoes atuais

- O contrato ainda precisa ser comparado com o schema real do PDV.
- A Fase 5 ainda nao faz baixa de estoque nem escreve no PDV.
- Dashboards de curva ABC e posicao detalhada de estoque ficam para o proximo incremento.
- A associacao de venda com categorias/centros financeiros e definida no momento da importacao.

## Proximos passos

1. Obter uma copia do banco SQLite real do PDV.
2. Criar views de compatibilidade com os nomes `pdv_categories`, `pdv_products` e `pdv_sales`.
3. Configurar `PDV_DATABASE_URL` no `.env` local.
4. Sincronizar pela tela "PDV e estoque".
5. Validar contagem de produtos, valor de estoque e vendas pagas contra o PDV real.
6. Importar um pequeno periodo de vendas para uma conta de teste e conferir saldos.
