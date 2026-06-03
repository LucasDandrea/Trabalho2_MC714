# Roteiro de Vídeo — Demonstração do Trabalho 2 MC714

---

## Preparação antes de gravar

1. Feche aplicativos desnecessários (o terminal deve ser o foco).
2. Abra **dois terminais** lado a lado:
   - **Terminal A** (principal): para comandos `docker compose`.
   - **Terminal B** (demonstração de falha): para `docker stop`/`start`.
3. Certifique-se de que o cluster NÃO está rodando (`docker compose down`).
4. Aumente o tamanho da fonte do terminal para ficar legível na gravação.

---

## Seção 1 — Introdução (0:00 – 1:30)

### O que falar:

> "Este é o Trabalho 2 de MC714 — Sistemas Distribuídos. Vou demonstrar um cluster de 5 nós que se comunicam via gRPC real, integrando três algoritmos: Relógio de Lamport, Exclusão Mútua de Ricart-Agrawala e Eleição de Líder com o algoritmo Bully."

### O que mostrar:

1. Mostre brevemente a estrutura do projeto no terminal:
   ```bash
   ls
   ```
2. Mostre o `docker-compose.yml` para evidenciar os 5 serviços:
   ```bash
   cat docker-compose.yml
   ```
3. Explique:
   > "Cada nó é um contêiner Docker independente, comunicando por gRPC na porta 50051 de uma rede bridge. Não há simulação de mensagens — tudo é TCP real."

---

## Seção 2 — Subindo o cluster e eleição inicial (1:30 – 3:30)

### Comandos:

```bash
docker compose up --build
```

### O que falar:

> "Estou subindo os 5 nós. Primeiro eles fazem discovery — cada nó pinga os vizinhos até todos estarem prontos. Depois, cada nó inicia uma eleição com o algoritmo Bully."

### O que apontar nos logs:

1. **Wait-for-peers:**
   > "Aqui vemos 📡 [NET] — cada nó descobre os vizinhos um a um via heartbeat."

2. **Eleição Bully:**
   > "Os nós menores enviam ELECTION aos maiores. O Node 5, que tem o maior ID, não tem ninguém acima dele, se declara líder e anuncia COORDINATOR a todos."

3. **COORDINATOR aceito:**
   > "Todos os nós reconhecem Node 5 como líder — veja as mensagens 👑 [BULLY] Reconhece Node 5."

---

## Seção 3 — Relógio de Lamport em ação (3:30 – 4:30)

### O que falar:

> "Agora reparem nas mensagens 🟢 [LAMPORT]. Em TODA troca de mensagem o relógio evolui. A regra é: ao receber, C = max(C_local, C_recebido) + 1."

### O que apontar:

> "Vejam este salto: Node 1 foi de 26 para 94 ao receber uma mensagem do Node 5 que já tinha clock 93. Isso é a causalidade de Lamport — o receptor nunca fica 'atrás' do emissor."

---

## Seção 4 — Exclusão mútua Ricart-Agrawala (4:30 – 7:00)

### O que falar:

> "Agora vou focar no Ricart-Agrawala. Os nós tentam entrar na Seção Crítica periodicamente. Quando há contenção, o algoritmo usa o par (timestamp, node_id) para decidir quem tem prioridade."

### O que apontar nos logs:

1. **REQUEST:**
   > "🟡 [RICART] Node X solicitando Seção Crítica — ele envia REQUEST a todos os 4 vizinhos."

2. **ADIAMENTO (o momento mais importante):**
   > "🔴 [RICART] — veja: Node 4 ADIOU o pedido do Node 5 porque (ts=88, id=4) é MENOR que (ts=104, id=5). Timestamp menor = maior prioridade. O Node 4 está na CS e tem direito."

3. **ENTRADA NA CS:**
   > "✅ [RICART] — Node 4 entrou! Ele trabalha por uns 2-3 segundos."

4. **SAÍDA E REPLY ADIADO:**
   > "🔵 [RICART] — Node 4 saiu e PROATIVAMENTE envia os REPLYs adiados para [2, 3, 5]. Só agora eles podem entrar, um por vez."

5. **SEQUÊNCIA CORRETA:**
   > "Observem: nunca dois nós estão na CS ao mesmo tempo. Primeiro Node 4, depois Node 3, depois Node 1... em ordem de prioridade."

---

## Seção 5 — Clímax: Matando o líder e reeleição Bully (7:00 – 9:00)

### O que falar:

> "Agora vou demonstrar tolerância a falhas. O líder atual é o Node 5. Vou matá-lo."

### Comando (no Terminal B):

```bash
docker stop node5
```

### O que apontar nos logs:

1. **Detecção de falha:**
   > "Olhem: 👑 [BULLY] Node X | Falha do líder (Node 5) detectada! — o heartbeat falhou e o nó percebeu."

2. **ELECTION:**
   > "O nó que detectou envia ELECTION aos de ID maior. Node 4 é o maior vivo, assume a eleição."

3. **COORDINATOR:**
   > "Node 4 anuncia: SOU O NOVO LÍDER! E todos reconhecem."

4. **Sistema continua:**
   > "Reparem que o Ricart-Agrawala continua funcionando normalmente com 4 nós. O sistema se recuperou sozinho."

### (Opcional) Restaurar o nó:

```bash
docker start node5
```

> "Se eu restauro o Node 5, na próxima eleição ele reassume como líder por ter o maior ID."

---

## Seção 6 — Conclusão (9:00 – 10:00)

### O que falar:

> "Resumindo: demonstrei um sistema distribuído com comunicação real via gRPC, onde:
> 1. O Relógio de Lamport evolui em toda mensagem, garantindo ordenação causal.
> 2. O Ricart-Agrawala garante exclusão mútua sem deadlock, usando os timestamps de Lamport como critério.
> 3. O Bully detecta falhas e reelege o líder automaticamente.
>
> Os três algoritmos trabalham em conjunto — o Lamport alimenta o Ricart-Agrawala, e o Bully garante tolerância a falhas. Obrigado."

### Comando final:

```bash
docker compose down
```

---

## Checklist pré-gravação

- [ ] Docker Desktop rodando
- [ ] Nenhum container antigo (`docker compose down`)
- [ ] Fonte do terminal grande o suficiente
- [ ] Dois terminais abertos lado a lado
- [ ] Gravação do Google Meet iniciada (compartilhar tela inteira)
- [ ] Cronômetro visível para controlar o tempo
