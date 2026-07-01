# Roteiro de Apresentação Completa — Trabalho 2 MC714

> **Como usar:** este roteiro intercala os **12 slides** (`apresentacao_projeto.html`) com o **hands-on no PAINEL VISUAL** (`http://localhost:8080`).
> Os blocos **"🎙️ Fala"** são escritos para serem **lidos em voz alta de forma corrida** — linguagem natural, como se você estivesse explicando para a turma, não recitando o slide.
> Marcações: 🖥️ = vá para o **dashboard** · 📊 = slides · 🔴 AO VIVO = ação executada na hora (clicar num botão do painel).
> Texto entre *[colchetes em itálico]* é **indicação de cena**, não para ler.

> **O que mudou (por que o painel):** antes tudo era log rolando no terminal e ficava difícil ver os três algoritmos ao mesmo tempo. Agora tem um **painel visual em rede** onde dá pra *enxergar* o sistema funcionando: os cinco nós desenhados num pentágono, com as **mensagens voando entre eles** em tempo real, coloridas por tipo (amarelo = REQUEST, verde = REPLY, roxo = ELECTION, laranja = COORDINATOR, cinza = heartbeat ida e volta). O número do relógio de Lamport de cada nó só sobe **no instante em que a bolinha pousa nele** — a animação e o relógio ficam perfeitamente sincronizados. Cada nó mostra seu relógio de Lamport, fica com anel verde brilhando quando entra na região crítica e ganha uma coroa quando é o líder. Embaixo, um painel de logs colorido pra você narrar. **Você dispara tudo pela UI** — eleição, matar nó, pedir região crítica — sem decorar comando.

---

## Preparação (antes de gravar)

1. **Slides** em tela cheia (`apresentacao_projeto.html`), navegação por ← →.
2. **Sobe o cluster** e **abre o painel** (só isso — sem dois terminais):
   ```bash
   docker compose up --build      # sobe os 5 nós + o dashboard
   ```
   Depois abra **http://localhost:8080** no navegador.
3. Layout de gravação sugerido: **slides em uma metade da tela, o painel na outra**. Um terminal pequeno atrás é opcional (só se quiser mostrar os logs "crus" em algum momento).
4. Antes de começar, garanta cluster limpo: `docker compose down`.
5. Cronômetro à vista. Meta: ~10 min.

> **Lógica da apresentação:** explico cada algoritmo no slide e, logo em seguida, mostro ele *acontecendo de verdade* no painel. A teoria (slides 1–8) vem antes do `up`; o cluster sobe e o painel ganha vida enquanto narro Lamport e Ricart; o **botão "Matar" no líder** cai no slide 9; os slides 10–12 fecham amarrando tudo.
>
> **Controles do painel:** abaixo do grafo há uma barra com os cinco nós, cada um com três botões — **⚡ Eleição** (dispara uma eleição Bully a partir daquele nó), **💀 Matar / ♻️ Reviver** (simula a queda do nó — os outros detectam e reelegem), **🔓 Pedir RC** (faz o nó pedir a região crítica). Em cima, o painel **"Região Crítica"** mostra quem está dentro — a prova visual da exclusão mútua. Há também um toggle **"mostrar heartbeats"**: deixe ligado pra mostrar o sistema "respirando", ou desligue pra limpar a tela e focar só no algoritmo do momento.
>
> **⏸️ Botão Pausar (seu melhor amigo na gravação):** congela a simulação **de verdade** — não é só a tela. Cada nó para seus loops de fundo, então o tempo e os relógios de Lamport param de avançar e os pacotes ficam parados no ar. Use sempre que quiser explicar com calma sem que nada continue mudando. Clique em **▶️ Continuar** e tudo retoma do ponto exato — nenhum tempo passou durante a pausa. Aparece um selo **"⏸ PAUSADO"** no canto pra você saber que está congelado.
>
> **A Região Crítica é MANUAL:** os nós **não** entram na região crítica sozinhos — ela fica **vazia** até você clicar em **🔓 Pedir RC**. Ou seja, VOCÊ decide quem tenta entrar e quando. Quando um nó entra, ele segura a região crítica por uns 5–6 segundos (tempo de sobra pra você narrar ou pausar).

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

### 🖥️ Suba o cluster (se ainda não subiu) e abra o painel:
```bash
docker compose up --build
```
> Abra **http://localhost:8080**. *[Deixe os slides na lateral ou volte ao slide 8 — a teoria de Bully casa com o que vai aparecer no painel.]*

🎙️ **Fala** *[enquanto o grafo ganha vida e as mensagens começam a voar]*:
> "Pronto, subi os cinco nós de uma vez, e é isso que vocês estão vendo: cada bolinha é um nó, um contêiner separado, e essas mensagens que voam de um pro outro são as chamadas gRPC de verdade acontecendo na rede. Repara que nenhum nó nasce sabendo quem são os vizinhos. Então a primeira coisa que cada um faz é se apresentar e procurar os outros — são esses pacotes indo e voltando."

**1. Discovery** — *[aponte os pacotes cinza (heartbeat) e, nos logs, filtre por "Rede/Sistema"]*:
> "Esse vai-e-vem cinza é o discovery: cada nó fica chamando os outros até confirmar que todo mundo está de pé. Nos logs dá pra ler 'um de quatro prontos', 'dois de quatro', até 'todos prontos'. Só depois disso ele começa a participar pra valer."

**2. Eleição Bully inicial** — *[aponte os pacotes roxos/laranja e a coroa 👑 pousando no Node 5]*:
> "Assim que ficam prontos, eles já fazem uma eleição pra escolher o líder — são essas mensagens roxas de eleição voando pros nós maiores. E olha o resultado: a coroa apareceu no Node 5. Foi certinho o que a teoria diz — os nós menores mandam a eleição pros maiores, e o Node 5, que tem o maior número, não acha ninguém acima dele e se declara líder."

**3. COORDINATOR aceito** — *[filtre os logs por "Bully" pra mostrar]*:
> "E, filtrando os logs por Bully, dá pra ler os outros aceitando: 'reconhece o Node 5 como líder'. Em uma fração de segundo o cluster escolheu um líder sozinho — a coroa no painel mostra isso de um jeito que não tem erro."

**4. ⚠️ Antecipando a dúvida da redundância** *[fale isso ANTES que percebam, mostra domínio]*:
> "E eu queria já adiantar uma coisa que aparece nos logs: o Node 5 se declara líder mais de uma vez ali no comecinho. Isso é esperado e está certo.
>
> Como cada nó faz uma eleição na hora que entra no cluster, e eles entram com uns segundinhos de diferença, a eleição acaba acontecendo algumas vezes nesse comecinho.
>
> O que importa é que o resultado é sempre o mesmo: não importa quantas vezes rode, sempre converge pro nó de maior número que estiver vivo. Então não é o sistema instável, é ele se confirmando."

---

## BLOCO 4 — DEMO: Relógio de Lamport ao vivo (5:00 – 5:45)

### 📊 Volte ao Slide 4 por uns segundos, depois 🖥️ aponte para o **⏱ dentro de cada nó** no grafo.

🎙️ **Fala** — *[aponte o número do relógio dentro de cada bolinha; cada pacote que chega faz o número pular]*:
> "Agora olha uma coisa que está rolando o tempo todo, meio que no fundo: o relógio de Lamport. É esse número com o relóginho dentro de cada nó, e ele muda a cada mensagem que chega — dá até pra ver o número saltar quando um pacote pousa no nó. Repara que os cinco não estão no mesmo número — cada um tem o seu contador lógico.
>
> E eles se puxam pra frente: quando um nó com relógio mais alto fala com outro que está mais atrás, o de trás dá um salto pra se ajustar. Dá pra ver isso ao vivo nos números subindo em ritmos diferentes."

*[Pra mostrar o salto exato, filtre o painel de logs por "Lamport" — cada linha mostra o "de X para Y".]*
> "Aqui nos logs, filtrando por Lamport, dá pra ver o salto na íntegra: por exemplo, um nó que estava no oito e, ao receber uma mensagem, pula direto pro dezesseis. Ele não foi do oito pro nove — ele pegou o maior valor entre o dele e o que chegou, e somou um.
>
> É a tal da causalidade acontecendo: quem recebe se ajusta pra nunca parecer que aconteceu antes de quem mandou."

---

## BLOCO 5 — DEMO: Exclusão mútua Ricart-Agrawala (5:45 – 7:30)

> **Coração da apresentação.** Vá devagar, é aqui que você prova que entende mesmo.
> O painel foi feito pra este momento: o banner **"Região Crítica"** no topo e os badges dos cards contam a história sozinhos.

### 📊 Tenha o Slide 5 à mão; 🖥️ foco no grafo — anéis dos nós + banner do topo. *[Dica: desligue "mostrar heartbeats" pra limpar a tela e ver só REQUEST/REPLY.]*

**1. Um pedido isolado** — 🔴 AO VIVO *[a região crítica está VAZIA; clique em "🔓 Pedir RC" em UM nó, ex.: Node 3]*:
> "Agora a parte que pra mim é a mais legal, a exclusão mútua. Repara no banner: a região crítica está livre, ninguém dentro. Eu que controlo quem tenta entrar — então deixa eu pedir a região crítica pro Node 3.
>
> Olha o que acontece: saem dele quatro pacotes amarelos de uma vez — são os REQUESTs, ele pedindo permissão pra todos os vizinhos. Ele ganha o anel amarelo, 'quero entrar', junta as respostas e o anel fica verde: entrou. O banner agora mostra o Node 3 lá dentro."

**2. Forçando a disputa** — 🔴 AO VIVO *[enquanto um nó está dentro, clique em "🔓 Pedir RC" em outros dois ou três nós]*:
> "E se dois quiserem ao mesmo tempo? Deixa eu provocar isso: com o Node 3 ainda dentro, vou pedir a região crítica pra mais dois ou três nós. Olha a chuva de pacotes amarelos — todos pedindo ao mesmo tempo. Vários ficam com o anel amarelo, 'quero entrar', mas presta atenção no banner: ele continua deixando **um** entrar de cada vez. Ninguém fura a fila.
>
> *[Dica: aqui é um ótimo momento pra clicar em ⏸️ Pausar e explicar a regra de prioridade com a tela congelada.]*"

**3. O ADIAMENTO — o momento-chave** — *[filtre o painel de logs por "Ricart-Agrawala"]*:
> "E por baixo desse comportamento tem a regra do algoritmo. Filtrando os logs por Ricart, aparece o que decide a fila: quando dois nós querem entrar juntos, cada um compara o próprio par de tempo e identificador com o do outro.
>
> Quem tem o tempo menor passa na frente e **segura** a resposta do outro — repara que ele não nega, ele só guarda pra responder depois. É a linha 'pedido do Node tal ADIADO', com a comparação dos tempos ali do lado.
>
> E olha que coisa boa, que prova que não tem ninguém centralizando: cada nó, sozinho, comparando só os tempos, chega exatamente na mesma fila. A ordem aparece sozinha."

**4. SAÍDA + REPLY proativo** — *[aponte o anel verde apagando e os pacotes verdes de REPLY saindo desse nó]*:
> "Quando o nó que estava dentro termina, ele sai — o anel verde apaga — e nesse instante saem dele os pacotes verdes de REPLY, a resposta guardada indo pra quem estava esperando. No painel você vê o banner trocar de dono na hora: saiu um, entrou o próximo da fila. Nos logs é a linha azul, 'saiu da região crítica, mandando a resposta guardada pra fulano'."

**5. A SEQUÊNCIA — frase de fechamento** *[diga com calma, é o seu ponto alto; aponte o banner]*:
> "E é isso que eu queria que ficasse: durante essa disputa toda, o banner nunca acusou dois nós dentro ao mesmo tempo. Um entrou, saiu, o próximo entrou — sempre em ordem, sempre um de cada vez.
>
> E essa ordem não é aleatória: é a ordem crescente dos relógios de Lamport. Quem pediu com o tempo menor entrou primeiro.
>
> Ou seja: cinco processos separados, sem nenhum chefe, conseguiram organizar perfeitamente quem usa o recurso e quando, usando só os relógios lógicos. É o Ricart-Agrawala funcionando direitinho como a teoria diz."

> 💡 *[Se quiser o exemplo numérico exato: filtre os logs por Ricart e leia uma linha de ADIAMENTO real que apareceu, ex.: "(ts=78,id=1) < (ts=96,id=5)". O painel garante que sempre há um exemplo fresco na tela.]*

---

## BLOCO 6 — CLÍMAX: matando o líder e reeleição Bully (7:30 – 9:00)

### 📊 Slide 9 (Tolerância a Falhas) — abra ANTES de matar o nó.
🎙️ **Fala:**
> "Até aqui eu mostrei o sistema funcionando quando tá tudo bem. Mas um sistema distribuído de verdade precisa aguentar uma falha — então agora eu vou quebrar ele de propósito.
>
> Cada nó tem uma parte que fica checando o líder a cada dois segundos, pra ver se ele ainda está vivo — são os heartbeats voando pro nó da coroa. O líder agora é o Node 5.
>
> Eu vou clicar em 'matar' nele, do nada, como se a máquina tivesse caído, e a gente vê se o cluster se vira sozinho."

### 🖥️ 🔴 AO VIVO — na barra de controles, clique em **💀 Matar** no **Node 5** (o líder):
> *[O nó vira uma caveira 💀 no grafo e para de trocar mensagens. Observe os outros quatro.]*

🎙️ **Fala** — *[aponte para o grafo conforme os nós reagem]*:
> "Pronto, derrubei o líder. Ele já virou uma caveira e parou de mandar e receber mensagem. Vamos esperar uns segundinhos..."

**1. Detecção** — *[filtre os logs por "Bully"]*:
> "Olha aí nos logs: 'falha do líder Node 5 detectada'. A checagem não recebeu resposta a tempo e os nós perceberam sozinhos que o líder sumiu."

**2. ELECTION + COORDINATOR** — *[aponte a coroa 👑 pulando pro Node 4]*:
> "E aí a mágica no painel: a coroa pula pro Node 4. Quem percebeu a falha já começa uma eleição, chamando os nós de número maior. Como o Node 5 caiu, o maior que sobrou vivo é o Node 4, e é ele quem assume — 'Node 4, sou o novo líder'. Todos os outros passam a reconhecer ele. O sistema escolheu um novo líder sozinho, sem eu fazer nada."

**3. Continuidade** *[esse é o argumento que fecha a robustez; aponte o banner da região crítica]*:
> "E o que fecha bem o raciocínio: repara que o banner da região crítica **continuou funcionando** o tempo todo. A exclusão mútua não parou — o Ricart-Agrawala segue rodando normal, só que agora com quatro nós em vez de cinco.
>
> Perder o líder não derrubou o serviço — e isso faz sentido, porque no Ricart-Agrawala não tem um chefe coordenando a região crítica. O líder aqui existe justamente pra isso que eu acabei de mostrar: pra ter o que monitorar e reeleger quando cai. O controle de quem entra na região crítica já é distribuído por natureza.
>
> Isso é tolerância a falha de verdade."

### 🖥️ (Opcional) Restaurar — na barra de controles, clique em **♻️ Reviver** no Node 5:
> "E pra fechar o ciclo: se eu reviver o Node 5, a coroa volta pra ele — porque na eleição seguinte ele continua sendo o de maior número. Então o sistema lida bem tanto com um nó saindo quanto com ele voltando."

> 💡 *[Alternativa "raiz": em vez do botão, dá pra derrubar o contêiner de verdade num terminal com `docker stop node5` — o efeito no painel é idêntico (o nó fica sem resposta e vira caveira). O botão é mais limpo pra gravação; o `docker stop` é mais "hardcore" se algum professor pedir a queda real do processo.]*

---

## BLOCO 7 — Infraestrutura e prova nos logs (9:00 – 9:45)

### 📊 Slide 10 (Docker Compose)
🎙️ **Fala:**
> "Vale mostrar rapidinho como tudo isso fica montado. São cinco contêineres numa rede só, todos na porta 50051, e — falando de novo, porque é exigência do trabalho — nada de simulação: cada uma dessas caixinhas é um processo de verdade, com IP de verdade, conversando pela rede. Cada nó recebe só o seu número e a lista dos vizinhos por configuração, então é o mesmo código subindo os cinco, mudando só esses ajustes."

🖥️ *[opcional]* `cat docker-compose.yml` rápido pra mostrar os cinco serviços.

### 📊 Slide 11 (Resultados / Logs Didáticos)
🎙️ **Fala** *[amarrando com o que acabaram de ver no painel]*:
> "E essa aqui é a legenda dos logs que estavam rolando no painel o tempo todo. Eu fiz questão de marcar cada evento com um emoji e dar uma cor pra cada nó, justamente pra facilitar na hora de mostrar — e o painel deixa filtrar por algoritmo, que é o que eu fui fazendo.
>
> Verde é o relógio de Lamport saltando; amarelo é alguém pedindo a região crítica; vermelho é um pedido ficando pra depois por causa da prioridade; o certinho verde é entrar na região crítica; o azul é sair e liberar quem estava esperando; e a coroa é a eleição.
>
> Então o painel visual e os logs contam a mesma história de dois jeitos: os cards mostram o *estado* de cada nó agora, e os logs mostram o *porquê*, mensagem por mensagem, em tempo real."

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

## Mapa rápido Slide ↔ Painel

| Momento | Slides | O que fazer no painel (http://localhost:8080) |
|---|---|---|
| Abertura | 1, 2, 3 | — (opcional: `cat docker-compose.yml`) |
| Teoria | 4, 5, 6, 7, 8 | — |
| Subida + Bully inicial | (8 ao fundo) | `docker compose up --build` → grafo ganha vida (pacotes voando), **coroa 👑 no Node 5** |
| Lamport ao vivo | 4 | apontar o **⏱ dentro de cada nó** saltando; filtrar logs por **Lamport** |
| Ricart-Agrawala | 5 | **banner "Região Crítica"** + anéis dos nós; clicar **🔓 Pedir RC** em 2–3 nós (chuva de pacotes amarelos); filtrar logs por **Ricart** |
| **Matar líder** 🔴 | 9 | clicar **💀 Matar** no Node 5 → **coroa pula pro Node 4**; filtrar logs por **Bully** |
| Reviver (opcional) | 9 | clicar **♻️ Reviver** no Node 5 → coroa volta |
| Infra + prova | 10, 11 | legenda de cores/emojis = painel de logs |
| Conclusão | 12 | `docker compose down` |

---

## Checklist pré-gravação

- [ ] Docker Desktop rodando
- [ ] `docker compose down` (sem containers antigos)
- [ ] `docker compose up --build` no ar **e http://localhost:8080 aberto** (grafo com os 5 nós e mensagens voando, coroa no Node 5)
- [ ] Layout: **slides + painel** dividindo a tela; fonte dos slides grande
- [ ] Cronômetro visível
- [ ] Gravação iniciada (tela inteira)
- [ ] Testar os botões uma vez antes de gravar: **⏸️ Pausar/Continuar**, **🔓 Pedir RC**, **💀 Matar / ♻️ Reviver** no Node 5
- [ ] Lembrar: a Região Crítica começa **vazia** — nada acontece nela até você clicar **🔓 Pedir RC**
- [ ] Lembrar: a reeleição só aparece se você **matar o líder ao vivo** (botão 💀 ou `docker stop node5`)
