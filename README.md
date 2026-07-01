# Trabalho 2 — MC714 (Sistemas Distribuídos)

Sistema distribuído que integra **Relógio Lógico de Lamport**, **Exclusão Mútua (Ricart-Agrawala)** e **Eleição de Líder (Bully)**, com comunicação real via **gRPC** entre 5 nós em contêineres Docker.

---

## Pré-requisitos

| Ferramenta       | Versão mínima |
|------------------|---------------|
| Docker           | 24+           |
| Docker Compose   | v2+           |

> Não é necessário instalar Python nem dependências locais — tudo roda dentro dos contêineres.

---

## Como executar

### 1. Subir o cluster + o painel (build + up)

```bash
docker compose up --build
```

Ou, usando o Makefile:

```bash
make up
```

Os 5 nós (node1 a node5) iniciam, descobrem uns aos outros via heartbeat, elegem um líder e começam a disputar a Região Crítica periodicamente. Junto sobe também o container `dashboard`.

### 2. Abrir o painel visual (recomendado) 🖥️

Abra no navegador:

```
http://localhost:8080
```

O painel desenha os **5 nós em rede (pentágono)** e **anima as mensagens voando** entre eles em tempo real, coloridas por tipo (REQUEST, REPLY, ELECTION, COORDINATOR, HEARTBEAT). Cada nó mostra:

- **Relógio de Lamport** (⏱ dentro do nó, atualizando a cada mensagem);
- **Estado do Ricart-Agrawala** — anel amarelo tracejado (`🟡 quer entrar`) ou anel verde brilhando (`✅ na região crítica`);
- **👑 Coroa** sobre o líder atual;
- pulso branco quando o nó **recebe** uma mensagem.

Além do grafo:

- **Banner "Região Crítica"** no topo — mostra quem está dentro agora (prova visual da exclusão mútua: nunca há dois ao mesmo tempo);
- **Painel de logs** colorido e filtrável por algoritmo (Lamport / Ricart-Agrawala / Bully / Rede);
- toggle **"mostrar heartbeats"** para limpar a animação quando quiser focar só nos algoritmos.

**Controles (você comanda tudo pela UI):**

| Botão | O que faz |
|-------|-----------|
| ⏸️ **Pausar / ▶️ Continuar** | Congela a simulação **de verdade**: cada nó para seus loops de fundo, então o tempo e os relógios de Lamport param de avançar (os pacotes ficam parados no ar). Ao retomar, tudo continua do ponto exato — nenhum tempo passou |
| ⚡ **Eleição** | Dispara uma eleição Bully a partir daquele nó |
| 💀 **Matar** / ♻️ **Reviver** | Simula a queda do nó (os demais detectam e reelegem) e o traz de volta |
| 🔓 **Pedir RC** | Faz o nó pedir a Região Crítica |

Cada nó expõe uma API HTTP própria (portas `18001`–`18005` no host) que o painel consome; o navegador fala direto com cada nó.

> **Região Crítica é MANUAL por padrão.** Os nós **não** disputam a Região Crítica sozinhos — ela fica **vazia** até você clicar em **🔓 Pedir RC** num nó. Isso deixa a demonstração inteiramente sob seu controle. Para voltar ao modo automático (nós tentam entrar periodicamente por conta própria), defina `AUTO_CS=1` no ambiente dos serviços em `docker-compose.yml`.

### 3. (Opcional) Acompanhar os logs "crus" no terminal

```bash
docker compose logs -f
```

Os mesmos logs coloridos continuam saindo no terminal — o painel apenas os agrega de forma visual.

### 4. Demonstrar falha do líder (reeleição Bully)

**Pela UI (recomendado):** clique em **💀 Matar** no card do líder (Node 5). A coroa migra para o Node 4 em segundos, e o banner da Região Crítica continua funcionando — tolerância a falhas ao vivo. Clique em **♻️ Reviver** para trazê-lo de volta.

**Pela linha de comando (queda real do processo):**

```bash
docker stop node5     # o card fica OFFLINE; efeito idêntico no painel
docker start node5    # restaura
```

### 5. Parar o cluster

```bash
docker compose down
```

---

## O que você vai ver no terminal

Os logs são coloridos (ANSI) e usam emojis para facilitar a leitura durante o vídeo de demonstração:

| Emoji | Significado |
|-------|-------------|
| 🟢 `[LAMPORT]` | Atualização do relógio lógico (salto de timestamp) |
| 🟡 `[RICART]`  | Nó solicitando a Seção Crítica |
| 🔴 `[RICART]`  | Pedido ADIADO (o nó tem prioridade e está na CS) |
| ✅ `[RICART]`  | Nó entrou na Seção Crítica |
| 🔵 `[RICART]`  | Nó saiu da CS e enviou REPLYs adiados |
| 👑 `[BULLY]`   | Evento de eleição (ELECTION / COORDINATOR / líder detectado) |
| 📡 `[NET]`     | Evento de rede (peer descoberto, servidor iniciado) |

Cada nó tem uma cor ANSI própria, permitindo diferenciar visualmente a origem das mensagens mesmo com os logs intercalados.

---

## Estrutura do projeto

```
.
├── proto/node.proto          # Contrato gRPC (todas as mensagens com lamport_ts)
├── src/
│   ├── lamport_clock.py      # Relógio lógico de Lamport (thread-safe)
│   ├── ricart_agrawala.py    # Exclusão mútua distribuída
│   ├── bully.py              # Eleição de líder (Bully)
│   ├── server.py             # Handlers gRPC (fire-and-forget)
│   ├── node.py               # Orquestrador (rede + loops + eleição)
│   ├── config.py             # Leitura de NODE_ID/PEERS/CS_INTERVAL
│   ├── logger.py             # Logging colorido + buffer p/ o dashboard
│   ├── dashboard_api.py      # API HTTP por nó (estado, logs, controles)
│   └── main.py               # Entrypoint
├── dashboard/
│   └── index.html            # Painel web visual (servido em :8080)
├── Dockerfile
├── docker-compose.yml        # 5 nós + dashboard, rede bridge isolada
├── requirements.txt
├── Makefile
├── RELATORIO.md              # Relatório técnico
├── ROTEIRO_VIDEO.md          # Script para gravação do vídeo
└── roteiro_apresentacao_completa.md  # Roteiro slides + painel (apresentação)
```

---

## Variáveis de ambiente configuráveis

| Variável      | Padrão | Descrição |
|---------------|--------|-----------|
| `NODE_ID`     | —      | ID único do nó (1-5) |
| `PEERS`       | —      | Lista `host:porta` de todos os nós |
| `CS_INTERVAL` | `5`    | Segundos entre tentativas de entrar na CS |

---

## Licença

Projeto acadêmico — uso restrito à disciplina MC714/Unicamp.
