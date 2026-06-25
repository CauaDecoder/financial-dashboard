# ADR-008 - Planejamento financeiro local

## Status

Aceita.

## Contexto

A fase de recursos avancados pede orcamento, projecoes e apoio a categorizacao.
Esses recursos lidam com informacoes sensiveis de planejamento institucional e
nao dependem, neste primeiro incremento, de APIs externas.

## Decisao

Implementar orcamentos, projecoes e regras de categorizacao no banco SQLite
local. As projecoes usam titulos em aberto ja registrados no sistema, e as
regras de categorizacao sao avaliadas localmente por palavra-chave. O orcamento
anual e distribuido em 12 orcamentos mensais, de forma linear ou sazonal por
pesos mensais positivos, para manter o comparativo simples.
As metas anuais exibidas na tela de planejamento sao derivadas da soma dos
orcamentos mensais locais, comparadas com lancamentos postados do mesmo ano.
Sugestoes de categoria podem preencher formularios, mas nunca confirmam
lancamentos sem acao explicita do operador. No wizard de importacao, regras
locais tambem podem preencher categorias e centros vazios, mas a origem da
classificacao aparece na pre-visualizacao antes da gravacao. Os primeiros
graficos nativos de planejamento usam Qt Charts para comparar metas anuais com o
realizado, exibir a projecao de caixa acumulada e apresentar categorias e
centros de custo do dashboard avancado. Tabelas e barras nativas do PySide6
permanecem como detalhamento. Relatorios auxiliares de categorizacao sao CSV
locais gerados a partir da pre-visualizacao. Perfis personalizados de dashboard
tambem sao salvos localmente, registrando apenas preferencias de periodo,
limite, alertas e secoes visiveis.

## Consequencias

- O recurso funciona offline e sem novos segredos de configuracao.
- Nao ha exposicao de descricoes financeiras para servicos externos.
- A comparacao orcado vs realizado fica auditavel e reproduzivel.
- A distribuicao sazonal permite reforcar meses especificos sem criar outra
  estrutura persistente de metas.
- Metas anuais reaproveitam a tabela de orcamentos e evitam duplicar a fonte de
  verdade do planejamento.
- Recursos futuros que automatizem mais etapas devem preservar confirmacao
  manual e trilha de auditoria.
- Graficos dedicados podem ser expandidos com Qt Charts, mantendo as agregacoes
  no servico local de analytics.
- Relatorios de importacao ajudam a auditar regras sugeridas sem criar novo
  estado persistente.
- Dashboards personalizados ficam auditaveis sem armazenar credenciais ou
  configuracoes sensiveis.
