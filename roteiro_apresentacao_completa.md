# Roteiro de Apresentação Completa — Trabalho 2 MC714

> **Como usar este roteiro:** ele intercala os **12 slides** (`apresentacao_projeto.html`) com o **hands-on no terminal** (`ROTEIRO_VIDEO.md`).
> Cada bloco diz **(A) em qual slide você está**, **(B) o que falar** e **(C) o que mostrar/apontar no terminal e quando**.
> Marcações: 🖥️ = vá para o terminal · 📊 = vá para os slides · 🔴 AO VIVO = ação executada na hora da gravação.

---

## Preparação (antes de gravar)

1. **Slides** abertos em tela cheia no navegador (`apresentacao_projeto.html`). Use ← → para navegar.
2. **Dois terminais** lado a lado, fonte grande:
   - **Terminal A** (principal): `docker compose`.
   - **Terminal B** (falha): `docker stop`/`start`.
3. Cluster parado: `docker compose down`.
4. Tenha o cronômetro à vista. Meta: ~10 min.

> **Estrutura geral:** explico o algoritmo no slide → mostro ele acontecendo no terminal. Os slides de teoria (1–8) vão antes do `up`; o `up` roda enquanto explico Lamport/Ricart; o `docker stop` ao vivo cai no slide 9; slides 10–12 fecham com a prova nos logs.

---

## BLOCO 1 — Abertura e visão geral (0:00 – 1:30)

### 📊 Slide 1 (Capa)
**Falar:**
> "Este é o Trabalho 2 de MC714, Sistemas Distribuídos. Vou demonstrar um cluster de 5 nós que se comunicam por gRPC real, integrando três algoritmos clássicos: Relógio de Lamport, Exclusão Mútua de Ricart-Agrawala e Eleição de Líder com Bully."

### 📊 Slide 2 (Visão Geral — 3 algoritmos)
**Falar:**
> "A ideia central é que os três algoritmos **não vivem isolados**: o Lamport é a 'cola' — ele carimba toda mensagem; o Ricart-Agrawala usa esse carimbo `(ts, id)` como critério de prioridade; e o Bully garante tolerância a falhas reelegendo o líder."

### 📊 Slide 3 (Stack Tecnológica)
**Falar:**
> "A stack é Python pela legibilidade dos algoritmos, gRPC sobre Protocol Buffers para comunicação **real via TCP**, e Docker Compose para isolar cada nó. Ponto importante do enunciado: **proibido simular** mensagens via arquivos ou memória compartilhada — aqui é tudo gRPC."

🖥️ **(opcional, transição rápida ao Terminal A):**
```bash
ls
cat docker-compose.yml
```
> "Cada um dos 5 serviços é um contêiner independente, com IP próprio, escutando gRPC na porta 50051 de uma rede bridge."

---

## BLOCO 2 — Teoria dos algoritmos (1:30 – 3:30)

> Mantenha-se nos slides. Esses 4 slides preparam o espectador para entender os logs depois.

### 📊 Slide 4 (Lamport)
**Falar:**
> "O relógio de Lamport tem duas operações. `tick()` incrementa o clock local **antes de enviar** qualquer mensagem. `update(T)` é chamado **ao receber**, e aplica `max(local, T) + 1` — é isso que garante que o receptor nunca fique causalmente atrás do emissor. Tudo protegido por lock, mas o log sai **fora** do lock para não segurar I/O."

### 📊 Slide 5 (Ricart-Agrawala)
**Falar:**
> "No Ricart-Agrawala, quando um nó quer a Seção Crítica ele pede a todos. A regra de quem adia quem é: 'eu seguro o seu REPLY se eu estou na CS, ou se eu também quero e meu par `(ts, id)` é menor que o seu'. Timestamp menor = prioridade maior, e o `id` desempata. Isso dá uma **ordem total determinística**."
> "Um nó passa por RELEASED → WANTED (esperando N-1 REPLYs) → HELD (na CS) → e ao sair libera os REPLYs adiados."

### 📊 Slide 6 (Comunicação gRPC — Fire-and-Forget)
**Falar:**
> "São 5 RPCs unárias. O detalhe crítico: se o `RequestAccess` **bloqueasse** esperando a CS liberar, o ThreadPool do gRPC esgotaria e daria deadlock. Por isso REQUEST e REPLY são RPCs **separadas**: o handler registra o pedido, devolve Ack na hora, e quando o nó sai da CS dispara os REPLYs proativamente."

### 📊 Slide 7 (Concorrência / Thread-Safety)
**Falar:**
> "Como o gRPC usa um pool de 20 workers, várias threads mexem no estado ao mesmo tempo. Cada módulo tem seu lock: o Lamport no contador, o Ricart-Agrawala cobrindo estado + fila de adiados, e o Bully cobrindo `leader_id` e a flag de eleição. A transição WANTED→HELD é atômica. Resultado: zero deadlock, zero race condition."

### 📊 Slide 8 (Bully)
**Falar:**
> "O Bully: quando o heartbeat do líder falha, o nó manda ELECTION para todos de ID **maior**. Se alguém responde, ele recua ('ok, você assume'). Se ninguém responde, ele se declara líder e anuncia COORDINATOR. Um detalhe elegante da nossa implementação: o **próprio Ack da RPC já serve como o 'OK'** do Bully — não precisamos de mensagem extra."

---

## BLOCO 3 — DEMO: subindo o cluster + eleição inicial (3:30 – 5:00)

### 🖥️ Terminal A — execute:
```bash
docker compose up --build
```

> Deixe os slides na lateral ou volte ao slide 8 (Bully) enquanto os logs sobem — a teoria de Bully casa com o que aparece agora.

**Apontar nos logs, na ordem em que aparecem:**

1. **Discovery (wait-for-peers)** — `📡 [NET]`:
   > "Cada nó descobre os vizinhos um a um: `Peer 4 respondeu! (3/4 prontos)` … até `Todos os 4 peers prontos!`."

2. **Eleição Bully inicial** — `👑 [BULLY]`:
   > "Os nós menores mandam ELECTION para os maiores. O Node 5 tem o maior ID, ninguém acima dele responde, então: **`SOU O NOVO LIDER! Anunciando COORDINATOR a [1, 2, 3, 4]`**."

3. **COORDINATOR aceito:**
   > "E todos reconhecem: `👑 Node X | Reconhece Node 5 como o novo LIDER`."

4. **⚠️ Explicar a redundância de eleições (importante, antecipe a dúvida):**
   > "Reparem que o Node 5 se declara líder **mais de uma vez**. Isso é esperado: como cada nó dispara uma eleição de validação **ao entrar** no cluster, e eles entram escalonados, a eleição roda algumas vezes. É **idempotente** — converge sempre para o maior ID vivo. Não é erro."

---

## BLOCO 4 — DEMO: Relógio de Lamport ao vivo (5:00 – 5:45)

### 📊 Volte ao Slide 4 (Lamport) por uns segundos, depois 🖥️ Terminal A.

**Falar + apontar `🟢 [LAMPORT]`:**
> "Em **toda** troca de mensagem o relógio evolui. Vejam estes saltos quando o Node 2 termina de inicializar com clock já alto e 'puxa' os outros:"

- `Node 1 | Clock atualizado: 8 -> 16 (via msg de Node 2)`
- `Node 3 | Clock atualizado: 8 -> 17 (via msg de Node 2)`
- `Node 5 | Clock atualizado: 10 -> 19 (via msg de Node 2)`

> "O receptor salta para `max(local, recebido) + 1`. Ele **nunca fica atrás** do emissor — é a causalidade de Lamport na prática."

---

## BLOCO 5 — DEMO: Exclusão mútua Ricart-Agrawala (5:45 – 7:30)

> **Este é o coração da demonstração.** Vá devagar aqui.

### 📊 Tenha o Slide 5 (Ricart) ou Slide 11 (logs) à mão; 🖥️ foco no Terminal A.

**1. REQUEST** — `🟡 [RICART]`:
> "O Node 1 quer a Seção Crítica: `Solicitando Secao Critica... (Lamport: 78, aguardando 4 REPLYs)`. Ele manda REQUEST aos 4 vizinhos."

**2. Concessão imediata** — `🟢 [RICART]`:
> "Como ninguém mais quer, todos concedem na hora: `Concedendo permissao ao Node 1 imediatamente (estado=RELEASED)`. Node 1 entra: `✅ Entrou na Secao Critica! (Lamport: 87)`."

**3. ADIAMENTO (o momento mais importante)** — `🔴 [RICART]`:
> "Agora vem o ouro. Enquanto o Node 1 trabalha, o Node 5 e o Node 2 também pedem a CS. Olhem o que o Node 1 faz:"
- `🔴 Node 1 | Pedido do Node 5 ADIADO (minha prioridade: (ts=78,id=1) < (ts=96,id=5))`
- `🔴 Node 1 | Pedido do Node 2 ADIADO (minha prioridade: (ts=78,id=1) < (ts=100,id=2))`
> "Timestamp menor = prioridade maior. O Node 1 segura os REPLYs. E reparem: o **próprio Node 5 já adia o Node 2**, porque `(ts=96,id=5) < (ts=100,id=2)`. A fila se ordena sozinha, sem coordenador central."

**4. SAÍDA + REPLY proativo** — `🔵 [RICART]`:
> "Node 1 sai e **proativamente** libera os adiados: `Saiu da Secao Critica. Enviando REPLY adiado para: [2, 5]`. Só agora o próximo pode entrar."

**5. A SEQUÊNCIA CORRETA (frase de efeito):**
> "Acompanhem a ordem de entrada na CS: **Node 1, depois 5, depois 2, depois 3, depois 4**. Isso corresponde **exatamente** à ordem dos timestamps: 78, 96, 100, 104, 109. Em nenhum momento dois nós estão na CS ao mesmo tempo. O algoritmo serializou o acesso usando só os relógios de Lamport."

---

## BLOCO 6 — CLÍMAX: matando o líder e reeleição Bully (7:30 – 9:00)

### 📊 Slide 9 (Tolerância a Falhas) — abra ANTES de matar o nó.
**Falar:**
> "Agora a tolerância a falhas. Uma thread dedicada pinga o líder a cada 2 segundos. O líder atual é o Node 5. Vou matá-lo e vocês vão ver o sistema se recuperar sozinho em uns 4 segundos."

### 🖥️ 🔴 AO VIVO — Terminal B, execute:
```bash
docker stop node5
```

**Apontar no Terminal A, conforme aparece:**

1. **Detecção** — `👑 [BULLY]`:
   > "Olhem: `Falha do lider (Node 5) detectada!` — o heartbeat estourou o timeout."

2. **ELECTION:**
   > "Quem detectou manda ELECTION aos de ID maior. O Node 4 é o maior **vivo**, então assume a eleição."

3. **COORDINATOR:**
   > "`Node 4 | SOU O NOVO LIDER!` e todos reconhecem o Node 4."

4. **Sistema continua:**
   > "E o mais importante: o Ricart-Agrawala **continua funcionando** normalmente, agora com 4 nós. O sistema se auto-recuperou sem intervenção."

### 🖥️ (Opcional) Restaurar — Terminal B:
```bash
docker start node5
```
> "Se eu trago o Node 5 de volta, na próxima eleição ele reassume a liderança por ter o maior ID."

---

## BLOCO 7 — Infraestrutura e prova nos logs (9:00 – 9:45)

### 📊 Slide 10 (Docker Compose)
**Falar:**
> "Tudo isso roda em 5 contêineres numa única rede bridge, porta 50051, **zero simulação**. Cada nó recebe seu `NODE_ID` e a lista de `PEERS` por variável de ambiente."

🖥️ (opcional) `cat docker-compose.yml` rápido pra evidenciar os 5 serviços.

### 📊 Slide 11 (Resultados / Logs Didáticos)
**Falar (amarrando com o que acabaram de ver no terminal):**
> "Esta é a legenda dos logs que vimos: 🟢 salto do relógio Lamport, 🟡 solicitando a CS, 🔴 pedido adiado, ✅ entrou na CS, 🔵 saiu e liberou REPLYs, 👑 eleição. Cada nó ainda tem cor própria no terminal para facilitar o acompanhamento visual."

---

## BLOCO 8 — Conclusão (9:45 – 10:00)

### 📊 Slide 12 (Conclusão)
**Falar:**
> "Resumindo o que demonstrei: o Lamport ordena causalmente toda mensagem e **alimenta** o Ricart-Agrawala, que garante exclusão mútua sem deadlock; o REQUEST/REPLY separado evita o deadlock do ThreadPool; e o Bully detecta a falha do líder e recupera a liderança em ~4 segundos — tudo sobre gRPC/TCP real entre contêineres Docker isolados. Os três algoritmos trabalham juntos como um sistema só. Obrigado."

### 🖥️ Terminal A — encerrar:
```bash
docker compose down
```

---

## Mapa rápido Slide ↔ Terminal

| Momento | Slides | Terminal |
|---|---|---|
| Abertura | 1, 2, 3 | `ls`, `cat docker-compose.yml` (opcional) |
| Teoria | 4, 5, 6, 7, 8 | — |
| Subida + Bully inicial | (8 ao fundo) | `docker compose up --build` → `📡 [NET]`, `👑 [BULLY]` |
| Lamport ao vivo | 4 | `🟢 [LAMPORT]` (saltos 8→16, 8→17, 10→19) |
| Ricart-Agrawala | 5 / 11 | `🟡` `🟢` `🔴` `✅` `🔵` (ordem 1→5→2→3→4) |
| **Matar líder** 🔴 | 9 | **`docker stop node5`** → reeleição p/ Node 4 |
| Infra + prova | 10, 11 | logs / `docker-compose.yml` |
| Conclusão | 12 | `docker compose down` |

---

## Checklist pré-gravação

- [ ] Docker Desktop rodando
- [ ] `docker compose down` (sem containers antigos)
- [ ] Slides em tela cheia + dois terminais lado a lado, fonte grande
- [ ] Cronômetro visível
- [ ] Gravação iniciada (tela inteira)
- [ ] **Lembrar de executar `docker stop node5` ao vivo** — a reeleição NÃO aparece se o cluster só subir
