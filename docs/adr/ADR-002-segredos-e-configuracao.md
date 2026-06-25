# ADR-002 - Segredos e configuracao

## Status

Aceita.

## Contexto

O sistema terá integrações futuras com Asaas e Google Sheets, além de senha inicial, chave de sessão e chave de backup.

## Decisão

Segredos ficam fora do código e fora do versionamento. O repositório mantém apenas `.env.example`; o `.env` real é ignorado.

## Consequências

- Chaves de API não aparecem no código.
- O primeiro administrador só é criado quando `DEFAULT_ADMIN_PASSWORD` estiver configurada localmente.
- Backups criptografados exigem `BACKUP_ENCRYPTION_KEY`.
