# HERMES — Fase 2: retirar o motor, conservar a capacidade de entregar

## 1. A arquitetura mínima

[JUDGMENT] Somnus sai do caminho de produção. Um timer do systemd procura uma tarefa já autorizada, chama uma instalação fixa do Hermes e termina. Sem tarefa, não chama modelo. Uma tarefa por vez; a fila e as decisões ficam em registros privados versionados, com cópia fora do Pi antes de serem consideradas aceitas. O limite inicial de atenção continua sendo 15 minutos/dia como hipótese, não como resultado.

[JUDGMENT] O processo do Hermes usa `hermes-control`, sem Docker, sudo ou credencial GitHub. Seu único instrumento de execução é o terminal SSH. A chave SSH tem comando obrigatório, instalado por root: entrar no contêiner `hermes-author`. O executor, UID 65532, recebe somente uma cópia limpa do código e um contrato. Não recebe histórico Git, configuração do operador, segredos, socket Docker, rede, montagens de serviços ou autoridade de publicação. A chave de modelo fica no processo de controle, fora de arquivos sincronizados e fora do ambiente do executor.

[JUDGMENT] Ao terminar, o serviço confiável encerra o executor, congela o artefato e o verifica em outro contêiner. O verificador não recebe credenciais. Um processo sob `hermes-publish` lê os resultados produzidos fora do executor, identifica os bytes e abre a PR. Merge automático fica restrito a classes explicitamente autorizadas, com checks obrigatórios, revisão dos donos para arquivos protegidos e impossibilidade de bypass pelo publicador. Infraestrutura, dados persistentes, dependências e autoridade permanecem sujeitos a decisão humana.

[JUDGMENT] O Pi contém trabalho descartável. Código, decisões aceitas, inventário, instruções de recuperação e recibos de entrega sobrevivem fora dele. Não há motor de hipóteses, migração de memória, banco de confiança, cinco serviços mitológicos ou novo framework. Uma instalação do harness, Docker, SSH, systemd, Git e scripts de finalidade fixa bastam. Essa escolha seria derrubada por uma tarefa rotineira comprovadamente impossível nesse perímetro e cuja execução ampliada ainda cumprisse reversibilidade e proteção dos segredos.

```text
hermes-somnus/                         # código público; nenhum registro privado
  README.md                           # esta arquitetura em uma página
  Makefile                            # comandos de instalação e recuperação
  ops/
    authority.json                    # classes, efeitos e caminhos protegidos
    images.lock                       # digests OCI e revisões do harness
    profile/config.yaml               # perfil sem credenciais sincronizáveis
    systemd/                          # timer e serviços de finalidade fixa
    ssh/                              # configuração do acesso obrigatório
    recover.md
  bin/
    run-one                           # sequência fixa; não um motor de agentes
    publish                           # nunca executa código do candidato
    hermes-enter.sh
    smoke_gate.py
  tests/

EDP-Helios/.hermes/                    # dados privados; autoridade separada
  decisions/                          # decisões humanas e expiração
  jobs/                               # contratos autorizados
  receipts/                           # referências de entrega sem segredos

VPS:/srv/hermes-records/               # réplica privada durável fora do Pi
  recovery/                           # inventário e exportações consistentes
  evidence/                           # recibos e artefatos ainda não publicados
```

[EVIDENCE] Os oito defeitos são entradas encerradas no novo pedido, §0, em [Texto colado.txt](sandbox:/workspace/scratch/e5b90d76a51e/upload/Texto-colado.txt). As referências **B** abaixo apontam ao [bundle fornecido](sandbox:/workspace/scratch/e5b90d76a51e/upload/02-hermes-bundle.txt), usando nome do arquivo e símbolo; **I** aponta ao [inventário fornecido](sandbox:/workspace/scratch/e5b90d76a51e/upload/01-hermes-inventory-2026-09-09.txt). As medições desta entrega estão em `VALIDATION.md`. [INFERENCE] A instrução anterior “PHASE 1 is DEMOLITION ONLY” cede a “THE DEMOLITION PROHIBITION IS LIFTED”: o pedido novo autoriza explicitamente este desenho.

[JUDGMENT] A árvore é a estrutura de destino. O pacote entregue implementa o smoke gate, a entrada SSH e testes; `run-one`, `publish`, a instalação e o restauro do host permanecem trabalho especificado, não software declarado instalado. Nenhuma configuração do Pi ou do GitHub foi alterada nesta entrega. A condição que derrubaria essa separação entre especificação e implementação seria a existência de resultados de implantação produzidos por esses serviços reais.

### C1 — O que sai e o que fica

| Componente atual | Presença no destino | Compensação que tentava fornecer | Veredito e critério de revisão |
|---|---|---|---|
| [EVIDENCE] Somnus: `daemon`, `ideate`, `consolidate`, `reflect`, Runtime e adjudicação automática (B) | [JUDGMENT] Ausente | [INFERENCE] Fazer o agente produzir a própria próxima tarefa e certificar melhoria | [JUDGMENT] **DELETE**. Uma melhoria útil entregue por esse motor, com benefício líquido medido, reabriria a decisão; testes com Runtime fictício não a reabrem. |
| [EVIDENCE] MemoryRouter, três bancos e ledger de realocação (B, `memory_router.py`) | [JUDGMENT] Ausente | [INFERENCE] Contornar retenção no banco global | [JUDGMENT] **DELETE**. Só volta a existir um problema de realocação se uma fonte não reproduzível exigir mudança de domínio com preservação demonstrável. |
| [EVIDENCE] Hindsight e sua infraestrutura compartilhada (I) | [JUDGMENT] Fora do caminho do Hermes; infraestrutura preservada enquanto houver outros consumidores | [INFERENCE] Recuperação de fatos fora do contexto corrente | [JUDGMENT] **SHRINK**. A ablação da seção 11 decide o uso pelo Hermes; não autoriza remover o serviço de outros usuários. |
| [EVIDENCE] Hooks, marcadores de sonho e hash de identidade (B, `hooks.py`, `state.py`) | [JUDGMENT] Ausentes como mecanismos de autoridade | [INFERENCE] Autorrestrição do mesmo usuário | [JUDGMENT] **REPLACE-WITH-STOCK-TOOL**: UID, SSH obrigatório e namespace. Um teste de escape bem-sucedido bloqueia a substituição. |
| [EVIDENCE] Snapshots locais e restauração parcial (B, `state.py`) | [JUDGMENT] Ausentes do executor | [INFERENCE] Recuperar depois de permitir efeitos amplos | [JUDGMENT] **DELETE**. Uma tarefa autorizada com efeito persistente fora do código exigiria rever o perímetro, antes de executá-la. |
| [EVIDENCE] Scripts precheck/smoke/gated e wrappers de cron (B, `scripts/`) | [JUDGMENT] Um gate e um timer | [INFERENCE] Economizar verificações e dar execução periódica | [JUDGMENT] **SHRINK**. A perda comprovada de uma obrigação periódica justificaria uma entrada declarada, não outro scheduler. |
| [EVIDENCE] SQLite de Somnus e JSONL de atividade (B) | [JUDGMENT] Exportação histórica; nenhum escritor novo | [INFERENCE] Persistir andamento do motor | [JUDGMENT] **DELETE** do funcionamento. Uma consulta operacional cuja resposta exista somente nesses dados exige exportá-la antes. |
| [EVIDENCE] Harness de programação, Git e CI existentes (§4 e fase 1) | [JUDGMENT] Presentes | [INFERENCE] Produção e verificação de alterações | [JUDGMENT] **KEEP**, fixando revisão, artefato e autoridade. Falha do teste real de entrega impede ativação. |
| [EVIDENCE] Pantheon e instruções de múltiplos papéis (§4; fase 1) | [JUDGMENT] Um executor; funções técnicas com UIDs quando precisam de autoridade distinta | [INFERENCE] Organização de raciocínio e revisão | [JUDGMENT] **DELETE** os nomes como topologia. Só um contrato executado sob autoridade realmente distinta justificaria um serviço separado. |
| [EVIDENCE] `code_audit.py` (B) | [JUDGMENT] Ferramenta manual opcional | [INFERENCE] Encontrar padrões suspeitos | [JUDGMENT] **KEEP** apenas como busca auxiliar; nunca como prova de ausência de segredos. Um mês sem resultado acionável justifica removê-la. |

### C2 — O que falta no sistema atual

| Adição concreta | Defeito ou obrigação atendida | Prova exigida |
|---|---|---|
| [JUDGMENT] Acesso SSH obrigatório a um executor sem rede e sem montagens privilegiadas | [INFERENCE] O hook não limita autoridade | [JUDGMENT] A mesma tentativa maliciosa falha pelo kernel; `/work` continua utilizável. |
| [JUDGMENT] Publicador separado e proteção de branches | [INFERENCE] Texto de revisão não impede push/merge | [JUDGMENT] Push direto e merge sem check são negados pelo GitHub; candidato rejeitado não altera refs remotas. |
| [JUDGMENT] Contrato ligado a base, artefato congelado e plano de verificação | [INFERENCE] Campos livres não identificam aquilo que foi testado | [JUDGMENT] Trocar um byte depois do teste invalida a entrega; mudar a base força nova integração. |
| [JUDGMENT] Prova de efeitos e contraprova antes de agendar | [INFERENCE] O desenvolvimento aceitou o próprio relatório como verificação | [JUDGMENT] Uma regressão conhecida faz o teste ficar vermelho, e o candidato correto o torna verde. |
| [JUDGMENT] Inventário privado fora do Pi e um ensaio de recuperação | [INFERENCE] Repositório de código não contém volumes, acessos e estado remoto | [JUDGMENT] Outra pessoa reconstrói sem consultar o Pi ou o criador. |
| [JUDGMENT] Registro diário de minutos e saldo real por provedor | [INFERENCE] Não existe denominador para o benefício alegado | [JUDGMENT] Uma semana tem sete registros ou lacunas explícitas; custos conciliam com cobrança. |

## 2. A mudança de maior valor está no desenvolvimento

[INFERENCE] A falha foi um circuito de confirmação: a mesma sessão propôs uma propriedade, escreveu uma implementação que parecia fornecê-la, escreveu testes que aceitavam os sinais dessa implementação e transformou os sinais em um relatório de implantação. A documentação consolidou certeza antes de existir uma observação independente do efeito. Isso explica conjuntamente o “rollback OK”, a preservação por document ID, o orçamento sem cobertura dos chamadores e a existência presumida do Runtime. É uma inferência sobre o processo; não demonstra quem escreveu cada linha.

[JUDGMENT] **Prioridade 1: uma contraprova obrigatória para cada promessa de efeito ou autoridade.** Antes do código, escrever uma frase: “o observador X, fora da autoridade do executor, verá Y depois de provocar Z”. O teste precisa falhar no defeito conhecido e passar na correção ou na retirada da capacidade. Autor e revisor podem usar o mesmo modelo; não podem usar a mesma afirmação como implementação e oráculo. A observação que derrubaria essa prioridade seria descobrir que testes assim já existiam e a entrega os ignorou deliberadamente; nesse caso a prioridade passa a ser impedir bypass da entrega.

[JUDGMENT] A menor alteração operacional é acrescentar à PR três referências: contraprova vermelha, prova verde e efeito observado na revisão exata candidata. Os checks do servidor e o publicador exigem a execução desses testes quando mudam autoridade, persistência ou publicação. Para uma correção textual de baixo impacto, isso não exige uma nova suíte: preserva-se o teste de escopo. O relatório pode dizer “implementado”, “exercitado localmente” ou “implantado”; só o último exige identificação do host/contêiner real, horário e artefato produzido. Falta de ambiente não autoriza trocar a palavra por “verificado”.

[JUDGMENT] Isso impediria sete defeitos de atravessar o gate por testes de efeitos. O oitavo seria barrado pela exigência de uma entrega real do harness instalado, sem Runtime fictício. Não acrescentaria um conselho de agentes, uma revisão literária obrigatória ou uma plataforma de observabilidade. O custo proposto é 5–15 minutos adicionais em mudanças na autoridade; a observação que derrubaria esse investimento seria um mês em que esse gate consumisse mais tempo do que as falhas e retrabalho que evita, sem capturar uma única divergência relevante.

## 3. Somnus: KILL

[JUDGMENT] **KILL.** Não há justificativa para construir o adaptador, preencher fixtures e consertar a estatística de um motor cuja utilidade ainda não foi demonstrada. Desligar apenas `enabled` conserva caminhos de escrita independentes; a retirada precisa alcançar registro de plugin, hooks e todos os jobs que invocam os scripts de memória. A observação que reabriria a decisão é uma série de tarefas reais mostrando benefício líquido de escolher melhorias automaticamente, além do que uma fila explícita com o mesmo harness entrega.

[EVIDENCE] No material extraído, `somnus/*.py` soma 3.307 linhas físicas, contando linhas em branco; `scripts/*.sh` soma 540 e `scripts/*.py`, 141. Essas são contagens do snapshot, não métricas de qualidade. [JUDGMENT] Retirar o pacote de execução e seus wrappers elimina até 3.988 linhas físicas antes do eventual aproveitamento de ferramentas de leitura. Não transportar `bench.py`, Store, hipóteses e relatos para outro diretório com um novo nome.

[JUDGMENT] Vale aproveitar exemplos dos defeitos como testes de aceitação; a parte de inspeção de AST de `code_audit.py`, se ainda usada; e a intenção do smoke, reimplementada no gate entregue. O histórico de decisões úteis precisa ser exportado antes de arquivar os bancos. Tar de banco aberto e “backup gerado” não bastam: usar a API `sqlite3.Connection.backup()` da biblioteca padrão, preservar o esquema, abrir a cópia e ler registros conhecidos. Não é necessário instalar o cliente `sqlite3` no host. Uma exportação que não contenha uma decisão útil conhecida derruba a remoção daquele arquivo, não o veredito sobre o motor.

## 4. Contenção e autoridade

[JUDGMENT] **O executor não pode modificar, substituir, personificar nem publicar a autoridade, o verificador ou a evidência que autoriza seus próprios efeitos.** O código do candidato pode ser hostil; o kernel, o SSH, a instalação do harness, o verificador instalado e o serviço de publicação constituem a base confiável. Um hash ajuda a identificar uma versão; o UID e o namespace impedem a alteração.

[JUDGMENT] Use três identidades: `hermes-control` para o harness; UID 65532 somente dentro do contêiner para código gerado; `hermes-publish` para a entrega. O root instala unidades, política e comandos. Nem `hermes-control` nem o executor pertencem a `docker` ou têm sudo. O serviço root cria o contêiner com nome fixo, `--read-only`, `--network none`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit 128`, `--cpus 1`, memória inicial de 1 GiB e somente `/work` gravável mais `/tmp` limitado. Autor e verificador não ficam ativos juntos. Um build que precise mais memória é BLOCKED; não recebe privilégio adicional por retry. Esses limites iniciais mudam se um build legítimo e medido for bloqueado apesar de haver folga térmica e de memória para os demais serviços.

[JUDGMENT] O supervisor faz a admissão antes de chamar modelo: tarefa autorizada, nenhum job ativo, sensor térmico válido abaixo de 70 °C, `MemAvailable` de pelo menos 1,5 GiB e 15 GiB livres como margens iniciais. Ausência de sensor é BLOCKED, não zero graus. Adiar compute pesado quando faltar margem; uma linha no próximo digest basta. Retirar “usuário ocioso por 90 minutos”: isso não mede autorização nem atenção. A observação que muda essas margens é um ensaio de carga mostrar folga estável para DNS e serviços compartilhados com limites menos conservadores. Nenhum ensaio desliga a proteção térmica do hardware.

[JUDGMENT] A entrada SSH é `hermes-enter.sh`, entregue no pacote. A chave do controlador é autorizada com `restrict`, comando obrigatório e origem apenas local; nenhuma sessão shell do host, encaminhamento, TTY, agent forwarding ou substituição de comando. Preferir uma instância de `sshd` escutando somente em `127.0.0.1`, com sua configuração e lista de chaves sob `/etc/hermes/ssh/`; não alterar às cegas o SSH administrativo existente. Um processo root inicia essa instância, mas a chave só pode executar o wrapper fixo. O executor jamais recebe a chave. Isso usa **b/d/e**, sustentados pela instalação **a**. A presença da palavra `somnus-sandbox.sh` no comando não altera o local de execução. [INFERENCE] O comando obrigatório e as restrições de chave são recursos do [OpenSSH](https://man.openbsd.org/sshd.8).

[INFERENCE] A documentação atual do Hermes descreve tanto o backend SSH quanto sincronização de estado para ambientes remotos; portanto trocar `backend` não prova que credenciais ficaram fora do executor. [Configuração do Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/configuration). [JUDGMENT] O perfil novo nasce vazio de credenciais em arquivos sincronizáveis: sem `.env`, auth/OAuth, skills dinâmicas, `credential_files`, passthrough, MCP ou plugins. A chave do modelo vem de credencial protegida entregue ao processo de controle, nunca do diretório sincronizado. O servidor SSH não aceita variáveis fornecidas pelo cliente. `--toolsets terminal` é a superfície pretendida; a ativação exige observar o registro real de ferramentas da versão fixada e o teste com canário. Se a versão ainda copiar uma credencial ou permitir execução local por outra ferramenta, ela não entra em produção. Não corrigir isso com uma regex.

| Arquivo ou autoridade viva | Dono/local e imposição | Observação que vale como prova |
|---|---|---|
| [JUDGMENT] `/etc/hermes/authority.json` | [JUDGMENT] root; diretórios não graváveis pelos UIDs do agente; não montado no executor (**a/b**) | [JUDGMENT] Tentativa de criar, substituir por symlink e renomear o pai é negada; bytes lidos pelo operador ficam iguais. |
| [JUDGMENT] `/usr/local/libexec/hermes-enter.sh`, `run-one`, `publish`, `smoke_gate.py` | [JUDGMENT] Instalação root; não executar a versão existente na PR (**a/b**) | [JUDGMENT] Editar o homônimo no candidato não muda o executável carregado; inode/caminho e revisão instalada são obtidos fora do candidato. |
| [JUDGMENT] `/etc/hermes/profile/config.yaml`, prompts de autoridade, `/opt/hermes/<revision>/` | [JUDGMENT] root; perfil sem ferramentas de manutenção; sem auto-update (**a/b/e**) | [JUDGMENT] Agente não consegue alterar backend, carregar plugin ou substituir o harness; sessão seguinte conserva a configuração instalada. |
| [JUDGMENT] `/etc/hermes/ssh/sshd_config`, `authorized_keys`, host key e chave privada do cliente | [JUDGMENT] root; leitura da chave cliente só por `hermes-control`; nenhum caminho sincronizado (**a/b/d**) | [JUDGMENT] SSH da chave restrita só produz efeitos em `/work`; encaminhamento e leitura da chave no executor falham. |
| [JUDGMENT] `/etc/systemd/system/hermes-*`, configuração de limites e timer | [JUDGMENT] root; nenhum D-Bus/socket administrativo no executor (**a/b/e**) | [JUDGMENT] Pedir outro timer, imagem ou montagem não cria unidade nem contêiner. |
| [JUDGMENT] `/srv/hermes/receipts/`, plano de testes e fixtures de aceitação | [JUDGMENT] Supervisor/verificador; executor sem montagem; candidato testado em outro contêiner (**a/b**) | [JUDGMENT] Recibo falso em `/work` é ignorado; alterar fixture do candidato não muda a suíte instalada. |
| [JUDGMENT] Credencial de modelo | [JUDGMENT] `hermes-control`; teto no provedor; nunca no executor (**a/b/d/e**) | [JUDGMENT] Chave-canário não aparece em contexto/log/cópia remota; chave esgotada é negada pelo provedor. |
| [JUDGMENT] Credencial GitHub de publicação | [JUDGMENT] Apenas `hermes-publish`; identidade de aplicação, sem administração/bypass (**a/d**) | [JUDGMENT] Executor não lê a chave nem modifica refs; publicador também não pode desligar proteção. |
| [JUDGMENT] `AGENTS.md`, `CLAUDE.md`, `.agents/skills/**`, `.claude/skills/**`, `.hermes/prompts/**`, `.hermes/plans/**`, `.hermes/jobs/**`, `.hermes/decisions/**`, `.hermes/receipts/**` | [JUDGMENT] Mudanças só por fluxo de autoridade; cópia candidata pode ser editada, mas não instalada nem publicada automaticamente (**c/d**) | [JUDGMENT] PR que toca qualquer caminho exige decisão humana ligada ao SHA; escrita local não altera a autoridade viva. |
| [JUDGMENT] `.github/CODEOWNERS`, `.github/workflows/**`, `.github/scripts/**`, manifests/locks de dependências, Dockerfiles, Compose, migrations e scripts de instalação | [JUDGMENT] Caminhos permanentemente fora de entrega ordinária; CODEOWNERS e verificação fora do candidato (**a/c/d**) | [JUDGMENT] Tentativa de desativar CI, mudar `delivery-sync.js`, acrescentar pacote ou ampliar volumes não é entregue sem gate humano. |
| [JUDGMENT] `main` de Somnus; `develop` e `main` de Helios | [JUDGMENT] Proteção do servidor: PR obrigatório, checks exatos, branch atualizada, sem force push/deletion/bypass; donos para arquivos protegidos (**c**) | [JUDGMENT] Solicitação real de push/merge proibido é rejeitada. Arquivo CODEOWNERS sozinho não satisfaz o teste. |

[EVIDENCE] O pedido estabelece que as proteções estão atualmente desligadas. [INFERENCE] Repositório privado pessoal pode precisar de GitHub Pro para protected branches e code owners; não tornar Helios público para obter a função. [Planos oficiais](https://docs.github.com/get-started/learning-about-github/githubs-products). [JUDGMENT] Esse custo de assinatura fica explicitamente pendente de preço e elegibilidade da conta; sem **c** exercitado, **d** continua permitindo apenas PRs e o merge automático permanece desligado. A observação que libera essa restrição é a negativa real do servidor ao teste de bypass.

[JUDGMENT] O publicador usa identidade de GitHub App instalada somente nos dois repositórios, token de instalação curto, permissões Contents/Pull requests necessárias e leitura dos checks, sem Administration, Actions write ou bypass. O instalador/emissor usa ferramentas existentes; a chave privada de assinatura fica fora do controlador. Se implementar essa emissão exceder o orçamento de simplicidade, manter a publicação manual: não entregar a credencial pessoal ao executor. A identidade distinta permite que o operador revise PRs de autoridade sem tentar aprovar a própria PR.

## 5. Rollback é definido por efeitos

[JUDGMENT] A unidade é uma operação autorizada com identificador, pré-condições, efeito permitido, recursos atingidos, reversão e teste externo de restauração. “A pasta voltou” não é o teste. Para trabalho ordinário, a unidade permite somente uma proposta de código e, depois de verificada, uma PR/merge em `develop`; não implica deploy, comando de produção, alteração de dados, envio de mensagem ou instalação de pacote.

| Efeito | Autonomia inicial | Reversão e observação externa |
|---|---|---|
| [JUDGMENT] Arquivos e processos do candidato | [JUDGMENT] Permitidos dentro de `/work` | [JUDGMENT] Encerrar o contêiner, remover integralmente o diretório privado da tarefa e recriar da base. Conferir conjunto de caminhos, conteúdo e modos; arquivo novo também desaparece. |
| [JUDGMENT] PR e merge de código, sem deploy | [JUDGMENT] Conforme classe de confiança | [JUDGMENT] Fechar PR ou produzir commit inverso pelo publicador sobre a base corrente. Verificar comportamento e refs remotas. Comentários/notificações já vistos permanecem efeitos históricos irreversíveis. |
| [JUDGMENT] Imagem somente baixada | [JUDGMENT] Instalador humano, não executor | [JUDGMENT] Remover a referência nova apenas se não usada; conferir imagens e espaço. Não confundir cache com alteração do serviço ativo. |
| [JUDGMENT] Pacotes do host | [JUDGMENT] Permanentemente humanos | [JUDGMENT] Reinstalação da versão anterior pode não desfazer scripts de manutenção, arquivos e formatos migrados. Exige plano específico ou reconstrução; não prometer cinco minutos. |
| [JUDGMENT] Serviços, scheduler, permissões, usuários e montagens | [JUDGMENT] Permanentemente humanos | [JUDGMENT] Reaplicar a configuração anterior, recarregar o serviço e comparar estado efetivo: UID/grupos/modos, unidades ativas e timers, processo e porta. É operação de infraestrutura, não um `git revert` do código. |
| [JUDGMENT] Escrita/invalidação em Hindsight | [JUDGMENT] Capacidade ausente | [JUDGMENT] Não há invalidação nova a compensar. Restaurar perdas anteriores requer exportação que contenha os registros originais; caso contrário é irrecuperável. |
| [JUDGMENT] Escrita em SAP/Databricks, migração, e-mail, webhook mutável, DNS, segredo emitido | [JUDGMENT] Capacidade ausente do executor; decisão específica do operador | [JUDGMENT] A reversão depende do sistema remoto; revelar segredo e enviar informação não têm inversa. O plano não as disfarça de operações revertíveis. |

[INFERENCE] O invariante literal “Any autonomous change is revertible ... including ... anything that left the machine” é incompatível com chamada paga de modelo e informação já transmitida em uma PR. A arquitetura não desfaz atenção consumida por destinatários nem cobrança liquidada. [JUDGMENT] A versão operacional é: **restaurar o comportamento e o estado mutável controlado de toda mudança ordinária, preservando o histórico de auditoria, em menos de cinco minutos**; transmissão ao provedor e criação de PR ficam como efeitos explicitamente autorizados e não reversíveis. Essa é uma limitação da especificação original, não uma garantia que o desenho já obteve. Se você exigir reversão literal também desses efeitos, publicação e uso de modelo remoto terão de permanecer humanos.

[JUDGMENT] O comando de destino é `sudo /usr/local/libexec/hermes-rollback OPERATION_ID`. Ainda não existe neste pacote; seria incorreto apresentá-lo como exercitado. Sua implementação ordinária faz: parar a fila; ler recibo de fonte independente; verificar que a inversa é aplicável sobre a base atual; criar PR inversa sem force push; executar a verificação relevante; obter merge sem ignorar proteções; conferir o efeito e retomar. Conflito, dependente posterior ou CI indisponível produz BLOCKED e mantém a pausa. O identificador deve ser escolhido pelo operador a partir do recibo, não pelo candidato.

[JUDGMENT] Os cinco minutos só são ganhos após três ensaios consecutivos cronometrados, incluindo arquivo acrescentado, alteração de permissão em laboratório e uma entrega Git real de teste, com uma pessoa que não escreveu o script. O relógio começa na decisão de reverter e termina na observação externa correta; espera por CI conta. Se a espera sozinha exceder cinco minutos, essa classe não recebe autonomia de merge sob o invariante. Uma revisão do requisito pelo operador pode aceitar um SLO maior; um check não pode inventá-lo.

## 6. Estado, queda de energia e perda do Pi

[INFERENCE] Consistência após crash significa conseguir abrir um estado estruturalmente válido; durabilidade significa preservar o que já foi reconhecido; sobrevivência à perda do dispositivo significa poder obtê-lo sem aquele dispositivo. WAL não cria uma cópia externa. Em SQLite/WAL, `synchronous=NORMAL` não sincroniza cada commit como `FULL`; dados reconhecidos podem ser perdidos após queda de energia. Mesmo `fsync` não fornece energia ou prova sobre o controlador do SSD. [SQLite](https://www.sqlite.org/pragma.html#pragma_synchronous).

| Fatos/store | Consistência de crash | Durabilidade requerida | Perda total e autoridade |
|---|---|---|---|
| [JUDGMENT] Código e decisões já aceitas | [JUDGMENT] Objetos Git e checagem de integridade; clone quebrado é descartável | [JUDGMENT] Reconhecimento só após leitura externa do commit aceito | [JUDGMENT] GitHub mais réplica privada do VPS. Código privado e decisões não vão para o repositório público Somnus. |
| [JUDGMENT] Contrato autorizado e recibo de preparação de entrega | [JUDGMENT] Arquivo temporário, sync, rename e sync do diretório | [JUDGMENT] Escrita confirmada fora do Pi antes de o publicador agir | [JUDGMENT] Registro privado no VPS, versionado; executor sem acesso. Perder o Pi depois não perde a intenção autorizada. |
| [JUDGMENT] Resultado e objeto do merge | [JUDGMENT] API/Git do servidor e reconciliação por job, base e head | [JUDGMENT] Resposta perdida fica INCONCLUSIVE até consultar o servidor | [JUDGMENT] GitHub é autoridade sobre merge; recibo é evidência derivada. Nunca repetir um efeito externo só porque faltou resposta local. |
| [JUDGMENT] Candidato ainda não aceito | [JUDGMENT] Pode ser descartado após crash | [JUDGMENT] Não prometida a cada edição; considerado trabalho reproduzível | [JUDGMENT] Aceitação exige exportação imutável fora do Pi. Se contiver contribuição humana inédita, ela precisa ser persistida antes de entrar aqui. |
| [JUDGMENT] Fingerprint e PASS local | [JUDGMENT] Gravação atômica no gate entregue | [JUDGMENT] Não serve de autoridade depois de crash ou para outro ambiente | [JUDGMENT] Reexecutar; é cache descartável. O publicador requer um recibo externo da execução correspondente. |
| [JUDGMENT] `somnus.db`, ledger.db, JSONL antigos | [JUDGMENT] Exportação consistente com escritores parados ou API de backup; validar a cópia | [JUDGMENT] Arquivo histórico preservado uma vez, não novos commits de runtime | [JUDGMENT] Cópia externa e esquema. Sem valor identificado, arquivar por prazo curto e remover da operação. |
| [JUDGMENT] Hindsight/Postgres existentes | [JUDGMENT] Backup nativo consistente; validar restauração | [JUDGMENT] Outros consumidores podem exigir durabilidade; não a presumir pela configuração atual | [JUDGMENT] Até classificar conteúdo, tratar como potencialmente único e exportar. Hermes novo não cria dependência dessa base. |
| [JUDGMENT] Perfis/sessões do harness | [JUDGMENT] Perder sessão interrompe tarefa; retomar da fila, não confiar em narrativa de sessão | [JUDGMENT] Só decisões e artefatos aceitos têm obrigação de preservação | [JUDGMENT] Demais conversas são descartáveis. Fato único descoberto deve virar decisão/proveniência antes de ser aceito. |
| [JUDGMENT] Segredos, DNS, túneis e acesso à recuperação | [JUDGMENT] Armazenamento próprio do gestor de segredos e exportação de configuração | [JUDGMENT] Recuperabilidade testada, fora de Git/contexto/log | [JUDGMENT] Credenciais em gestor existente ou material cifrado sob custódia do operador; instruções sem valores no repositório. |

[JUDGMENT] Não há um único store honesto para “tudo que Hermes acredita”. O código responde pelo comportamento versionado; decisões aprovadas respondem pela autorização; GitHub responde por merge/review; o provedor responde pela cobrança; o host responde pelo estado em execução. Um arquivo que copie tudo isso não toma sua autoridade. Hoje, configuração local não declarada, segredos sem custódia externa conhecida e fatos de memória sem fonte podem não ter upstream. A observação que encerra essa lacuna é recuperar um exemplo conhecido de cada classe sem ler o Pi.

[JUDGMENT] Um writer por vez, `flock` do processo supervisor e diretório de arquivos bastam. Não criar banco novo para coordenação. O lock impede concorrência acidental; **a/b/d** impedem que o candidato altere o supervisor. Um hash válido de recibo não prova durabilidade: precisa de leitura e sync do lado do VPS. Uma sessão SSH que executa somente `cat` não prova que o disco remoto confirmou a gravação.

## 7. Verificação

[JUDGMENT] **PASS**: todos os riscos exigidos pelo contrato tiveram evidência válida na revisão e ambiente especificados. **FAIL**: uma obrigação foi violada em ambiente apto. **BLOCKED**: faltou uma pré-condição, ferramenta, autorização ou serviço. **INCONCLUSIVE**: a execução ocorreu, mas terminou sem evidência suficiente ou coerente — timeout, cancelamento, artefato trocado, resultado truncado. Flakiness descreve divergência entre repetições comparáveis; não substitui o estado da tentativa.

| Degrau | Riscos cobertos | Custo inicial estimado | Quando parar ou bloquear |
|---|---|---|---|
| [JUDGMENT] Identidade e efeitos permitidos | [JUDGMENT] Base errada, caminho protegido, dependência ou efeito externo não autorizado | [JUDGMENT] Segundos, zero modelo | [JUDGMENT] Qualquer expansão de efeito encerra a entrega ordinária. |
| [JUDGMENT] Parse, tipos, lint direcionado e diff | [JUDGMENT] Erros mecânicos e incompatibilidades detectáveis | [JUDGMENT] Segundos a poucos minutos, zero modelo | [JUDGMENT] Não cobre perda de dados ou regra de negócio sozinho. |
| [JUDGMENT] Teste da falha + testes afetados | [JUDGMENT] Consequência concreta da alteração | [JUDGMENT] 1–10 minutos de máquina como orçamento inicial | [JUDGMENT] Pré-condição indisponível é BLOCKED; bug demonstrado é FAIL. |
| [JUDGMENT] Build e integração na plataforma relevante | [JUDGMENT] Empacotamento, importação, contratos e diferenças de plataforma | [JUDGMENT] Até 15 minutos previstos; usar CI existente para Windows | [JUDGMENT] Linux/ARM não certifica comportamento exclusivo do job Windows de Helios. |
| [JUDGMENT] Restauração, invariantes de dados e exercício de autoridade | [JUDGMENT] Riscos com consequências persistentes ou de privilégio | [JUDGMENT] 5–30 minutos em laboratório | [JUDGMENT] Falta dessa evidência mantém essas classes humanas. |
| [JUDGMENT] Revisão por modelo ou decisão humana | [JUDGMENT] Incerteza sem oráculo mecânico suficiente | [JUDGMENT] Uma chamada delimitada ou 2–5 minutos do operador | [JUDGMENT] Não pode transformar teste ausente em aprovado; escolhe reduzir escopo, adiar ou assumir risco explicitamente. |

[JUDGMENT] Os tempos são limites de planejamento, não medições do Pi; a primeira execução correspondente os substitui. O stop rule é a cobertura das consequências listadas no contrato, não “chegamos ao quinto degrau”. Novos testes só entram para uma lacuna concreta ou gate exigido. Uma falha intermitente impede usar uma passagem fortuita como único comprovante; uma repetição diagnóstica é permitida e as duas tentativas permanecem visíveis. Se o teste é necessário e continua instável, o resultado agregado fica INCONCLUSIVE até haver evidência alternativa que cubra o mesmo risco.

[EVIDENCE] `smoke_gate.py` está escrito e passou nos testes locais do pacote. Ele recebe um plano protegido, aceita worktrees cujo `.git` é arquivo, exige HEAD e árvore limpa, identifica commit/tree/plano/gate, executa comandos com ambiente mínimo sem segredos herdados, descarta stdout/stderr bruto dos filhos e só grava PASS depois de todos os comandos passarem e a identidade continuar igual. Remove o recibo anterior no início de uma tentativa; BLOCKED nunca vira PASS na seguinte. Usa lock, arquivo temporário, `fsync`, rename e sync do diretório. Não reutiliza um PASS anterior para pular testes.

[JUDGMENT] O contrato de invocação instalado será:

```sh
python3 /usr/local/libexec/smoke_gate.py \
  --repo /srv/hermes/verify/repo \
  --plan /etc/hermes/checks/helios.json \
  --state /srv/hermes/receipts/current/pass.json
```

[JUDGMENT] O supervisor só chama o gate quando há candidato ou alteração de revisão relevante. Ausência de trabalho é `NO_WORK` na fila, não um resultado de verificação. O gate certifica **somente os comandos listados**: a escolha do plano, o digest real da imagem, a plataforma, a versão dos pacotes e a ausência de montagens/segredos são observados pelo supervisor fora do código candidato. O JSON local não é uma autorização de merge. Um script de teste substituído no próprio candidato não vale como suíte independente; o plano deve executar também os testes protegidos de comportamento/autoridade.

[JUDGMENT] `helios.plan.example.json` esclarece o ponto de execução: o gate fica no supervisor, mas seu comando inicia Docker; **não executar `pytest`, `npm` ou script candidato diretamente no host do supervisor**. O arquivo é um exemplo incompleto, com imagem explicitamente não preenchida. O instalador deve fornecer digest real e `/opt/hermes-checks/run-helios` dentro da imagem imutável, contendo os comandos já validados para a plataforma e sem instalação de pacotes durante a tarefa. O mesmo supervisor encerra o contêiner de verificação ao cancelar o job; timeout do processo cliente Docker sozinho não prova que o contêiner terminou. Não preencher a imagem com `latest` nem substituir o teste por `true` para satisfazer o exemplo.

[JUDGMENT] O benchmark desaparece com o motor. Para uma otimização ordinária, preservar correção é objetivo suficiente: uma alteração com o mesmo comportamento pode ser aceita se reduzir custo medido e não piorar riscos relevantes. Registrar antecipadamente tarefa, amostra, métrica e tolerância; comparar em pares com IDs únicos, conjuntos completos e guardas todos aprovados. Para código determinístico, igualdade do conjunto exigido mais redução repetível de custo pode bastar. Para comportamento probabilístico, “não observei diferença” não prova equivalência: seis tarefas podem apoiar um ensaio reversível, não uma alegação populacional. Não exigir melhora de acurácia para aceitar uma economia de tokens, nem reconstruir a adjudicação estatística do Somnus.

## 8. Confiança com seis entregas

[INFERENCE] O limite de 39,3% citado no pedido é `1 − 0,05^(1/6)`, para zero falhas em seis observações independentes com a mesma distribuição. Merge, autoria de token e ausência de revert não estabelecem essas premissas. [JUDGMENT] A confiança será atribuída à **classe de efeito**, não a um agente genericamente promovido a administrador. Os números abaixo são critérios de operação reversível, não certificados estatísticos. Um defeito de autoridade derruba a escada inteira; um defeito funcional demove a classe atingida.

| Nível | Efeito permitido | Promoção medida | Rebaixamento |
|---|---|---|---|
| [JUDGMENT] 0 — Produzir proposta | [JUDGMENT] Ler snapshot, executar testes locais e devolver artefato; sem credencial de entrega | [JUDGMENT] Três tarefas consecutivas da mesma classe com artefato identificado, verificação independente e escopo respeitado; operador cronometra a revisão | [JUDGMENT] Permanece aqui enquanto isolamento, entrega ou dados de resultado estiverem BLOCKED. |
| [JUDGMENT] 1 — Abrir PR | [JUDGMENT] Publicador pode criar branch e PR previamente autorizadas; não fazer merge | [JUDGMENT] Seis entregas da classe aceitas sem reescrita funcional, mediana de atenção ≤5 min/tarefa, nenhum efeito não declarado e reversão exercitada | [JUDGMENT] Uma divergência entre artefato proposto e entregue volta ao nível 0. |
| [JUDGMENT] 2 — Merge ordinário delimitado | [JUDGMENT] Somente classes enumeradas: inicialmente documentação de uso fora da constituição, depois transformações mecânicas já cobertas; uma alteração ativa por vez, sem deploy | [JUDGMENT] Não há promoção automática além disso. Ampliar a lista é mudança de autoridade humana, com seu próprio ensaio | [JUDGMENT] Uma regressão atribuível suspende merge daquela classe; três novas entregas corretas e a contraprova do defeito permitem reconsiderar. |

[JUDGMENT] Permanentemente sujeitos a decisão humana: modificar autoridade, testes obrigatórios ou CI; adicionar/atualizar dependências; alterar imagem ou scripts de instalação; host, DNS, túnel, credencial, segredo, produção, esquema/migração, fonte SAP/Databricks, regras de integridade e envio externo além da PR e do provedor autorizado. Uma década sem incidente não torna esses efeitos intrinsecamente reversíveis. A observação que faria rever a classificação de uma ação é um procedimento específico que reduza seu efeito ao perímetro ordinário e demonstre reversão dentro do limite; ela não libera a classe inteira.

[JUDGMENT] “Sem reescrita” é determinado comparando os bytes do candidato congelado com o que foi entregue, descontando somente a alteração mecânica de metadados de merge. Correção humana necessária entra no custo, mesmo que esteja no mesmo commit por squash. Enquanto esse dado não existir, os seis merges antigos não dão promoção. Não esperar 299 tarefas para permitir documentação reversível; tampouco usar seis para liberar integridade de dados.

## 9. Contrato de delegação e publicação

[JUDGMENT] Cada tarefa recebe um JSON de versão 1 com campos obrigatórios fechados: `job_id`, repositório exato, branch de destino, `base_commit`, hash do snapshot exportado, `authority_revision`, decisão que autorizou a classe, expiração, objetivo verificável, caminhos exatos permitidos, efeitos permitidos, plano de verificação e limite de tentativas. O contrato é criado pelo supervisor a partir de autorização humana já persistida; sugestões de contrato feitas pelo modelo não o autorizam. Um número de issue, uma label ou um texto “aprovado” escrito pelo executor não substitui a decisão. O publisher lê o contrato por `job_id` de seu próprio store, nunca o JSON fornecido em `/work`.

[JUDGMENT] Para evitar interpretação livre pelo próximo agente, implementar esta sequência em `run-one`/`publish`, nessa ordem:

1. [JUDGMENT] Obter a base do remoto permitido; confirmar decisão e revisão de autoridade fora do candidato. Criar o registro de intenção fora do Pi antes de reconhecer a tarefa. Nenhum input da issue escolhe comando do host, imagem, URL de API, caminho de segredo ou branch de destino.
2. [JUDGMENT] Exportar somente blobs atuais do repositório que foram aprovados para contexto. Não montar o repositório do operador nem sua base de objetos Git. Arquivos de credencial, `.env`, histórico contaminado, sockets, devices e links que escapem são recusados. A ausência de achado de scanner não certifica que qualquer texto contém zero segredos.
3. [JUDGMENT] Criar o contêiner fixo e iniciar o harness fixado com o contrato. Um único processo de autoria; nenhuma delegação recursiva. Rejeitar sem executar qualquer tentativa de usar ferramenta que amplie a superfície. A fronteira continua sendo a montagem/rede e a chave restrita, não a intenção do prompt.
4. [JUDGMENT] Encerrar todos os processos do contêiner e retirar seu acesso ao diretório antes de coletar o artefato. Enumerar os arquivos como objetos não confiáveis: rejeitar symlinks, devices, FIFOs, sockets, paths fora do contrato, `.git`, gitlinks/submodules e alterações de permissões não previstas. Não extrair um tar arbitrário do candidato como usuário privilegiado.
5. [JUDGMENT] Aplicar somente as mudanças de arquivos permitidas sobre uma cópia limpa da base em repositório pertencente ao supervisor. Desativar hooks, aliases, includes e filtros Git vindos do candidato. O supervisor cria o commit candidato e calcula o tree ID e SHA-256 de uma enumeração canônica de caminhos/modos/bytes; o hash enviado pelo autor serve apenas como alegação a comparar.
6. [JUDGMENT] Construir a integração exata com a base atual e executar o plano protegido em um novo contêiner, sem chave de modelo/GitHub/produção e sem rede. O processo externo escreve o recibo com job, base, commit/tree, digest real da imagem, revisão do plano, testes exigidos versus executados, resultados e horários. Uma lista vazia, IDs duplicados ou testes omitidos produz BLOCKED/FAIL, jamais evidência populacional.
7. [JUDGMENT] Persistir recibo e artefato aceito no VPS e confirmar sua leitura. Só então entregar ao publicador. O autor não pode escolher o caminho desse recibo nem escrevê-lo por compartilhamento de UID ou volume.
8. [JUDGMENT] Abrir PR pela identidade de aplicação. Mudança em arquivo protegido segue fluxo humano separado, sem ativação automática no host. Para a classe com merge permitido, consultar conclusão **success** dos checks esperados, fonte esperada e SHA exato, além das aprovações exigidas e da base atual.
9. [JUDGMENT] Fazer merge com pré-condição do head SHA e proteção estrita de branch atualizada. Mudança da base invalida a integração anterior; não confiar somente no parâmetro `sha` da API, que protege o head. Serializar as próprias entregas; confiar no servidor para rejeitar concorrência com outras atualizações. Conferir a árvore entregue após a resposta.
10. [JUDGMENT] Em timeout de publicação, consultar por job/branch/head antes de repetir. Candidato rejeitado conserva somente artefato diagnóstico sem segredo e motivo estruturado; não recebe token, branch de entrega ou autorização por retry. Uma revisão de candidato é outra identificação, com nova verificação; limitar inicialmente a duas tentativas automáticas por tarefa.

[INFERENCE] O GitHub aceita estados `skipped` e `neutral` em certas condições de required checks; por isso “a interface permite merge” não é equivalente a “nossos testes executaram e passaram”. O publicador exige `success` dos jobs esperados e o recibo independente, além da proteção do servidor. [Protected branches](https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches). [INFERENCE] A API de merge aceita uma pré-condição para o SHA do head; isso não identifica sozinha a integração testada. [API de pull requests](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request).

[JUDGMENT] Não é necessário reler integralmente toda alteração para conferir base, escopo, artefato, execução de testes, build e proibição de efeitos. Não existe substituto mecânico universal para decidir que código arbitrário é seguro. Por isso mudanças cujo risco semântico não tenha cobertura suficiente terminam em decisão humana, ainda que pequenas. Limite de linhas é controle de custo de revisão, não prova de segurança.

[JUDGMENT] **Pantheon: apagar como arquitetura.** Autor, verificador e publicador são funções com permissões diferentes; não cinco personagens com narrativas de independência. Um segundo modelo pode revisar uma alteração delimitada sob o mesmo contrato e sem entrega. Essa revisão é evidência probabilística adicional, não poder de veto por nome. A observação que justificaria conservar um dos cinco nomes como serviço seria uma interface real, autoridade exclusiva e uma obrigação mensurável que desaparecesse ao removê-lo.

## 10. Um digest de quinze minutos

[SPECULATIVE] **Exemplo inventado de 10/09, 19h30.** Os números de prioridade e a existência de sete `needs-decision` vêm do pedido; recomendações, atrasos, valores e detalhes operacionais abaixo são hipóteses ilustrativas. O dado que substitui este exemplo é o digest real das sete issues com suas alternativas e evidências atuais. Decidir adiar uma questão com dono e data tira a ambiguidade da fila; não fecha a issue nem resolve o problema de produto.

> [SPECULATIVE] **Hoje: 12 minutos de decisões, 2 de leitura e 1 de registro.** Nenhuma publicação altera produção. Os quatro P0/P1 continuam visíveis. Uma aprovação aqui vale somente para a opção e escopo descritos; silêncio significa adiar. Se alguma decisão exigir investigação adicional, usamos o minuto de registro para marcar quem investiga e até quando, sem estourar o orçamento escondido.

| Issue e tempo | Decisão proposta no exemplo | Custo de esperar mais 24h | Incerteza residual |
|---|---|---|---|
| [SPECULATIVE] #19, P0 — 3 min | [SPECULATIVE] Confirmar que alterar Nota Mãe requer confirmação explícita mostrando registro atual e proposto; aprovar implementação em fixture, sem escrita real | [SPECULATIVE] O fluxo afetado permanece bloqueado; estimativa de 20 min de trabalho manual | [SPECULATIVE] Falta confirmar uma exceção de uso; tratar a exceção como fora do escopo até resposta |
| [SPECULATIVE] #25, P1 — 3 min | [SPECULATIVE] Separar o contrato de estado recuperável da provisão de credenciais; autorizar apenas testes e implementação local sem conexão produtiva | [SPECULATIVE] Integração real permanece um dia atrasada, mas código pode avançar sem segredo | [SPECULATIVE] Não está demonstrado quem emite/renova a credencial nem como retomar operação interrompida |
| [SPECULATIVE] #37, P1 — 2 min | [SPECULATIVE] Definir um destinatário e escopo do relatório de remediação; permitir preparar o artefato, manter envio humano | [SPECULATIVE] A comunicação operacional atrasa um dia; sem bloquear correções independentes | [SPECULATIVE] O destinatário ainda pode pedir outro formato; nenhum envio é pressuposto |
| [SPECULATIVE] #74 — 1 min | [SPECULATIVE] Tornar o inventário de writers e volumes a condição para qualquer alteração de persistência | [SPECULATIVE] Nenhum custo adicional de implementação; evita trabalhar sobre armazenamento desconhecido | [SPECULATIVE] Um writer não inventariado pode existir; a investigação continua |
| [SPECULATIVE] #71 — 1 min | [SPECULATIVE] Adiar o cutover de containerização até backup/restauro exercitado; autorizar Compose apenas em laboratório | [SPECULATIVE] Um dia de atraso no cutover, sem interromper desenvolvimento local | [SPECULATIVE] O laboratório ainda não demonstrou equivalência da persistência |
| [SPECULATIVE] #73 — 1,5 min | [SPECULATIVE] Fixar somente campos e estados necessários ao dashboard; adiar refinamento visual e novas métricas | [SPECULATIVE] Evita retrabalho; parte visual espera a próxima sessão | [SPECULATIVE] Um consumidor pode precisar de campo ainda não listado; será mudança posterior de contrato |
| [SPECULATIVE] #27 — 0,5 min | [SPECULATIVE] Adiar paginação/timeline por sete dias; preservar acesso ao diagnóstico existente | [SPECULATIVE] Consulta operacional continua menos conveniente; nenhum risco P0/P1 resolvido por essa expansão | [SPECULATIVE] Se a consulta atual impedir investigar um incidente, a prioridade muda naquele dia |

> [SPECULATIVE] **#95, P0, fora das sete decisões:** a prova de ponta a ponta ainda não existe. Próxima ação autônoma: testar o caminho Plano → Carteira → Dashboard em fixture e devolver evidência; nenhum pedido de aprovação genérico hoje. Os demais itens urgentes estão nas três primeiras linhas. Não somar sete decisões e quatro prioridades como onze casos independentes.
>
> [SPECULATIVE] **Enquanto aguarda:** reproduzir falhas com dados sintéticos, completar inventário de leitura permitido, executar testes de contrato e preparar alterações independentes em snapshots distintos. Ao atingir limite de tentativas ou faltar trabalho autorizado, encerrar. Não escolher regra de negócio, provisionar segredo, escrever em produção ou inventar tarefas de autoaperfeiçoamento para manter atividade.

[JUDGMENT] O exemplo resolve o ato de decidir ou adiar dentro de quinze minutos; não demonstra que as sete questões reais cabem nesse tempo. Se dois dias da primeira semana excederem quinze minutos por decisões substantivas, reduzir trabalho em curso e tamanho dos lotes antes de criar uma interface nova. A observação que derruba esse limite inicial é o registro de atenção mostrar que ele impede decisões essenciais mesmo com uma única tarefa ativa.

## 11. Memória depois do router

| Classe | Mudança | Reobtida de repo/Git? | Consequência de erro | Leitor e destino |
|---|---|---|---|---|
| [JUDGMENT] Estrutura, símbolos, build e configuração versionada | [JUDGMENT] A cada commit | [JUDGMENT] Sim | [JUDGMENT] Pode induzir implementação incorreta | [JUDGMENT] Modelo: ler a revisão corrente; não reter uma segunda descrição autoritativa |
| [JUDGMENT] Política e escopo autorizado | [JUDGMENT] Raro, com validade explícita | [JUDGMENT] Sim, depois de aprovação versionada | [JUDGMENT] Perigoso | [JUDGMENT] Supervisor e auditoria: arquivo de decisão; modelo recebe cópia contextual sem poder alterá-la |
| [JUDGMENT] Motivo de decisão que não está no código | [JUDGMENT] Por decisão | [JUDGMENT] Não, até ser registrado | [JUDGMENT] Pode provocar retrabalho ou decisão errada | [JUDGMENT] Humano/modelo: nota curta, fonte, data, responsável, escopo e próxima revisão |
| [JUDGMENT] Resultado de uma execução | [JUDGMENT] A cada tarefa | [JUDGMENT] Pode ser reexecutado, mas o fato histórico não | [JUDGMENT] Perigoso se usado para autorizar entrega | [JUDGMENT] Auditoria: recibo externo ligado ao artefato; resultado antigo não certifica código novo |
| [JUDGMENT] Estado de incidente ou bloqueio | [JUDGMENT] Horas/dias | [JUDGMENT] Parte vem das issues e serviços | [JUDGMENT] Perigoso se confundido com autorização | [JUDGMENT] Humano: issue com fonte, dono e prazo; reler na execução |
| [JUDGMENT] Preferência de linguagem ou apresentação | [JUDGMENT] Raro | [JUDGMENT] Não originalmente | [JUDGMENT] Em geral ruído | [JUDGMENT] Modelo: pequeno arquivo estático escolhido pelo operador |
| [JUDGMENT] Credencial ou valor sensível operacional | [JUDGMENT] Por rotação/uso | [JUDGMENT] Nunca do Git | [JUDGMENT] Perigoso | [JUDGMENT] Somente processo autorizado/gestor de segredos; nunca memória semântica |
| [JUDGMENT] Resumo de conversa, hipótese ou “lição” sem fonte | [JUDGMENT] Muito frequente | [JUDGMENT] Geralmente descartável ou refazível | [JUDGMENT] Ruído, podendo poluir uma decisão | [JUDGMENT] Não persistir por padrão; promoção exige fonte e utilidade concreta |

[JUDGMENT] O router vira **zero código e zero chamadas**. Não há realocação nem invalidação entre bancos. Governança fica na decisão aprovada; conhecimento atual do repositório é lido; justificativas não reproduzíveis são registradas como notas. O provedor semântico pode ser desligado para o perfil Hermes antes de se decidir o destino da infraestrutura Hindsight compartilhada.

[JUDGMENT] Experimento mínimo: nas próximas seis tarefas reais elegíveis, executar uma sessão sem consulta semântica; em cópia do mesmo snapshot e contrato, executar uma alternativa com apenas o conteúdo de memória aprovado e congelado. Alternar qual condição vem primeiro, impedir que uma sessão veja a saída da outra, manter modelo e limite de trabalho iguais e entregar somente uma versão. Um revisor compara resultado verificável, minutos humanos, uso faturado e decisões erradas; seis pares não estimam uma taxa rara, mas podem decidir se vale manter uma dependência.

[JUDGMENT] Custo máximo do experimento: seis execuções adicionais, até US$5 de uso faturado e até 30 minutos adicionais de revisão no total; cortar o experimento ao atingir qualquer teto. São tetos propostos, não previsão de preço. Desligar o acesso semântico se não economizar ao menos 30 minutos humanos líquidos nas seis tarefas, ou se recuperar uma decisão obsoleta que cause risco. A observação que derruba essa decisão é a condição sem memória perder repetidamente uma informação necessária que não pode ser recuperada das fontes e cuja nota simples não resolva a falta. A comparação inclui manutenção do provedor; mais tokens recuperados não é sucesso.

## 12. Recuperação e o registro que falta

[JUDGMENT] Antes do ensaio devem existir fora do Pi: revisão exata do código de controle e dos dois repositórios; lista de imagens por digest e uma forma testada de obtê-las em ARM; imagem customizada Hindsight preservada se ainda necessária; decisões e recibos aceitos; inventário privado de serviços, volumes, proprietários, permissões, portas, DNS e túneis; backups consistentes de cada store com dado único; sequência de reconstrução; localização e acesso de recuperação às credenciais. O repositório contém o procedimento e nomes dos segredos, nunca seus valores. Não fazer cópia indiscriminada de histórico contendo credencial exposta; revogar primeiro e tratar o histórico contaminado fora do contexto do agente.

[JUDGMENT] Um estranho sem credenciais de acesso não consegue reconstruir contas e recursos privados a partir de um repositório sem segredos. A exigência literal “repository alone” conflita com o invariante de segredo e com indisponibilidade do operador por seis meses. O contrato viável é **repositório + material de recuperação sob custódia previamente delegada**. O custo dessa fronteira **d/e** é preparar essa custódia uma vez. Sem ela, a resposta ao teste do segundo operador continua sendo não; não preencher a lacuna com instrução para ligar ao criador.

| Relógio do ensaio | Procedimento e prova |
|---|---|
| [JUDGMENT] 0–15 min | [JUDGMENT] Declarar o Pi inacessível. Garantir DNS doméstico pela configuração previamente ensaiada. Obter inventário, acesso e revisões sem consultar o Pi. Cronometrar também dificuldades de login. |
| [JUDGMENT] 15–60 min | [JUDGMENT] Instalar base compatível em máquina limpa, confirmar arquitetura, armazenamento, hora, SSH e Docker. Não instalar a partir de “latest” sem revisão/digest registrado. |
| [JUDGMENT] 60–120 min | [JUDGMENT] Restaurar UIDs, arquivos protegidos e serviços de suporte; recuperar somente volumes declarados e confirmar registros/contagens conhecidos. Configurar DNS/túnel a partir do inventário, nunca de memória. |
| [JUDGMENT] 120–180 min | [JUDGMENT] Criar executor descartável, executar testes de contenção, orçamento e entrega real. Confirmar zero jobs de Somnus ressuscitados por restauração de perfil antigo. |
| [JUDGMENT] 180–240 min | [JUDGMENT] Recuperar uma decisão aceita, um recibo de merge e um dado único de serviço, verificar acesso dos consumidores e produzir uma proposta real. Entrega automática só volta depois dos gates. |

[JUDGMENT] Quatro horas é orçamento de ensaio, não tempo demonstrado. Download de imagens e restauração contam; não parar o relógio quando fica inconveniente. Se um estranho precisar de mais de um dia com rede funcional e material completo, o requisito de reconstrução falhou. O que o ensaio pode reconstruir é a instalação declarada e os dados que efetivamente estão no material externo; alterações soltas no contêiner antigo não aparecem por desejo.

[JUDGMENT] O instrumento é um arquivo privado já acessível do telefone. Uma linha diária: `data | min_supervisao | uso_modelos_USD | infra_e_taxas_USD | fonte | nota`. Registrar minutos ao encerrar a última interação do dia; incluir revisão, aprovações, diagnóstico, interrupções e manutenção do Hermes, não só a tela de decisões. Ao menos semanalmente, copiar uso faturado de **todos** os provedores e cobranças de infraestrutura; alocar por dia somente para comparação, sem contar compra de crédito e consumo desse mesmo crédito duas vezes. Valor indisponível é `?`, jamais zero.

```text
2026-09-10 | 18 | 0.42 | ? | painel-provedor, fatura-VPS-pendente | 6 min corrigindo ambiente
```

[SPECULATIVE] A linha é fictícia; um registro real de sete dias a substitui. [JUDGMENT] Uma linha sem preenchimento é a falha barata a observar; não escrever um coletor para corrigir falta de hábito. Se o registro levar mais de um minuto/dia, reduzir campos a minutos e gasto acumulado semanal por fonte. Se não sobreviver a sete dias, a operação perde direito de alegar economia de atenção ou custo controlado.

[JUDGMENT] Orçamento deixa de depender de chamadas a `Budget.spend`. O executor não tem rede nem chave; o controlador tem somente uma credencial de modelo limitada no servidor, sem conta administrativa ou recarga automática. Todas as rotas auxiliares e de fallback devem usar essa mesma credencial ou estar desativadas; Claude Code e `helios-proxy` ficam fora da execução autônoma enquanto não demonstrarem o mesmo perímetro de cobrança. A observação que libera uma rota alternativa é a recusa real do fornecedor quando o teto foi atingido, pelo caminho efetivamente usado pelo harness.

[JUDGMENT] Escolha implementável para esse requisito: uma chave limitada do OpenRouter, sem instalar seu SDK, se esse fornecedor puder receber o código segundo as permissões já aplicáveis. Isso pode substituir a rota atual de modelos, não somar um segundo orçamento invisível. Se essa autorização ou o limite não estiverem disponíveis, o mecanismo de gasto permanece **incompleto** e o modo autônomo pago fica desligado. Não inventar que o proxy atual oferece um teto que não foi observado. [INFERENCE] O fornecedor documenta limite por chave e rejeição por falta de crédito. [Limites do OpenRouter](https://openrouter.ai/docs/api_reference/limits).

[JUDGMENT] `acceptance.py budget` testa uma chave protegida que já esteja esgotada: confirma teto finito, tenta uma requisição mínima, exige HTTP 402 e consulta o uso novamente. Não executamos esse teste com credencial real aqui. A aceitação completa inclui repetir o canário pelo Hermes instalado com o mesmo teto esgotado e reconciliar a cobrança depois; o teste direto não prova configuração de todos os chamadores nem ausência de atraso de faturamento. O teto de US$20 é global: um modelo a US$1 por tarefa, usado dez vezes/semana, já excederia US$40/mês antes da infraestrutura. Uma assinatura GitHub e taxas de compra de crédito também entram na soma.

## 13. Migração, retirada e custo de cada proposta

[JUDGMENT] A ordem é por valor esperado, não por maturidade do código disponível. A primeira linha pode começar hoje; não esperar terminar todo o desenho para interromper escritores inseguros. A observação que derruba a ordem é um incidente ativo de segredo/dados/DNS exigir contenção antes de qualquer trabalho de desenvolvimento. Nesse caso, conter o incidente vem primeiro.

| Ordem/data | Ação e resultado exigido | Valor; esforço inicial; reversibilidade |
|---|---|---|
| [JUDGMENT] 1 — Dia 1 | [JUDGMENT] Pausar jobs de realocação/reflexão e Somnus no scheduler real; impedir merge autônomo; preservar exportações consistentes. Rodar os testes vermelhos antes de aceitar outro “verified”. Conferir revogação das credenciais anteriormente expostas sem trazer valores para o modelo. | [JUDGMENT] Muito alto; 1–2 h; pausa é reversível, revogação não é desfeita reativando uma chave comprometida. |
| [JUDGMENT] 2 — Dia 2 | [JUDGMENT] Instalar UIDs, SSH obrigatório e contêiner descartável em laboratório. Testar escrita proibida, leitura de canário, ausência de rede/socket e diferença entre perfis. | [JUDGMENT] Muito alto; 3–4 h; remover unidades novas restaura o estado anterior declarado. |
| [JUDGMENT] 3 — Dia 3 | [JUDGMENT] Ativar e exercitar proteção de branches; separar credencial de publicação; proteger workflows e scripts com acesso a tokens. Manter somente proposta enquanto qualquer teste estiver BLOCKED. | [JUDGMENT] Alto; 2–3 h mais eventual plano GitHub; reversível pelo administrador, nunca pelo executor. |
| [JUDGMENT] 4 — Dia 4 | [JUDGMENT] Integrar o gate entregue com plano e imagem reais; implementar congelamento/identificação e publicação. Fazer o canário completo em repositório de teste e ensaiar inversão de uma entrega. | [JUDGMENT] Alto; 3–5 h; voltar à revisão instalada anterior, mantendo a fila parada durante a troca. |
| [JUDGMENT] 5 — Dia 5 | [JUDGMENT] Persistir inventário, imagens/dados únicos e recibos fora do Pi; exercitar reconstrução em máquina limpa com outra pessoa. | [JUDGMENT] Muito alto, depende da coleta anterior; 3–4 h ou mais se exportações faltarem; ensaio isolado é reversível. |
| [JUDGMENT] 6 — Dia 6 | [JUDGMENT] Usar o primeiro digest real; começar uma tarefa elegível por vez em nível 0/1; registrar minutos e custo. | [JUDGMENT] Alto; 30–60 min de preparação, depois ≤15 min/dia como alvo; voltar a proposta é imediato. |
| [JUDGMENT] 7 — Dia 7 | [JUDGMENT] Remover código/jobs mortos depois das exportações; comparar sete dias de atenção e resultados, sem reativar por desconforto com baixa atividade. | [JUDGMENT] Médio/alto; 1–2 h; código é recuperável por Git, dados só pela exportação verificada. |
| [JUDGMENT] 8 — Dia 30 | [JUDGMENT] Decidir Hindsight pela ablação e promover apenas classes que cumpriram a escada; excluir estados sem leitor demonstrado. | [JUDGMENT] Médio; experimento limitado a US$5/30 min adicionais; acesso semântico pode ser restabelecido sem router. |
| [JUDGMENT] 9 — Dia 90 | [JUDGMENT] Repetir o ensaio de perda do Pi e uma reversão; revisar custo líquido e caminhos de autoridade após atualizações. | [JUDGMENT] Alto; até meio dia de ensaio, explicitamente contabilizado; sem efeito na produção durante o laboratório. |
| [JUDGMENT] 10 — Dia 365 | [JUDGMENT] Revalidar capacidade/fornecedor e retirar compensações que perderam utilidade. Não ampliar o sistema por aniversário. | [JUDGMENT] Médio; 1 h de revisão mais ensaio se mudou o runtime; reversível por revisão de controle. |

[JUDGMENT] O orçamento inicial de migração é aproximadamente 14–21 horas distribuídas na semana, sem contar incidente ativo ou dados não exportáveis. Reconstruir uma instalação já declarada em um fim de semana é uma meta diferente de descobrir e migrar o estado atual. Se a implantação exceder esse esforço por complexidade do novo controle, retirar merge automático e conservar entrega de PR; não construir um novo motor para administrar o controle.

[JUDGMENT] Estes comandos podem iniciar a retirada **no Pi**, após confirmar o nome do contêiner. A lista determina quais nomes existem; um nome ausente é uma lacuna de implantação a registrar, não motivo para criá-lo. A CLI atual oferece list/pause/resume. [Scheduler do Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron).

```sh
docker exec hermes-raspberry hermes cron list
docker exec hermes-raspberry hermes cron pause hindsight-memory-route
docker exec hermes-raspberry hermes cron pause somnus-memory-maintenance
docker exec hermes-raspberry hermes cron pause hindsight-weekly-reflect
docker inspect --format '{{json .Mounts}}' hermes-raspberry
```

[JUDGMENT] Localizar também hooks/plugin Somnus e qualquer job com outro nome que invoque os mesmos escritores. Pausar um agendamento não encerra uma execução já iniciada: o operador confirma o processo e termina somente o job correspondente antes da exportação. Conferir que `jobs.json` está em montagem persistente e que a pausa continua após reiniciar o contêiner, no horário de manutenção. O timer systemd novo só entra depois da retirada das invocações antigas. Os jobs `coffee-healthcheck` e a infraestrutura Hindsight de outros consumidores não são removidos por associação de nomes.

[JUDGMENT] Não iniciar novas execuções desassistidas no perfil antigo durante a migração. Registrar e retirar suas cópias vivas de `hooks.py`, `somnus-gate.sh`, `somnus-sandbox.sh` e dos scripts de realocação; um arquivo removido do Git ainda pode existir em `~/.hermes/scripts/` ou no volume do contêiner. Antes de experimentar unidades/containers, o operador confirma DNS independente do Pi e testa resolução sem depender do túnel Cloudflare. Isso é preparação humana de recuperação, não uma nova permissão de Hermes para mudar o roteador.

### Contabilidade das propostas

[JUDGMENT] O limite de implementação é **800 linhas físicas de código/configuração operacional próprio**, excluindo testes, documentação e o harness existente. O pacote traz 182 linhas do gate e seis do wrapper SSH. Reservar até 120 para a sequência de uma tarefa, 280 para publicação/contrato/token e 212 para instalação, descarte, recibos e unidades. Isso é teto, não medição de software ainda inexistente. A implementação que ultrapassar o teto volta a produzir PRs e retira merge automático até ser simplificada. Nenhum dos dois arquivos entregues, isoladamente, estabelece a fronteira completa.

[JUDGMENT] Todos os comandos `make` da tabela abaixo são **interfaces de implantação especificadas, ainda não implementadas neste pacote**. Não criar stubs que imprimam sucesso. Cada alvo deve comparar o estado resultante com a revisão anterior preservada antes de instalação. O `Makefile` entregue contém apenas alvos de teste já funcionais. Essa limitação impede confundir um comando de rollback inventado no documento com uma recuperação disponível.

| Proposta | Delta e dependências | O que elimina | Um comando de retorno e o que ele deve fazer |
|---|---|---|---|
| [JUDGMENT] Retirada do Somnus/router | [EVIDENCE] Até −3.988 linhas físicas do snapshot, antes do salvamento opcional; zero runtime novo | [JUDGMENT] Motor, bancos de andamento, hooks, realocação e wrappers exclusivos | [JUDGMENT] `make restore-archive RELEASE=previous`: restaurar código/exportação em modo inativo; nunca religar escritores inseguros automaticamente. |
| [JUDGMENT] Contraprovas e gate | [EVIDENCE] +182 runtime e testes fornecidos; Python padrão/Git existentes | [JUDGMENT] Três scripts precheck/smoke/gated e confiança em exit 0 isolado | [JUDGMENT] `make rollback-control RELEASE=previous`: restaurar revisão instalada do gate com fila parada; permanecer sem merge se a anterior for insegura. |
| [JUDGMENT] Contenção e sequência fixa | [JUDGMENT] +6 entregues e parte dos tetos 120/212; Docker/SSH/systemd existentes | [JUDGMENT] Hook de texto, sandbox opcional, home compartilhado e schedulers sobrepostos | [JUDGMENT] `make remove-new-host-units`: parar os processos novos, remover somente unidades/UIDs novos sem dados únicos, restaurar configuração anterior registrada; não tocar Pi-hole. |
| [JUDGMENT] Publicação e proteção de branches | [JUDGMENT] Até +280 runtime; GitHub existente, identidade de aplicação nova; plano privado eventualmente pago; nenhum framework/SDK novo | [JUDGMENT] Token de entrega no executor, autoridade por prompt e cinco papéis fictícios | [JUDGMENT] `make disable-publication`: revogar/retirar a credencial de publicação e parar seu serviço; preservar proteções do servidor. Reverter proteção é ação administrativa específica, não rollback automático. |
| [JUDGMENT] Estado externo e recuperação | [JUDGMENT] Dentro dos +212 restantes; VPS e Git existentes; zero banco novo | [JUDGMENT] Backups locais apresentados como recuperação e estado aceito só no Pi | [JUDGMENT] `make disable-replication`: parar escritor novo preservando cópias; nenhum descarte da última cópia. Reverter localização sem perder dados exige operação explícita. |
| [JUDGMENT] Digest, confiança e registro | [JUDGMENT] Zero runtime adicional; texto e uma linha/dia; decisão aprovada reutiliza mecanismo de contrato | [JUDGMENT] Microaprovações rotineiras, taxa de merge como confiança, métricas inventadas | [JUDGMENT] `make set-trust LEVEL=0`: instalar política que só produz proposta, mantendo histórico de decisões; aprovação humana necessária para subir novamente. |
| [JUDGMENT] Memória por leitura e notas | [JUDGMENT] Zero runtime novo; redução dos escritores já contada acima; Hindsight desativado só para Hermes | [JUDGMENT] Migração entre bancos e retenção automática de conversas | [JUDGMENT] `make restore-memory-read`: restaurar somente leitura do snapshot aprovado, sem reviver router, invalidação ou segredo. |
| [JUDGMENT] Limite de gasto no fornecedor | [JUDGMENT] Zero runtime próprio de orçamento; serviço externo pode mudar para OpenRouter; custos/taxas entram na medição | [JUDGMENT] Budget estimado e rotas pagas laterais não contadas | [JUDGMENT] `make stop-model-access`: retirar credencial e parar o controlador; cobrança já realizada não é reversível. |

| Mecanismo | Como falha e sinal mais barato | Proxy tentador → observação real | Fronteira |
|---|---|---|---|
| [JUDGMENT] Retirada | [JUDGMENT] Job reaparece após rebuild; observar primeira execução agendada e o store de jobs | [JUDGMENT] `enabled=false` → nenhum escritor invocado no processo/scheduler real | [JUDGMENT] a/e |
| [JUDGMENT] Contraprova/gate | [JUDGMENT] Cobertura errada ou recibo reutilizado; introduzir mutação conhecida e alterar um byte após teste | [JUDGMENT] “PASS” → efeito pretendido e negação da mutação na revisão exata | [JUDGMENT] a/b para o verificador; c/d para entrega |
| [JUDGMENT] Contenção | [JUDGMENT] Montagem/credencial extra; canário conhecido e tentativa de escrita negada | [JUDGMENT] Flag de sandbox → acesso realmente ausente e obra útil possível em `/work` | [JUDGMENT] a/b/d/e |
| [JUDGMENT] Publicação | [JUDGMENT] Confundir PR/head/base ou check; observar negativa do servidor e árvore entregue | [JUDGMENT] PR “verde” → checks esperados executados, fonte correta, hash correto e nenhuma ref alterada na rejeição | [JUDGMENT] a/c/d |
| [JUDGMENT] Recuperação | [JUDGMENT] Backup ilegível/acesso perdido; restaurar um dado conhecido fora do Pi | [JUDGMENT] Arquivo de backup → serviço restaurado, consumidores atendidos e tempo medido | [JUDGMENT] a/d/e para custódia; mídia externa é durabilidade, não autoridade nova |
| [JUDGMENT] Digest/confiança | [JUDGMENT] Perguntas grandes ou incidentes escondidos; minutos registrados e reescritas comparadas | [JUDGMENT] Sete itens fechados → decisões explícitas, efeitos respeitados e atenção total dentro do alvo | [JUDGMENT] c/d quando a decisão autoriza efeito; o formato não é fronteira |
| [JUDGMENT] Memória | [JUDGMENT] Perder justificativa única; tarefa precisa perguntar algo que existia somente no store | [JUDGMENT] Fatos recuperados → resultado útil ou atenção poupada em comparação controlada | [JUDGMENT] e para escrita ausente; a/c para decisões |
| [JUDGMENT] Gasto | [JUDGMENT] Auxiliar usa outra chave ou cobrança atrasada; painel de todos os provedores e canário com teto esgotado | [JUDGMENT] Contador local → requisição negada no fornecedor e uso faturado conciliado | [JUDGMENT] a/b/d/e |

[JUDGMENT] Esses custos não devem ser somados duas vezes: exclusão dos scripts já está nas 3.988 linhas; contratos, confiança e digest usam a mesma publicação; 800 é o teto conjunto. Como instalação/publicador/rollback não estão implementados aqui, seus deltas exatos e comandos permanecem incompletos. A evidência que os completa é o diff real e os testes de efeitos após implantação, não este orçamento.

### Parar de fazer, e o sinal de retirada errada em 24 horas

| Retirada imediata | Sinal que justificaria reconsiderar, em 24h |
|---|---|
| [JUDGMENT] Gerar hipóteses/reflexões por horário sem tarefa autorizada | [JUDGMENT] Uma necessidade real deixa de ser detectada e há evidência de que o job a detectava antes. Ficar quieto não é falha. |
| [JUDGMENT] Realocar e invalidar memória | [JUDGMENT] Uma tarefa autorizada perde acesso a fato único conhecido; restaurar leitura/exportação, não invalidação. |
| [JUDGMENT] Permitir shell geral do operador | [JUDGMENT] Trabalho ordinário não consegue testar/escrever nem em `/work`; corrigir o ambiente limitado, não fornecer o home inteiro. |
| [JUDGMENT] Repetir smoke a cada 15 min para o mesmo candidato como fonte de “saúde” | [JUDGMENT] Uma obrigação de monitoramento de serviço vivo fica sem cobertura; manter um healthcheck de serviço explicitamente separado da verificação de código. |
| [JUDGMENT] Criar scripts e relatórios soltos em home | [JUDGMENT] Artefato aceito não está no registro persistido; corrigir a entrega, sem tornar scratch armazenamento oficial. |
| [JUDGMENT] Cinco papéis com sessões pagas fixas | [JUDGMENT] Uma tarefa concreta perde revisão obrigatória por consequência identificada; acrescentar a revisão daquela tarefa, não a companhia inteira de personagens. |
| [JUDGMENT] Auto-instalar dependência para destravar teste | [JUDGMENT] Build legítimo fica BLOCKED por pacote ausente; atualizar a imagem em operação humana e verificar o lock. |

## 14. Os testes, inclusive o que não foi demonstrado

[EVIDENCE] O pacote contém `tests/legacy_regressions.py`, `tests/test_smoke.py`, `acceptance.py` e `TESTS.md`. A execução local produziu **sete regressões vermelhas no código antigo, uma integração BLOCKED por ausência de entrypoint de produção, e 12 testes verdes do gate novo**. Docker não está instalado neste ambiente e a criação de namespace de rede foi negada; nenhum teste de isolamento no Pi foi declarado verde. Isso não contradiz a reprodução anterior do oitavo defeito: ausência de integração é precisamente a razão para não fabricar uma execução fictícia como teste de produção.

| Defeito | Teste escrito e observação | O que deve passar no destino |
|---|---|---|
| [EVIDENCE] 1. Substring do hook | [EVIDENCE] `test_01`: comando com comentário altera arquivo que deveria permanecer igual; vermelho no legado | [JUDGMENT] `acceptance.py namespace` atravessa a chave SSH obrigatória; ataque não escreve fora de `/work`, não vira root e o artefato permitido é lido por observador externo. Completar os testes de host de `TESTS.md`. |
| [EVIDENCE] 2. Rollback mentiroso | [EVIDENCE] `test_02` compara bytes da identidade e existência do arquivo acrescentado, não `rollback.ok`; vermelho | [JUDGMENT] O executor não alcança a identidade; descarte remove todos os arquivos/processos do candidato. Reversão de merge/host exige o ensaio separado escrito em `TESTS.md`. |
| [EVIDENCE] 3. Truncamento/ID/invalidação | [EVIDENCE] `test_03` fornece três fatos longos e read-back mentiroso; ao menos um fato deixa de existir nas duas fontes; vermelho | [JUDGMENT] A capacidade de escrever/invalidate some. Testar tentativa de chamada e comparar os registros remotos reais antes/depois, incluindo o fim do terceiro fato. |
| [EVIDENCE] 4. Erro bruto no modelo | [EVIDENCE] `test_04` captura o argumento destinado ao modelo com canário fictício; vermelho. O teste novo do gate confirma ausência de stdout/stderr bruto e de variável secreta herdada | [JUDGMENT] Canário sob custódia protegida permanece inacessível ao executor e ausente de contexto, arquivos, logs e objetos Git. Testar também erro do provedor que ecoa canário. |
| [EVIDENCE] 5. Limite sem alcance dos chamadores | [EVIDENCE] `test_05` esgota chamadas permitidas e observa `build_candidate` produzir efeito mesmo assim; vermelho | [JUDGMENT] Chave esgotada nega chamada real no provedor; repetir via harness com auxiliares/fallback desativados. `acceptance.py budget` é uma parte desse teste, não toda a prova. |
| [EVIDENCE] 6. Fingerprint antes do teste | [EVIDENCE] `test_06` observa `[3, 0]` no legado; o novo gate repete o comando, continua BLOCKED e não deixa recibo PASS | [EVIDENCE] Testes de retry, repo ausente, worktree, timeout, dirty tree, corrida e gravação posterior passaram localmente. |
| [EVIDENCE] 7. IDs duplicados/fixtures insuficientes | [EVIDENCE] `test_07` passa 20 cópias do mesmo caso pela adjudicação e observa arquivo realmente criado pelo `stage` do daemon; vermelho | [JUDGMENT] Motor não existe nem publica. O plano ordinário recusa vazio/duplicatas; conferir omissão e substituição dos testes exigidos antes de dar credencial de entrega. |
| [EVIDENCE] 8. Runtime só nos testes | [EVIDENCE] Teste legado marca BLOCKED, não inventa um CLI inexistente para alegar uma oitava falha unitária | [JUDGMENT] `acceptance.py canary` chama o Hermes instalado e exige arquivo com nonce novo, lido pela montagem conhecida pelo operador; depois o publicador real entrega esse mesmo artefato em repo de teste. |

[JUDGMENT] A retirada torna os caminhos antigos de realocação, auto-adjudicação, rollback expansivo e Runtime Somnus impossíveis **quando seus jobs, credenciais e pontos de entrada forem efetivamente retirados**. Apagar um arquivo sem remover uma instalação antiga não faz isso. As propriedades de host, fornecedor, servidor GitHub e restauração não cabem inteiramente em teste unitário; o pacote escreve os procedimentos de aceitação e se recusa a produzir PASS onde falta ambiente.

[JUDGMENT] Para executar localmente, sem dependência Python nova:

```sh
make -C hermes-phase2 test
python3 hermes-phase2/tests/legacy_regressions.py --source audit-work/source -v
python3 hermes-phase2/acceptance.py namespace --ssh-target hermes-executor
```

[EVIDENCE] O segundo comando retorna falha esperada no snapshot antigo; o terceiro retorna exit 3 neste ambiente. [JUDGMENT] Não inverter essa convenção com `|| true` em CI. No destino, uma aceitação obrigatória BLOCKED impede ativação de autonomia; não conta como teste aprovado nem como falha funcional do produto.

## 15. Onde este desenho falha

[JUDGMENT] O ponto fraco deliberado é o perímetro inicial estreito. O executor sem rede não instala dependências, não consulta serviço produtivo e pode produzir candidatos que só o CI Windows consegue verificar. Isso aumenta espera e exige imagens preparadas. O sinal de desenho ruim é mais da metade das tarefas elegíveis ficar BLOCKED por ambiente em duas semanas; corrigir a imagem/seleção de tarefa antes de ampliar privilégios. Não medir sucesso por utilização constante do Pi.

[JUDGMENT] Descartar erros brutos no gate também custa diagnóstico. O executor pode reproduzir o teste público correspondente no seu ambiente sem credenciais; o verificador retorna identificador do check e estado. Se a causa só puder ser conhecida lendo um log privilegiado, essa investigação é humana e conta no orçamento. Duas tentativas sem nova evidência encerram a tarefa; não gerar reescritas cegas porque o resultado contém somente FAIL.

[JUDGMENT] A base confiável ainda pode ter defeitos: parser Git, Docker/kernel, SSH, harness e publicador. Separar UIDs não contém um exploit de kernel; o namespace não protege contra um volume perigoso que o instalador autorizou. O sinal inicial mais barato é o teste de canário e inventário efetivo em cada mudança desses componentes. Modelos melhores não eliminam esse trabalho. O acesso root do operador continua podendo desfazer a política; o desenho protege contra o executor, não contra um administrador decidido a anulá-la.

[JUDGMENT] A instrução absoluta de nenhum segredo em qualquer contexto não foi provada para texto arbitrário: um humano pode colar um segredo ou um arquivo aprovado pode conter um valor até então desconhecido. O desenho garante ausência de **capacidades e credenciais conhecidas** no executor somente depois do teste de implantação, e elimina ingestão automática de logs brutos. Não promete um detector perfeito. Um único canário visto em contexto/log/objeto Git suspende a execução e exige revogação da credencial afetada, sem confiar em sanitização posterior.

[JUDGMENT] O SLA de cinco minutos está **aspiracional**, e o requisito literal de reconstrução só do repositório também não está satisfeito sem custódia externa de acesso. A ausência de UPS permanece: trabalho ainda não aceito pode desaparecer; dados aceitos dependem do reconhecimento externo. Perder edição humana inédita, depender de uma imagem ARM que só existia no Pi ou não recuperar uma credencial derruba o invariante de perda zero. Esses são testes de ativação e de recuperação, não itens cosméticos de documentação.

[JUDGMENT] Não afirmo que a economia de atenção exista. Ao fim de 30 dias, se manutenção + supervisão ultrapassarem o tempo estimado para as mesmas entregas manuais, ou se o sistema consumir mais de 105 minutos/semana por duas semanas sem uma fila externa excepcional, voltar ao modo sob demanda. Registrar também entregas úteis e reescritas; otimizar minutos simplesmente entregando menos não satisfaz a missão. O número que derruba essa retirada é benefício líquido positivo documentado nas tarefas comparáveis, incluindo manutenção e custo de decisão.

[JUDGMENT] Com dez vezes o hardware e orçamento, eu separaria fisicamente o executor do DNS doméstico, colocaria energia protegida no estado que precisa permanecer local e compraria mais capacidade de verificação em ambientes compatíveis com a aplicação. Manteria uma tarefa por autorização, credenciais fora do executor, artefato identificado e recuperação exercitada. Não restauraria o motor Somnus, a migração de memória ou os cinco papéis por haver dinheiro disponível. A observação que justificaria paralelismo seria uma fila de trabalho independente já autorizado esperando CPU/CI, com atenção humana e risco ainda dentro do limite; disponibilidade de RAM sozinha não justificaria nada.
