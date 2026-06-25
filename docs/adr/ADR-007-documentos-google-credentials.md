# ADR-007 - Documentos locais e credenciais Google

## Status

Aceita para o primeiro incremento da Fase 7.

## Contexto

A Fase 7 pede anexos de PDFs/documentos e importacao de Google Sheets. O projeto
tambem exige que nenhum segredo seja colocado no codigo ou versionado.

## Decisao

Armazenar documentos em pasta local controlada pela aplicacao, com metadados e
SHA-256 no banco. Para Google Sheets, guardar no banco apenas historico de
importacoes e exigir que credenciais/tokens fiquem em arquivos locais indicados
por `.env`.

## Alternativas consideradas

- Gravar PDFs diretamente no banco: rejeitado por aumentar o tamanho do SQLite e
  dificultar backup incremental.
- Versionar arquivos de credencial Google: rejeitado por risco critico de
  vazamento de segredo.
- Implementar OAuth antes de validar a conta Google oficial: adiado para evitar
  escopos ou fluxos incorretos.

## Consequencias

- Backups precisam incluir a pasta `documents/`.
- A integridade dos anexos pode ser auditada pelo SHA-256.
- A leitura Google Sheets pode evoluir sem migrar metadados.
- A configuracao local continua simples e segura para ambiente desktop.
