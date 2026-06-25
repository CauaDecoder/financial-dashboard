# ADR-003 - Persistencia local

## Status

Aceita inicialmente.

## Contexto

O sistema precisa funcionar offline em Windows, com caminho futuro para banco central ou criptografia mais forte.

## Decisao

Usar SQLite local na Fase 1, com SQLAlchemy/Alembic como trilho formal de modelo e migracao.

## Consequencias

- O aplicativo funciona sem servidor.
- A base atual continua usando `sqlite3` diretamente nos repositorios pequenos da fundacao.
- As proximas fases devem migrar regras financeiras para repositorios orientados por modelos SQLAlchemy quando o ambiente Python estiver verificavel.
- SQLCipher permanece como endurecimento planejado depois da prova de empacotamento.
