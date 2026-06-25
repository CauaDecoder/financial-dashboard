# Fase 3 - Importacoes

## Inicio implementado

Esta fase foi iniciada com importacao padronizada de movimentacoes financeiras por
CSV e XLSX, sem dependencias externas novas e mantendo validacao antes de qualquer
gravacao.

Implementado ate aqui:

- Template CSV para importacao financeira.
- Template XLSX para importacao financeira.
- Template CSV para importacao de contas a pagar/receber previstas.
- Template XLSX para importacao de contas a pagar/receber previstas.
- Leitura de arquivos `.csv` com deteccao simples de delimitador.
- Leitura de arquivos `.xlsx` com primeira aba da planilha.
- Colunas padrao: `tipo`, `data`, `descricao`, `valor`, `conta`, `categoria`,
  `centro_custo`.
- Pre-validacao de arquivo antes de importar.
- Relatorio interno de linhas validas, erros e duplicatas.
- Relatorio CSV exportavel de erros com numero de linha.
- Deteccao de duplicatas por hash normalizado da linha.
- Importacao de receitas e despesas como movimentacoes financeiras realizadas.
- Atualizacao do saldo da conta durante a importacao.
- Identificador externo `import:<hash>` para evitar reimportacao.
- Identificador externo `due-import:<hash>` para evitar reimportacao de titulos.
- Tela PySide6 para gerar templates e importar arquivo.
- Pre-visualizacao tabular antes da gravacao.
- Confirmacao explicita antes da gravacao.
- Mapeamento simples de colunas alternativas no servico de importacao.
- Mapeamento manual de colunas na interface para planilhas fora do template.
- Exportacao CSV de relatorio financeiro com separador `;` e valores em formato BR.
- Importacao de titulos previstos sem alterar saldo de contas antes da baixa.
- Testes para CSV, XLSX, duplicatas, mapeamento, titulos previstos e rejeicao
  de arquivo com erro.

## Regras preservadas

- Valores monetarios continuam em centavos inteiros.
- Arquivos com erros de validacao nao gravam nenhuma linha.
- Contas, categorias e centros de custo precisam existir antes da importacao.
- Titulos previstos importados entram como abertos e nao impactam o caixa realizado.
- Importacoes geram auditoria de lote.
- Nenhum segredo ou chave de API entra no codigo.
- Parsing de XLSX rejeita declaracoes XML inseguras antes de processar o arquivo.

## Proximos passos da Fase 3

- Validar com arquivos reais de extratos ou planilhas internas da Basilica.
- Ajustar o mapeamento visual se os arquivos reais usarem layouts com cabecalhos em linhas diferentes.
- Revisar com a equipe se os nomes `pagar`/`receber` cobrem as planilhas reais.

## Passos para seguir para o proximo bloco

1. Validar manualmente a importacao com o template CSV.
2. Validar manualmente a importacao com o template XLSX.
3. Testar reimportacao do mesmo arquivo para confirmar duplicatas ignoradas.
4. Validar manualmente templates de titulos previstos e baixa posterior no modulo
   Pagar e receber.
