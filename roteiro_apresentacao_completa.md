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
> "Oi, pessoal. Esse é o meu Trabalho 2 de MC714, de Sistemas Distribuídos.
>
> A ideia aqui não foi pegar três algoritmos separados e mostrar cada um rodando sozinho. Foi montar um sistema único, com cinco nós que conversam entre si pela rede, onde o relógio de Lamport, a exclusão mútua do Ricart-Agrawala e a eleição de líder do Bully funcionam juntos e um depende do outro.
>
> Então eu vou explicar a ideia de cada um e, logo em seguida, mostrar tudo rodando de verdade num cluster Docker."

### 📊 Slide 2 (Visão Geral — 3 algoritmos)
🎙️ **Fala:**
> "Antes de ir pro código, eu queria deixar claro o fio condutor do trabalho, porque é o que conecta tudo. Esses três algoritmos não são independentes — um apoia o outro.
>
> O Lamport é a base de tudo: ele coloca um carimbo de tempo em toda mensagem que circula na rede.
>
> O Ricart-Agrawala usa justamente esse carimbo, o par tempo e identificador, pra decidir quem tem a vez de entrar na seção crítica. Ou seja, ele só consegue funcionar porque tem o Lamport embaixo.
>
> E o Bully fica por cima de tudo, cuidando pra que, se o líder cair, o sistema se reorganize sozinho.
>
> Então dá pra resumir assim: o Lamport ordena, o Ricart-Agrawala coordena, e o Bully protege contra falha."

### 📊 Slide 3 (Stack Tecnológica)
🎙️ **Fala:**
> "Sobre as escolhas de tecnologia. Eu usei Python porque ele deixa a lógica dos algoritmos bem fácil de ler, que é o que importa num trabalho como esse, mais conceitual.
>
> Pra comunicação eu usei gRPC com Protocol Buffers, e isso foi de propósito: o enunciado pede que a troca de mensagens seja real. Então cada mensagem aqui é uma chamada de rede de verdade, por TCP, com o contrato definido no arquivo .proto.
>
> Nada de fingir que mandou mensagem escrevendo num arquivo ou em memória compartilhada — isso aí seria motivo de zerar o trabalho.
>
> E pra separar mesmo os nós, cada um roda no seu próprio contêiner Docker, com IP próprio, na mesma rede."

🖥️ *[transição rápida e opcional ao Terminal A, só pra dar credibilidade visual]*
```bash
ls
cat docker-compose.yml
```
> "Aqui dá pra ver: são cinco serviços, cinco processos separados, cada um escutando gRPC na porta 50051. Não tem um processo central mandando nos outros — são todos iguais, conversando um com o outro."

---

## BLOCO 2 — Teoria dos algoritmos (1:30 – 3:30)

> Fique nos slides. Aqui você "ensina" o espectador para que, na hora dos logs, ele já entenda o que está vendo.

### 📊 Slide 4 (Lamport)
🎙️ **Fala:**
> "Começando pelo relógio de Lamport. O problema que ele resolve é o seguinte: num sistema distribuído a gente não pode confiar no relógio físico de cada máquina, porque eles nunca estão certinhos um com o outro.
>
> Então a gente larga mão de medir tempo real e usa um contador lógico, que se preocupa com uma coisa só: a ordem de causa e efeito entre os eventos.
>
> Na prática são duas operações. Uma é o `tick`: toda vez que eu vou mandar uma mensagem, eu incremento meu contador antes de enviar. A outra é o `update`: quando eu recebo uma mensagem, eu olho o meu relógio e o número que veio junto, pego o maior dos dois e somo um.
>
> É esse `max` mais um que faz a mágica, porque garante uma coisa: se um evento causou outro, o primeiro sempre vai ter um número menor. Quem recebe nunca fica com o relógio atrasado em relação a quem mandou.
>
> E um cuidado que eu tive na implementação: o contador fica protegido por um lock, mas eu imprimo o log fora do lock, pra não travar os outros nós só por causa de uma escrita na tela."

### 📊 Slide 5 (Ricart-Agrawala)
🎙️ **Fala:**
> "Com o Lamport funcionando, dá pra montar a exclusão mútua em cima dele. O que o Ricart-Agrawala quer garantir é que só um nó por vez entre na seção crítica, mas sem ninguém centralizando isso.
>
> Porque se tivesse um nó coordenando, ele viraria um ponto fraco: caiu ele, parou tudo. E é exatamente isso que a gente quer evitar.
>
> O jeito que funciona é: quando eu quero entrar, eu peço permissão pra todo mundo e só entro quando todos os outros responderem.
>
> A parte interessante é decidir quando eu, ao receber o pedido de outro nó, respondo na hora e quando eu seguro a resposta. A regra é simples: eu seguro a resposta se eu já estou dentro da seção crítica, ou se eu também quero entrar e o meu par de tempo e identificador é menor que o dele.
>
> Resumindo: quem tem o tempo menor passa na frente, e se der empate no tempo, o identificador menor desempata. Isso dá uma ordem única e previsível — todo mundo concorda em qual é a fila, sem precisar combinar nada."

### 📊 Slide 6 (Comunicação gRPC — Fire-and-Forget)
🎙️ **Fala:**
> "Agora vem uma parte que eu acho a mais difícil de acertar, e que é fácil de errar se a gente faz do jeito mais óbvio.
>
> O gRPC atende cada chamada usando uma thread de um conjunto limitado. Se o meu pedido de acesso ficasse parado esperando a seção crítica liberar pra só então responder, eu estaria prendendo uma dessas threads o tempo todo que o outro nó estivesse lá dentro. Aí, com vários nós pedindo ao mesmo tempo, essas threads acabam, e o sistema inteiro trava.
>
> Pra evitar isso, eu separei as coisas: o pedido e a resposta são duas chamadas diferentes. Quando chega um pedido, eu só anoto que aquele nó está querendo e respondo na hora um 'recebi', liberando a thread na mesma hora.
>
> A resposta de verdade, dando a permissão, sai só depois, quando eu termino e saio da seção crítica — e aí eu mesmo mando as respostas que estavam guardadas.
>
> Resumindo: ninguém fica pendurado esperando numa chamada de rede."

### 📊 Slide 7 (Concorrência / Thread-Safety)
🎙️ **Fala:**
> "E como tudo isso acontece ao mesmo tempo, eu tive que tomar cuidado com a sincronização. O gRPC trabalha com vinte threads, então pode muito bem acontecer de duas mensagens chegarem juntas e quererem mexer na mesma informação ao mesmo tempo.
>
> Pra isso cada parte tem o seu próprio cadeado protegendo o que é dela: o Lamport protege o contador; o Ricart-Agrawala protege o estado, o tempo do pedido e a lista de respostas guardadas; e o Bully protege quem é o líder e se tem uma eleição rolando.
>
> O ponto que exige mais atenção é a passagem de 'eu quero entrar' pra 'eu estou dentro': isso tem que acontecer tudo de uma vez, sem brecha. Senão pode aparecer aquele instante perigoso em que eu acho que já posso entrar mas a informação ainda não foi atualizada.
>
> Na prática, eu rodei o sistema várias vezes e nunca deu trava nem comportamento errado por causa de concorrência."

### 📊 Slide 8 (Bully)
🎙️ **Fala:**
> "Pra fechar a teoria, o algoritmo de eleição, o Bully. O nome já entrega a ideia: ganha o maior, e aqui maior é quem tem o maior identificador.
>
> Funciona assim: quando eu percebo, pelo heartbeat, que o líder caiu, eu mando uma mensagem de eleição pra todos os nós com identificador maior que o meu.
>
> Se algum deles responder, eu fico na minha — quer dizer que tem alguém maior vivo, então deixo com ele. Mas se ninguém maior responder, então o maior que sobrou sou eu, e eu me anuncio como líder mandando um aviso pra todo mundo.
>
> E tem uma escolha que eu fiz aqui que eu acho que vale comentar, porque deixou o sistema mais enxuto: eu não criei uma mensagem só pra dizer 'ok, recebi sua eleição'. O próprio fato da chamada gRPC ter dado certo já me diz que aquele nó maior está vivo e vai assumir. Então eu aproveitei isso, em vez de mandar uma mensagem a mais só pra confirmar."

---

## BLOCO 3 — DEMO: subindo o cluster + eleição inicial (3:30 – 5:00)

### 🖥️ Terminal A — execute:
```bash
docker compose up --build
```
> *[Deixe os slides na lateral ou volte ao slide 8 — a teoria de Bully casa com o que vai aparecer.]*

🎙️ **Fala** *[enquanto os logs sobem]*:
> "Pronto, estou subindo os cinco nós de uma vez. E repara que nenhum deles nasce sabendo quem são os vizinhos. Então a primeira coisa que cada um faz é se apresentar e procurar os outros."

**1. Discovery** — aponte para `📡 [NET]`:
> "São essas linhas de NET aqui. Cada nó fica chamando os outros até confirmar que todo mundo está de pé — dá pra ver o contador subindo, 'um de quatro prontos', 'dois de quatro', até 'todos os quatro prontos'. Só depois disso ele começa a participar pra valer."

**2. Eleição Bully inicial** — aponte para `👑 [BULLY]`:
> "Assim que ficam prontos, eles já fazem uma eleição pra escolher o líder. E aconteceu certinho o que a teoria diz: os nós menores mandam a eleição pros maiores, e o Node 5, que tem o maior número, não acha ninguém acima dele. Olha a linha dele aqui: 'sou o novo líder, avisando todo mundo, do um ao quatro'."

**3. COORDINATOR aceito:**
> "E os outros todos aceitam: 'reconhece o Node 5 como líder'. Em uma fração de segundo o cluster já escolheu um líder, sem eu ter configurado nada na mão."

**4. ⚠️ Antecipando a dúvida da redundância** *[fale isso ANTES que percebam, mostra domínio]*:
> "E eu queria já adiantar uma coisa que vocês vão reparar: o Node 5 aparece se declarando líder mais de uma vez aqui nos logs. Isso é esperado e está certo.
>
> Como cada nó faz uma eleição na hora que entra no cluster, e eles entram com uns segundinhos de diferença, a eleição acaba acontecendo algumas vezes nesse comecinho.
>
> O que importa é que o resultado é sempre o mesmo: não importa quantas vezes rode, sempre converge pro nó de maior número que estiver vivo. Então não é o sistema instável, é ele se confirmando."

---

## BLOCO 4 — DEMO: Relógio de Lamport ao vivo (5:00 – 5:45)

### 📊 Volte ao Slide 4 por uns segundos, depois 🖥️ Terminal A.

🎙️ **Fala** — aponte para `🟢 [LAMPORT]`:
> "Agora olha uma coisa que está rolando o tempo todo, meio que no fundo: o relógio de Lamport mexendo a cada mensagem. Essas linhas verdes aqui são os saltos do contador. E eu queria mostrar um exemplo bem claro: quando o Node 2 termina de subir, ele já está com o relógio mais alto, e quando ele fala com os outros, ele acaba puxando todo mundo pra frente. Olha só:"

- `Node 1 | Clock atualizado: 8 -> 16 (via msg de Node 2)`
- `Node 3 | Clock atualizado: 8 -> 17 (via msg de Node 2)`
- `Node 5 | Clock atualizado: 10 -> 19 (via msg de Node 2)`

> "O Node 1 estava no oito e pulou direto pro dezesseis quando recebeu a mensagem. Ele não foi do oito pro nove — ele pegou o maior valor entre o dele e o que chegou, e somou um. É a tal da causalidade acontecendo: quem recebe se ajusta pra nunca parecer que aconteceu antes de quem mandou."

---

## BLOCO 5 — DEMO: Exclusão mútua Ricart-Agrawala (5:45 – 7:30)

> **Coração da apresentação.** Vá devagar, é aqui que você prova que entende mesmo.

### 📊 Tenha o Slide 5 ou o Slide 11 à mão; 🖥️ foco no Terminal A.

🎙️ **Fala** — aponte conforme cada linha aparece:

**1. REQUEST** (`🟡 [RICART]`):
> "Agora vamos ver a exclusão mútua acontecendo, que pra mim é a parte mais legal. O Node 1 resolve entrar na seção crítica — é essa linha amarela: 'pedindo a seção crítica, Lamport setenta e oito, esperando quatro respostas'. Ele mandou o pedido pros quatro vizinhos e agora fica esperando a permissão de todo mundo."

**2. Concessão imediata** (`🟢 [RICART]`):
> "Como nesse momento ninguém mais quer entrar, todos liberam na hora — 'liberando o Node 1 na hora'. Ele junta as quatro permissões e entra: 'entrou na seção crítica'."

**3. O ADIAMENTO — o momento-chave** (`🔴 [RICART]`):
> "E agora vem a parte que eu mais queria mostrar. Enquanto o Node 1 está lá dentro trabalhando, o Node 5 e o Node 2 também resolvem pedir a seção crítica. Olha o que o Node 1 faz:"
- `🔴 Node 1 | Pedido do Node 5 ADIADO (minha prioridade: (ts=78,id=1) < (ts=96,id=5))`
- `🔴 Node 1 | Pedido do Node 2 ADIADO (minha prioridade: (ts=78,id=1) < (ts=100,id=2))`
> "Ele compara: o tempo dele é setenta e oito, o do Node 5 é noventa e seis. Setenta e oito é menor, então o Node 1 tem a vez e segura a resposta — repara que ele não nega, ele só guarda pra responder depois.
>
> E olha que coisa boa, que prova que não tem ninguém centralizando: o próprio Node 5, antes mesmo de entrar, já guarda o pedido do Node 2, porque noventa e seis é menor que cem.
>
> Cada nó, sozinho, comparando só os tempos, chega na mesma fila. A ordem aparece sozinha."

**4. SAÍDA + REPLY proativo** (`🔵 [RICART]`):
> "Quando o Node 1 termina, ele sai e já manda na hora a resposta pra quem ele tinha deixado esperando — essa linha azul: 'saiu da seção crítica, mandando a resposta guardada pro dois e pro cinco'. É só nesse momento que o próximo da fila consegue entrar."

**5. A SEQUÊNCIA — frase de fechamento** *[diga com calma, é o seu ponto alto]*:
> "E agora junta tudo e acompanha a ordem em que os nós entraram na seção crítica: primeiro o um, depois o cinco, depois o dois, o três e o quatro.
>
> Compara com os tempos de cada um: setenta e oito, noventa e seis, cem, cento e quatro, cento e nove. É exatamente a ordem crescente dos relógios de Lamport.
>
> E, em nenhum momento, dois nós estiveram dentro ao mesmo tempo.
>
> Ou seja: cinco processos separados, sem nenhum chefe, conseguiram organizar perfeitamente quem usa o recurso e quando, usando só os relógios lógicos. É o Ricart-Agrawala funcionando direitinho como a teoria diz."

---

## BLOCO 6 — CLÍMAX: matando o líder e reeleição Bully (7:30 – 9:00)

### 📊 Slide 9 (Tolerância a Falhas) — abra ANTES de matar o nó.
🎙️ **Fala:**
> "Até aqui eu mostrei o sistema funcionando quando tá tudo bem. Mas um sistema distribuído de verdade precisa aguentar uma falha — então agora eu vou quebrar ele de propósito.
>
> Cada nó tem uma parte que fica checando o líder a cada dois segundos, pra ver se ele ainda está vivo. O líder agora é o Node 5.
>
> Eu vou simplesmente derrubar o contêiner dele, do nada, como se a máquina tivesse caído, e a gente vê se o cluster se vira sozinho."

### 🖥️ 🔴 AO VIVO — Terminal B:
```bash
docker stop node5
```

🎙️ **Fala** — aponte no Terminal A conforme aparece:
> "Pronto, derrubei o líder. Vamos esperar uns segundinhos..."

**1. Detecção** (`👑 [BULLY]`):
> "Olha aí: 'falha do líder Node 5 detectada'. A checagem não recebeu resposta a tempo e o nó percebeu sozinho que o líder sumiu."

**2. ELECTION:**
> "Quem percebeu já começa uma eleição na hora, chamando os nós de número maior. Como o Node 5 caiu, o maior que sobrou vivo é o Node 4, e é ele quem toma a frente."

**3. COORDINATOR:**
> "E olha: 'Node 4, sou o novo líder', e todos os outros passam a reconhecer ele. O sistema escolheu um novo líder sozinho, sem eu fazer nada."

**4. Continuidade** *[esse é o argumento que fecha a robustez]*:
> "E o que fecha bem o raciocínio: repara que a exclusão mútua não parou. O Ricart-Agrawala continua rodando normal, só que agora com quatro nós em vez de cinco.
>
> Perder o líder não derrubou o serviço — e isso faz sentido, porque no Ricart-Agrawala não tem um chefe coordenando a seção crítica mesmo. O líder serve pra outras coisas; o controle de quem entra na seção crítica já é distribuído por natureza.
>
> Isso é tolerância a falha de verdade."

### 🖥️ (Opcional) Restaurar — Terminal B:
```bash
docker start node5
```
> "E pra fechar o ciclo: se eu trouxer o Node 5 de volta, na próxima eleição ele volta a ser o líder, porque continua sendo o de maior número. Então o sistema lida bem tanto com um nó saindo quanto com ele voltando."

---

## BLOCO 7 — Infraestrutura e prova nos logs (9:00 – 9:45)

### 📊 Slide 10 (Docker Compose)
🎙️ **Fala:**
> "Vale mostrar rapidinho como tudo isso fica montado. São cinco contêineres numa rede só, todos na porta 50051, e — falando de novo, porque é exigência do trabalho — nada de simulação: cada uma dessas caixinhas é um processo de verdade, com IP de verdade, conversando pela rede. Cada nó recebe só o seu número e a lista dos vizinhos por configuração, então é o mesmo código subindo os cinco, mudando só esses ajustes."

🖥️ *[opcional]* `cat docker-compose.yml` rápido pra mostrar os cinco serviços.

### 📊 Slide 11 (Resultados / Logs Didáticos)
🎙️ **Fala** *[amarrando com o que acabaram de ver]*:
> "E essa aqui é a legenda dos logs que a gente acabou de acompanhar ao vivo. Eu fiz questão de marcar cada evento com um emoji e dar uma cor pra cada nó, justamente pra facilitar na hora de mostrar.
>
> Verde é o relógio de Lamport saltando; amarelo é alguém pedindo a seção crítica; vermelho é um pedido ficando pra depois por causa da prioridade; o certinho verde é entrar na seção crítica; o azul é sair e liberar quem estava esperando; e a coroa é a eleição.
>
> Tudo que eu fui falando está nessas marcações, em tempo real."

---

## BLOCO 8 — Conclusão (9:45 – 10:00)

### 📊 Slide 12 (Conclusão)
🎙️ **Fala:**
> "Então, pra fechar e voltar na ideia do começo: eu não mostrei três algoritmos soltos, eu mostrei um sistema integrado.
>
> O Lamport deu a ordem que o Ricart-Agrawala usou pra garantir que só um nó por vez entra na seção crítica, sem ninguém centralizando e sem travar — e essa trava eu evitei de propósito, separando o pedido da resposta.
>
> Em cima disso, o Bully cuidou da tolerância a falha, percebendo a queda do líder e escolhendo outro em poucos segundos.
>
> E tudo isso com comunicação de verdade, gRPC e TCP, entre contêineres separados. Os três assuntos da matéria funcionando juntos, como uma coisa só.
>
> Era isso que eu queria mostrar. Muito obrigado, e estou à disposição pra perguntas."

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
