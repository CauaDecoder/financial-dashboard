# Fase 1 - Fundacao tecnica

## Status

Concluida em 2026-06-16 para o escopo tecnico inicial.

## Implementado nesta iteracao

- Estrutura de projeto Python em `src/`.
- Configuracao por `.env`, com `.env.example` versionado e `.env` ignorado.
- `pyproject.toml` com PySide6, SQLAlchemy, Alembic, pytest, ruff e mypy.
- Schema SQLite inicial com usuarios, sessoes, perfis, permissoes, auditoria e historico de backup.
- Trilha Alembic em `migrations/` para evoluir o schema formalmente.
- Hash de senha com Argon2id.
- Bloqueio depois de 5 tentativas de login sem sucesso.
- Primeiro administrador criado somente com `DEFAULT_ADMIN_PASSWORD` local.
- Auditoria de login, criacao de usuario e backup.
- Backup manual criptografado com Fernet.
- Restauracao de backup com verificacao de integridade e backup preventivo.
- UI PySide6 com login, menu lateral, usuarios/perfis, auditoria, backup e restauracao.
- Testes automatizados, lint e typecheck executados em `.venv`.
- Smoke test visual PySide6 em modo offscreen com captura temporaria da tela de login.
- Build inicial com PyInstaller gerando `dist/Basilica Financeiro`.
- Smoke test do executavel empacotado no Windows.

## Evidencias de validacao

- `python -m pytest`: 17 testes passando, cobertura acima de 80%.
- `python -m ruff check .`: sem erros.
- `python -m mypy src`: sem erros.
- Varredura de segredos: sem chaves ou tokens versionados.
- PyInstaller: build `onedir` concluido com sucesso.
- Executavel empacotado: inicializacao validada por smoke test.

## Passos para seguir para a Fase 2

A Fase 2 ja foi iniciada pelo nucleo de dominio. Os proximos passos sao:

- Formularios reais de contas financeiras.
- Formularios de categorias/plano de contas e centros de custo.
- Formularios de receitas, despesas e transferencias.
- Contas a pagar/receber com vencimentos, status e alertas.
- Dashboard com saldo, receitas, despesas e resultado do periodo.
- Relatorio basico exportavel.
