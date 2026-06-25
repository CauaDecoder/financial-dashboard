# ADR-001 - Interface desktop

## Status

Aceita inicialmente.

## Contexto

O planejamento recomenda uma aplicação desktop local, instalável em Windows, com aparência de SaaS moderno e operação sem navegador ou servidor remoto.

## Decisão

Usar PySide6 como tecnologia principal da interface desktop.

## Consequências

- Permite interface profissional com componentes Qt.
- Mantém o projeto em Python, alinhado ao ecossistema existente.
- Exige validação de empacotamento com PyInstaller ainda na Fase 1.
- Se o empacotamento se tornar impeditivo, CustomTkinter fica documentado como fallback.
