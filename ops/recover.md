# Procedimento de Recuperação de Desastre (Fora do Pi)

## 1. Premissas
- O Pi físico é considerado descartável ou perdido.
- Nenhum segredo ou credencial privada reside no repositório de código público.
- A reconstrução utiliza apenas:
  1. Repositório versionado (Git).
  2. Réplica durável externa no VPS (`/srv/hermes-records/`).
  3. Gestor de segredos sob custódia humana do operador.

## 2. Linha do Tempo de Recuperação (SLO 4h)
- **0–15 min**: Declarar incidente, validar DNS doméstico via rota estática, extrair inventário do VPS.
- **15–60 min**: Provisionar SO base limpo (Linux ARM64/x86_64 compatível), Docker e OpenSSH.
- **60–120 min**: Restaurar UIDs de controle (`hermes-control`, `hermes-publish`, `hermes-author` UID 65532), instalar unidades systemd e sshd isolado.
- **120–180 min**: Restaurar volumes e snapshots declarados a partir da réplica de backup consistente.
- **180–240 min**: Executar probes de aceitação (`acceptance.py namespace`, `smoke_gate.py`) e liberar fila em Nível 0 (apenas propostas).
