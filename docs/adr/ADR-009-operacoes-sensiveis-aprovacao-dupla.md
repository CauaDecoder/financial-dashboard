# ADR-009 - Operacoes sensiveis com aprovacao dupla

## Status

Aceita.

## Contexto

A Fase 8 preve operacoes de escrita no Asaas em uma etapa futura. Essas
operacoes podem criar, cancelar ou estornar cobrancas e, por isso, nao devem ser
executadas diretamente por uma unica acao de operador nem armazenar credenciais
ou chaves em payloads locais.

## Decisao

Criar uma camada local de solicitacoes de operacoes sensiveis antes de qualquer
chamada externa de escrita. A solicitacao registra tipo, titulo, valor opcional,
referencia externa e payload JSON sem segredos. O payload e validado
recursivamente para rejeitar campos com nomes como token, senha, segredo, chave
de API ou autorizacao.

Uma solicitacao nasce como `pending`. O solicitante nao pode aprovar a propria
operacao. A solicitacao so muda para `approved` depois de duas aprovacoes de
usuarios distintos. Qualquer rejeicao muda a solicitacao para `rejected` e
impede novas aprovacoes. Cancelamentos continuam locais e auditados.

Neste incremento, nenhuma chamada de escrita ao Asaas foi implementada. O estado
`approved` significa apenas que a operacao esta autorizada para uma etapa futura
de execucao, que ainda devera exigir adapter isolado, idempotencia e novos
testes com mock.

## Consequencias

- A escrita externa continua desabilitada por padrao.
- O fluxo de aprovacao dupla pode ser testado sem internet e sem chaves reais.
- Solicitacoes, aprovacoes, rejeicoes e cancelamentos ficam registradas na
  auditoria local.
- Payloads de operacoes nao podem carregar credenciais acidentalmente.
- A futura execucao contra o Asaas tera uma fronteira clara: so consumir
  solicitacoes ja aprovadas e ainda nao executadas.
- A UI de aprovacao e a execucao idempotente ficam como proximos incrementos da
  Fase 8.
