# Roteiro de Apresentação Completa — Trabalho 2 MC714

> **Como usar:** este roteiro intercala os **12 slides** (`apresentacao_projeto.html`) com o **hands-on no terminal** (`ROTEIRO_VIDEO.md`).
> Os blocos **"🎙️ Fala"** são escritos para serem **lidos em voz alta de forma corrida** — linguagem natural, como se você estivesse explicando para a turma, não recitando o slide.
> Marcações: 🖥️ = vá para o terminal · 📊 = slides · 🔴 AO VIVO = ação executada na hora.
> Texto entre *[colchetes em itálico]* é **indicação de cena**, não para ler.

---

## Preparação (antes de gravar)

1. **Slides** em tela cheia (`apresentacao_projeto.html`), navegação por ← →.
2. **Dois terminais** lado a lado, fonte grande:
   - **Terminal A** (principal): `docker compose`.
   - **Terminal B** (falha): `docker stop`/`start`.
3. Cluster parado: `docker compose down`.
4. Cronômetro à vista. Meta: ~10 min.

> **Lógica da apresentação:** explico cada algoritmo no slide e, logo em seguida, mostro ele *acontecendo de verdade* no terminal. A teoria (slides 1–8) vem antes do `up`; o cluster sobe enquanto narro Lamport e Ricart; o `docker stop` ao vivo cai no slide 9; os slides 10–12 fecham amarrando tudo.

---

## BLOCO 1 — Abertura e visão geral (0:00 – 1:30)

### 📊 Slide 1 (Capa)
🎙️ **Fala:**
> "Olá. Esse é o meu Trabalho 2 de MC714, Sistemas Distribuídos. A proposta aqui não foi implementar três algoritmos soltos e mostrar que cada um roda — foi montar **um sistema só**, com cinco nós conversando por rede de verdade, em que o Relógio de Lamport, a exclusão mútua de Ricart-Agrawala e a eleição de líder do Bully trabalham juntos e dependem uns dos outros. Eu vou explicar a ideia de cada um e, em seguida, mostrar tudo funcionando ao vivo num cluster Docker."

### 📊 Slide 2 (Visão Geral — 3 algoritmos)
🎙️ **Fala:**
> "Antes de entrar no código, quero deixar clara a tese do trabalho, porque é o que costura tudo. Esses três algoritmos não são independentes — eles se alimentam. O **Lamport** é a base: ele dá um carimbo de tempo lógico para toda mensagem que trafega na rede. O **Ricart-Agrawala** pega exatamente esse carimbo e usa o par tempo-mais-identificador para decidir quem tem prioridade de entrar na seção crítica — ou seja, ele só funciona porque o Lamport existe embaixo. E o **Bully** entra por cima: é ele que garante que, se o líder morrer, o sistema se reorganiza sozinho. Então a leitura correta é: Lamport ordena, Ricart-Agrawala coordena, e o Bully protege contra falha."

### 📊 Slide 3 (Stack Tecnológica)
🎙️ **Fala:**
> "Sobre as escolhas técnicas. Usei Python porque deixa a lógica dos algoritmos limpa e legível, que é o que importa num trabalho conceitual desses. Para a comunicação, usei **gRPC sobre Protocol Buffers** — e isso é proposital: o enunciado exige troca de mensagens **real**, então cada mensagem aqui é uma chamada de rede TCP de verdade, com contrato tipado no arquivo `.proto`. Nada de simular mensagem escrevendo em arquivo, em pipe ou em memória compartilhada — isso seria eliminatório. E para isolar de fato os nós, cada um roda no seu próprio contêiner Docker, com IP próprio, numa rede dedicada."

🖥️ *[transição rápida e opcional ao Terminal A, só pra dar credibilidade visual]*
```bash
ls
cat docker-compose.yml
```
> "Aqui dá pra ver: são cinco serviços, cinco processos independentes, cada um escutando gRPC na porta 50051. Não há um processo mestre orquestrando — eles são pares conversando entre si."

---

## BLOCO 2 — Teoria dos algoritmos (1:30 – 3:30)

> Fique nos slides. Aqui você "ensina" o espectador para que, na hora dos logs, ele já entenda o que está vendo.

### 📊 Slide 4 (Lamport)
🎙️ **Fala:**
> "Começando pelo Relógio de Lamport. O problema que ele resolve é simples de enunciar e profundo na prática: num sistema distribuído **não existe relógio físico confiável e sincronizado** entre as máquinas. Então a gente abandona a ideia de tempo real e usa um contador lógico que respeita só uma coisa — a **causalidade**. A implementação tem duas operações. A primeira é o `tick`: sempre que eu vou **enviar** uma mensagem, eu incremento meu contador antes. A segunda é o `update`: quando eu **recebo** uma mensagem, eu pego o maior valor entre o meu relógio e o que veio na mensagem, e somo um. Esse `max` mais um é a alma do algoritmo, porque ele garante que se um evento A causou o evento B, então o tempo de A é sempre menor que o de B. O receptor **nunca** consegue ficar 'atrás' de quem mandou a mensagem. Um detalhe de implementação que eu cuidei: o contador é protegido por um lock, mas eu emito o log **fora** do lock, pra não segurar a região crítica fazendo escrita de tela."

### 📊 Slide 5 (Ricart-Agrawala)
🎙️ **Fala:**
> "Com o Lamport pronto, dá pra construir a exclusão mútua. O objetivo do Ricart-Agrawala é clássico: garantir que **só um nó por vez** entre na seção crítica, mas **sem nenhum coordenador central** — porque um coordenador central seria um ponto único de falha, justamente o que a gente quer evitar. O mecanismo é o seguinte: quando eu quero entrar, eu peço permissão a todos os outros e só entro quando os N menos um responderem. A pergunta interessante é: quando é que eu, ao receber um pedido de outro nó, **adio** a resposta dele em vez de liberar na hora? A regra é: eu seguro o REPLY se eu já estou dentro da seção crítica, ou se eu também quero entrar e o meu par tempo-identificador é menor que o dele. Ou seja, **timestamp menor ganha**, e quando dá empate de timestamp o identificador menor desempata. Isso transforma uma ordem que seria parcial numa **ordem total determinística** — todo mundo concorda na mesma fila, sem precisar conversar sobre isso."

### 📊 Slide 6 (Comunicação gRPC — Fire-and-Forget)
🎙️ **Fala:**
> "Agora um ponto que eu considero o mais sutil do trabalho, e que muita implementação ingênua erra. O gRPC atende cada chamada numa thread de um pool. Se o meu `RequestAccess` ficasse **bloqueado** esperando a seção crítica liberar para só então responder, eu estaria segurando uma thread do pool durante todo o tempo da seção crítica. Com vários nós pedindo ao mesmo tempo, o pool esgota e o sistema trava — um **deadlock distribuído**. A solução que eu adotei é desacoplar: REQUEST e REPLY são duas chamadas **separadas**. Quando chega um pedido, o handler só registra esse pedido numa estrutura e devolve um Ack imediato, liberando a thread na hora. O REPLY de verdade só é enviado depois, quando eu saio da seção crítica — e aí eu disparo os REPLYs adiados de forma **proativa**, numa thread minha. Em uma frase: ninguém fica esperando pendurado numa chamada de rede."

### 📊 Slide 7 (Concorrência / Thread-Safety)
🎙️ **Fala:**
> "E como tudo isso roda concorrente, eu precisei tratar a sincronização com cuidado. O pool do gRPC tem vinte workers, então é perfeitamente possível duas mensagens chegarem ao mesmo tempo e quererem mexer no mesmo estado. Cada módulo tem o seu próprio lock protegendo o que é dele: o Lamport protege o contador, o Ricart-Agrawala protege de uma vez o estado, o timestamp do pedido e a fila de adiados, e o Bully protege quem é o líder e a flag de eleição em andamento. O ponto fino é a transição de 'querendo' para 'dentro da seção crítica': ela é **atômica**, acontece toda dentro de um lock, justamente pra não existir aquela janela onde eu acho que já posso entrar mas o estado ainda não foi atualizado. O resultado disso é que eu rodei o sistema repetidas vezes sem nenhum deadlock e sem nenhuma condição de corrida."

### 📊 Slide 8 (Bully)
🎙️ **Fala:**
> "Fechando a teoria, o algoritmo de eleição, o Bully. O nome já diz: 'ganha o mais forte', e aqui força é o **maior identificador**. A dinâmica é: quando eu percebo, por heartbeat, que o líder caiu, eu mando uma mensagem de ELECTION para todos os nós com identificador maior que o meu. Se algum deles responde, eu recuo — penso 'tem gente mais forte viva, deixo com eles'. Se **ninguém** maior responde, então o mais forte vivo sou eu, e eu me anuncio como líder mandando COORDINATOR pra todo mundo. E aqui tem uma decisão de implementação que eu gosto de destacar, porque mostra economia: eu **não criei** uma mensagem separada de 'OK'. O próprio sucesso da chamada gRPC — o Ack — já me diz que o nó maior está vivo e assumiu. Então eu reaproveito a semântica do protocolo em vez de inventar tráfego extra."

---

## BLOCO 3 — DEMO: subindo o cluster + eleição inicial (3:30 – 5:00)

### 🖥️ Terminal A — execute:
```bash
docker compose up --build
```
> *[Deixe os slides na lateral ou volte ao slide 8 — a teoria de Bully casa com o que vai aparecer.]*

🎙️ **Fala** *[enquanto os logs sobem]*:
> "Pronto, estou subindo os cinco nós ao mesmo tempo. Reparem que ninguém nasce sabendo quem são os vizinhos — então a primeira coisa que cada nó faz é uma fase de **descoberta**."

**1. Discovery** — aponte para `📡 [NET]`:
> "São essas linhas de NET. Cada nó fica pingando os outros até confirmar que todos estão de pé — vejam o contador subindo, 'um de quatro prontos', 'dois de quatro', até 'todos os quatro peers prontos'. Só depois disso ele começa a participar de verdade."

**2. Eleição Bully inicial** — aponte para `👑 [BULLY]`:
> "Assim que ficam prontos, eles já disparam uma eleição pra decidir o líder. E acontece exatamente o que a teoria previu: os nós menores mandam ELECTION pros maiores, e o Node 5, que tem o maior identificador, não encontra ninguém acima dele. Olhem a linha dele: **'sou o novo líder, anunciando COORDINATOR para um, dois, três e quatro'**."

**3. COORDINATOR aceito:**
> "E todos os outros reconhecem: 'reconhece Node 5 como o novo líder'. Em poucos décimos de segundo o cluster convergiu para um líder, sem nenhuma configuração manual."

**4. ⚠️ Antecipando a dúvida da redundância** *[fale isso ANTES que percebam, mostra domínio]*:
> "E eu quero me adiantar a uma coisa que vocês vão notar: o Node 5 se declara líder **mais de uma vez** nos logs. Isso é proposital e é correto. Como cada nó roda uma eleição de validação no momento em que entra no cluster, e eles entram com pequenos atrasos diferentes, a eleição acaba rodando algumas vezes nesses primeiros segundos. O importante é que ela é **idempotente**: não importa quantas vezes rode, o resultado converge sempre pro mesmo nó, o de maior identificador vivo. Então não é instabilidade, é o algoritmo se confirmando."

---

## BLOCO 4 — DEMO: Relógio de Lamport ao vivo (5:00 – 5:45)

### 📊 Volte ao Slide 4 por uns segundos, depois 🖥️ Terminal A.

🎙️ **Fala** — aponte para `🟢 [LAMPORT]`:
> "Agora repare numa coisa que está acontecendo o tempo todo, em segundo plano: o relógio de Lamport evoluindo a cada mensagem. Essas linhas verdes são os saltos do contador. E eu quero mostrar um caso bem ilustrativo: quando o Node 2 termina de inicializar, ele já está com o relógio adiantado, e ao falar com os outros ele 'puxa' todo mundo pra frente. Vejam:"

- `Node 1 | Clock atualizado: 8 -> 16 (via msg de Node 2)`
- `Node 3 | Clock atualizado: 8 -> 17 (via msg de Node 2)`
- `Node 5 | Clock atualizado: 10 -> 19 (via msg de Node 2)`

> "O Node 1 estava em oito e saltou direto pra dezesseis ao receber a mensagem. Ele não foi de oito pra nove — ele pulou pro máximo entre o dele e o que recebeu, mais um. É a causalidade na prática: o receptor se reposiciona pra nunca parecer que aconteceu antes de quem mandou a mensagem."

---

## BLOCO 5 — DEMO: Exclusão mútua Ricart-Agrawala (5:45 – 7:30)

> **Coração da apresentação.** Vá devagar, é aqui que você prova que entende mesmo.

### 📊 Tenha o Slide 5 ou o Slide 11 à mão; 🖥️ foco no Terminal A.

🎙️ **Fala** — aponte conforme cada linha aparece:

**1. REQUEST** (`🟡 [RICART]`):
> "Agora vamos ver a exclusão mútua em ação, que é a parte mais bonita. O Node 1 resolve entrar na seção crítica — essa linha amarela: 'solicitando seção crítica, Lamport setenta e oito, aguardando quatro REPLYs'. Ele mandou o pedido pros quatro vizinhos e agora espera a permissão de todos."

**2. Concessão imediata** (`🟢 [RICART]`):
> "Como nesse instante ninguém mais quer entrar, todos liberam na hora — 'concedendo permissão ao Node 1 imediatamente, estado RELEASED'. Ele junta as quatro permissões e entra: 'entrou na seção crítica'."

**3. O ADIAMENTO — o momento-chave** (`🔴 [RICART]`):
> "E agora vem o que eu mais queria mostrar. Enquanto o Node 1 está lá dentro trabalhando, o Node 5 e o Node 2 também resolvem pedir a seção crítica. Olhem a decisão do Node 1:"
- `🔴 Node 1 | Pedido do Node 5 ADIADO (minha prioridade: (ts=78,id=1) < (ts=96,id=5))`
- `🔴 Node 1 | Pedido do Node 2 ADIADO (minha prioridade: (ts=78,id=1) < (ts=100,id=2))`
> "Ele compara os pares: o dele é tempo setenta e oito, o do Node 5 é noventa e seis. Setenta e oito é menor, então o Node 1 tem prioridade e **segura** os REPLYs — não nega, apenas adia. E aqui tem um detalhe lindo que prova que não existe coordenador: o **próprio Node 5**, antes mesmo de entrar, já adia o Node 2, porque noventa e seis é menor que cem. Cada nó, sozinho, comparando só os timestamps, chega à mesma fila. A ordem emerge naturalmente."

**4. SAÍDA + REPLY proativo** (`🔵 [RICART]`):
> "Quando o Node 1 termina, ele sai e **proativamente** libera quem ele tinha adiado — essa linha azul: 'saiu da seção crítica, enviando REPLY adiado para dois e cinco'. Só nesse momento o próximo da fila consegue entrar."

**5. A SEQUÊNCIA — frase de fechamento** *[diga com calma, é o seu ponto alto]*:
> "E agora juntem tudo e acompanhem a ordem em que os nós entraram na seção crítica: primeiro o um, depois o cinco, depois o dois, o três e o quatro. Compare com os timestamps deles: setenta e oito, noventa e seis, cem, cento e quatro, cento e nove. É **exatamente** a ordem crescente dos relógios de Lamport. Em nenhum instante dois nós estiveram dentro ao mesmo tempo. Ou seja: cinco processos independentes, sem nenhum chefe, conseguiram serializar perfeitamente o acesso a um recurso usando apenas relógios lógicos. Isso é o Ricart-Agrawala fazendo jus à teoria."

---

## BLOCO 6 — CLÍMAX: matando o líder e reeleição Bully (7:30 – 9:00)

### 📊 Slide 9 (Tolerância a Falhas) — abra ANTES de matar o nó.
🎙️ **Fala:**
> "Até aqui mostrei o sistema funcionando no caso feliz. Mas sistema distribuído de verdade tem que sobreviver a falha — então agora eu vou **quebrar** o sistema de propósito. Cada nó tem uma thread que fica pingando o líder a cada dois segundos por heartbeat. O líder atual é o Node 5. Eu vou simplesmente matar o contêiner dele, sem aviso, como se a máquina tivesse caído, e a gente vai ver se o cluster se recupera sozinho."

### 🖥️ 🔴 AO VIVO — Terminal B:
```bash
docker stop node5
```

🎙️ **Fala** — aponte no Terminal A conforme aparece:
> "Pronto, o líder está morto. Vamos contar uns segundinhos..."

**1. Detecção** (`👑 [BULLY]`):
> "Aí está: 'falha do líder Node 5 detectada'. O heartbeat estourou o timeout e o nó percebeu sozinho que o chefe sumiu."

**2. ELECTION:**
> "Quem detectou imediatamente dispara uma eleição, mandando ELECTION pros de identificador maior. Como o Node 5 morreu, o maior **vivo** agora é o Node 4, e é ele quem assume a disputa."

**3. COORDINATOR:**
> "E olhem: 'Node 4, sou o novo líder', e todos os outros passam a reconhecer o quatro. O sistema reorganizou a liderança sozinho, sem ninguém intervir."

**4. Continuidade** *[esse é o argumento que fecha a robustez]*:
> "E o detalhe que fecha o raciocínio: reparem que a exclusão mútua **não parou**. O Ricart-Agrawala segue funcionando normalmente, agora com quatro nós em vez de cinco. A morte do líder não derrubou o serviço — afinal, no Ricart-Agrawala não existe um chefe pra coordenar a seção crítica. O líder serve para outras funções; a exclusão mútua é descentralizada por natureza. Isso é tolerância a falha de verdade."

### 🖥️ (Opcional) Restaurar — Terminal B:
```bash
docker start node5
```
> "E pra fechar o ciclo: se eu trouxer o Node 5 de volta, na próxima eleição ele reassume a liderança, porque continua sendo o maior identificador. O sistema acomoda tanto a saída quanto o retorno de um nó."

---

## BLOCO 7 — Infraestrutura e prova nos logs (9:00 – 9:45)

### 📊 Slide 10 (Docker Compose)
🎙️ **Fala:**
> "Vale mostrar rapidamente como isso tudo está empacotado. São cinco contêineres numa única rede bridge, todos na porta 50051, e — repito, porque é requisito — **zero simulação**: cada caixinha dessas é um processo de verdade, com IP de verdade, conversando por rede. Cada nó recebe só o seu identificador e a lista de vizinhos por variável de ambiente, então o mesmo código sobe os cinco, mudando apenas a configuração."

🖥️ *[opcional]* `cat docker-compose.yml` rápido pra evidenciar os cinco serviços.

### 📊 Slide 11 (Resultados / Logs Didáticos)
🎙️ **Fala** *[amarrando com o que acabaram de ver]*:
> "E essa é a legenda dos logs que a gente acompanhou ao vivo — eu fiz questão de instrumentar cada evento com um emoji e uma cor por nó, justamente pra ficar didático na hora de demonstrar. Verde é salto do relógio de Lamport; amarelo é alguém pedindo a seção crítica; vermelho é um pedido sendo adiado por prioridade; o check verde é entrada na seção crítica; o azul é a saída liberando os adiados; e a coroa é a eleição. Tudo que eu narrei está nessas marcações, em tempo real."

---

## BLOCO 8 — Conclusão (9:45 – 10:00)

### 📊 Slide 12 (Conclusão)
🎙️ **Fala:**
> "Então, pra fechar e amarrar a tese do começo: eu não mostrei três algoritmos isolados, mostrei um sistema integrado. O Lamport deu a ordem causal que serviu de critério pro Ricart-Agrawala garantir exclusão mútua **sem coordenador e sem deadlock** — e o deadlock foi evitado por uma decisão consciente de separar REQUEST de REPLY. Por cima disso, o Bully deu tolerância a falha, detectando e reelegendo o líder em poucos segundos. E tudo sobre comunicação real, gRPC e TCP, entre contêineres isolados. Os três conceitos da disciplina conversando como um organismo só. Era isso que eu queria demonstrar. Muito obrigado, e fico à disposição pra perguntas."

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
