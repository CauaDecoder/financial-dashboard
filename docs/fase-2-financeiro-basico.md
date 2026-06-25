# Fase 2 - Financeiro basico

## Inicio implementado

Esta fase foi iniciada com o nucleo de dominio financeiro e os primeiros fluxos
operacionais da interface desktop.

Implementado ate aqui:

- Contas financeiras com saldo inicial e saldo atual em centavos.
- Categorias de receita e despesa.
- Centros de custo.
- Lancamentos de receita e despesa.
- Lancamentos parcelados e recorrentes mensais.
- Transferencias entre contas com par de movimentacoes vinculado.
- Resultado financeiro ignora transferencias internas.
- Auditoria das operacoes financeiras iniciais.
- Tela PySide6 de consulta de contas financeiras.
- Formulario PySide6 para criar contas financeiras.
- Tela PySide6 de lancamentos.
- Filtros PySide6 de lancamentos por tipo, categoria e centro de custo.
- Formularios PySide6 para receita, despesa e transferencia.
- Formularios PySide6 para categorias e centros de custo.
- Contas a pagar e a receber com vencimento, contraparte e status operacional.
- Contas a pagar e receber parceladas ou recorrentes mensais.
- Baixa parcial ou total de titulos, gerando receita ou despesa no caixa.
- Status efetivo de vencido calculado para titulos em aberto ou parciais.
- Tela PySide6 de pagar e receber com criacao e baixa de titulos.
- Filtros PySide6 de pagar/receber por tipo, categoria, centro de custo e status.
- Dashboard PySide6 com saldo, receitas, despesas, resultado e pendencias.
- Exportacao inicial de relatorio financeiro XLSX com resumo, fluxo e titulos.
- Exportacao PDF com cabecalho institucional da Basilica.
- Backup automatico diario configuravel via `.env`.
- Cancelamento logico de lancamentos com reversao do saldo.
- Cancelamento logico de contas a pagar/receber ainda nao pagas.
- Testes preparados para saldo, fluxo de caixa, transferencia neutra e bloqueio de `float`.
- Testes de contas a pagar/receber, baixa parcial, baixa total e vencidos.
- Testes de filtros por tipo, categoria, centro de custo e status.
- Testes de parcelamento, recorrencia, distribuicao exata de centavos e datas de fim de mes.
- Testes da exportacao XLSX sem dependencia externa.
- Testes da exportacao PDF sem dependencia externa.
- Testes do backup automatico diario.
- Testes de cancelamento logico para lancamentos, transferencias e titulos.
- Conversao BRL para centavos sem `float`.
- Build PyInstaller atualizado apos os formularios iniciais.

## Regras preservadas do planejamento

- Valores monetarios usam `int` em centavos.
- Transferencias nao entram como receita ou despesa.
- Operacoes financeiras geram auditoria.
- Nao ha exclusao fisica de registros financeiros nesta etapa.
- Titulos pagos ou cancelados nao aceitam nova baixa.
- Baixas acima do valor em aberto sao rejeitadas.
- Lancamentos cancelados saem do fluxo de caixa e revertem o saldo contabilizado.
- Transferencias canceladas revertem as duas contas do par vinculado.
- Backup automatico depende de `BACKUP_ENCRYPTION_KEY` no ambiente e nao grava segredo no codigo.
- Parcelas distribuem centavos sem `float`, com diferenca residual na ultima parcela.
- Recorrencias mantem o valor cheio para cada ocorrencia.
- Formularios financeiros validam campos obrigatorios antes de registrar operacoes.
- Integracoes externas continuam fora do codigo e sem chaves versionadas.

## Proximos passos da Fase 2

- Revisao manual dos fluxos principais antes de abrir Fase 3.

## Passos para seguir para o proximo bloco

1. Validar manualmente no aplicativo os fluxos de criar conta a pagar, criar conta a receber
   e baixar um titulo.
2. Validar manualmente as exportacoes XLSX e PDF pelo dashboard.
3. Validar manualmente parcelamento e recorrencia nos formularios de lancamentos e titulos.
4. Fechar Fase 2 com revisao manual dos fluxos principais.
