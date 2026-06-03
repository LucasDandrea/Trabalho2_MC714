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

### 1. Subir o cluster (build + up)

```bash
docker compose up --build
```

Ou, usando o Makefile:

```bash
make up
```

Os 5 nós (node1 a node5) iniciam, descobrem uns aos outros via heartbeat, elegem um líder e começam a disputar a Seção Crítica periodicamente.

### 2. Acompanhar os logs (em outro terminal)

```bash
docker compose logs -f
```

### 3. Demonstrar falha do líder (reeleição Bully)

Identifique o líder atual nos logs (Node 5 na eleição inicial) e mate-o:

```bash
docker stop node5
```

Observe nos logs dos demais nós a detecção de falha e a reeleição automática.

Para restaurar:

```bash
docker start node5
```

### 4. Parar o cluster

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
│   ├── logger.py             # Logging colorido com emojis
│   └── main.py               # Entrypoint
├── Dockerfile
├── docker-compose.yml        # 5 nós, rede bridge isolada
├── requirements.txt
├── Makefile
├── RELATORIO.md              # Relatório técnico
└── ROTEIRO_VIDEO.md          # Script para gravação do vídeo
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
