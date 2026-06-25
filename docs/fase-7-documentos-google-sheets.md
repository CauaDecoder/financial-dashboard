# Fase 7 - Google Sheets e documentos

Esta fase foi iniciada com armazenamento local de documentos/anexos, controle de
integridade por SHA-256 e preparacao segura para Google Sheets. O sistema ainda
nao guarda credenciais Google no codigo nem no banco.

## Entregue nesta etapa

- Tabelas `documents` e `document_links`.
- Tabela `google_sheet_imports` para historico de importacoes Google Sheets.
- Servico de anexos com copia controlada para `documents/`.
- Calculo de SHA-256 para cada arquivo anexado.
- Reuso do mesmo documento por hash, evitando copias duplicadas.
- Vinculos de documentos com:
  - lancamentos financeiros
  - titulos a pagar/receber
  - fornecedores
  - pedidos de compra
- Tela PySide6 "Documentos" para anexar arquivos, abrir o arquivo armazenado e
  visualizar historico de Google Sheets.
- Configuracao `GOOGLE_CLIENT_SECRET_PATH` e `GOOGLE_TOKEN_PATH` apenas via `.env`.
- Servico de status Google Sheets que verifica arquivos locais sem persistir
  segredo.

## Seguranca e integridade

- O `.env` continua fora do versionamento.
- Credenciais e tokens Google ficam somente em arquivos locais configurados pelo
  operador.
- O banco guarda apenas caminhos, metadados e hash dos documentos.
- Os anexos sao copiados para a pasta controlada da aplicacao.
- O SHA-256 permite detectar troca ou corrupcao de arquivo.

## Limitacoes atuais

- A importacao OAuth real do Google Sheets ainda nao consome a API.
- A tela registra e exibe historico de importacoes, mas a leitura online depende
  de credenciais e escopos a validar com a conta da Basilica.
- A visualizacao interna de PDF ainda usa o aplicativo padrao do sistema.
- Anexos ainda nao aparecem diretamente dentro de cada tela de lancamento,
  fornecedor ou compra.

## Proximos passos

1. Criar credenciais OAuth Google no console da conta autorizada.
2. Salvar `client_secret.json` fora do repositorio e apontar
   `GOOGLE_CLIENT_SECRET_PATH` no `.env`.
3. Gerar o token local fora do repositorio e apontar `GOOGLE_TOKEN_PATH`.
4. Definir quais planilhas Google Sheets entram no fluxo oficial.
5. Implementar leitura autenticada das abas e reutilizar o wizard de importacao
   existente para validar/mapear colunas.
6. Adicionar botao de anexos diretamente nas telas de lancamentos, fornecedores
   e compras.
