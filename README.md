# HERMES — Fase 2: Entrega Ordinária e Verificável

## 1. Arquitetura Mínima
- O motor Somnus (hipóteses, consolidação, reflexão e auto-adjudicação) foi completamente removido do caminho de produção.
- Um timer do systemd (`hermes-task.timer`) busca jobs previamente autorizados pelo operador humano em `/srv/hermes/jobs/`.
- Sem trabalho autorizado, nenhum modelo é chamado (`NO_WORK`).
- Uma tarefa por vez; a fila e as decisões residem em registros privados versionados.

## 2. Contenção e Identidades
- **Supervisor (`hermes-control`)**: Executa o harness Hermes oficial fora de contêiner, sem privilégios de root nem grupo docker.
- **Executor (`hermes-author`, UID 65532)**: Executa dentro de contêiner descartável (`--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, memória 1 GiB, CPUs 1, PIDs 128). Montagem gravável restrita a `/work` e `/tmp` (tmpfs 128M).
- **Acesso Obrigatório**: O controlador conecta ao executor via SSH local (`127.0.0.1:2222`) com chave restrita e comando forçado (`hermes-enter.sh`).
- **Verificador (`hermes-verify`, UID 65532)**: Executa em contêiner independente, sem rede e sem credenciais, acionado por `smoke_gate.py`.
- **Publicador (`hermes-publish`)**: Lê recibos independentes (`pass.json`) fora do alcance do executor e interage com o GitHub via GitHub App.

## 3. Comandos Principais
- `make test`: Executa os testes do smoke gate determinístico (`tests/test_smoke.py`).
- `make count-lines`: Confere o teto de código próprio (máx. 800 linhas em `bin/` e `ops/`).
- `bin/smoke_gate.py`: Verifica se o worktree está limpo e se todos os checks passaram antes de emitir recibo PASS.
- `bin/acceptance.py`: Validação de ambiente (`namespace`, `budget`, `canary`).
