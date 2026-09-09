# Verificação executada

[EVIDENCE] Resultados desta entrega, executados no ambiente local de trabalho. Não representam implantação no Pi. `validation-results.json` contém os comandos e saídas completas, somente com canários sintéticos.

| Grupo | Resultado observado | Limite |
|---|---|---|
| [EVIDENCE] Smoke gate novo | [EVIDENCE] 12 testes passaram; exit 0 | [INFERENCE] Certifica o programa local e os cenários testados; não certifica Docker, política de publicação ou recuperação. |
| [EVIDENCE] Snapshot Somnus fornecido | [EVIDENCE] 7 falhas esperadas, 1 integração BLOCKED; exit 1 | [INFERENCE] Interações externas são fixtures instrumentadas; os testes observam bytes, chamadas, persistência e stage, sem provedores reais. |
| [EVIDENCE] Namespace/SSH | [EVIDENCE] BLOCKED, exit 3 | [EVIDENCE] Docker ausente neste ambiente; o teste não declarou PASS. |

[EVIDENCE] Python padrão e Git foram utilizados. Nenhuma dependência foi instalada; nenhuma chave real foi lida e nenhuma chamada paga de modelo foi feita.

[JUDGMENT] Pendências de ativação: isolamento com chave real restrita; sincronização e erro de credencial-canário pelo harness; limite do provedor pelo caminho real; rejeição de publicação e comparação remota; inversão de efeitos e recuperação cronometradas. Esses ensaios estão escritos em TESTS.md e na especificação. Não converter BLOCKED em sucesso para implantar.

[EVIDENCE] A primeira seção de arquitetura tem 302 palavras antes da árvore. A especificação contém os 15 itens pedidos.
