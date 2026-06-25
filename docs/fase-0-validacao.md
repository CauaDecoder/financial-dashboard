# Fase 0 - Descoberta e validacao

Este projeto começou com a especificação técnica recebida em
`D:\Downloads\PLANEJAMENTO_FINANCEIRO_BASILICA.md`.

## Premissas ainda pendentes

- Quantidade real de usuários simultâneos e computadores.
- Regime financeiro padrão: caixa ou competência.
- Plano de contas e centros de custo oficiais.
- Planilhas históricas que serão importadas na Fase 3.
- Fonte oficial para vendas do PDV e regra contra dupla contagem.
- Destino de backup externo.
- Relatórios prioritários para a equipe administrativa.

## Decisões iniciais

- Aplicação desktop local e offline-first.
- Python como linguagem principal.
- PySide6 como interface de referência.
- SQLite local na Fase 1, preparado para endurecimento com criptografia e migrações formais.
- Nenhum segredo versionado; `.env` local obrigatório para credenciais e chaves.

## Próximo passo da Fase 0

Validar as perguntas pendentes com a equipe da Basílica e transformar as respostas em ADRs antes de estabilizar a Fase 2.
