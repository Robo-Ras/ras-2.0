# Como rodar o robô

Passo a passo para ligar o RAS 2.0 no notebook do robô. Detalhes de cada parte ficam em [DOCUMENTACAO.md](DOCUMENTACAO.md) e, para a voz, em [voz/README.md](voz/README.md).

## O que abre em cada endereço

| Endereço | O que é |
|----------|---------|
| http://localhost:8080 | Painel de controle (câmera, LiDAR, joystick, modo autônomo, controle por voz do navegador) |
| http://localhost:8080/tablet | Carinha de status do robô (vermelha, laranja ou verde) |
| http://localhost:8090 | Rosto do assistente de voz José (só com `--voz`) |
| ws://localhost:8765 | Backend (o navegador e o José falam com ele; não precisa abrir) |

## 1. Primeira vez (só uma vez por máquina)

```bash
cd ~/ras-2.0
sudo apt install libportaudio2                       # microfone do José
~/L515/bin/pip install -r backend/requirements.txt   # backend
~/L515/bin/pip install -r voz/requirements.txt       # assistente de voz
```

Rode os comandos **de dentro de `~/ras-2.0`**. Fora dela o pip não acha o arquivo (`Could not open requirements file`).

O frontend instala sozinho na primeira vez que o `start.sh` roda. O modelo de fala do José (~500 MB) baixa na primeira vez que ele abre.

Opcional: as histórias do José (~260 MB) não vêm no git. Baixe de [RAS-CommandPerVoice/historinhas](https://github.com/KimberlyRotman/RAS-CommandPerVoice/tree/main/historinhas) para `~/ras-2.0/voz/historinhas/`.

## 2. Testar sem o robô (simulador)

```bash
cd ~/ras-2.0
./start.sh --sim          # painel com robô, Arduino, câmera e LiDAR simulados
./start.sh --sim --voz    # o mesmo, mais o José
```

Bom para conferir que está tudo instalado antes de ligar o robô de verdade.

## 3. Rodar no robô

1. Ligue a bateria do robô.
2. Conecte no notebook, por USB: o Arduino, o LiDAR, a câmera C270 e a D435 (a D435 numa porta USB 3, azul).
3. Coloque o robô **no chão, com espaço livre em volta**, ou com as rodas fora do chão no primeiro teste.
4. Rode:

   ```bash
   cd ~/ras-2.0
   ./start.sh --voz
   ```

5. Abrem duas abas: o painel (8080) e o rosto do José (8090). No rosto, **clique uma vez para tela cheia**.
6. No painel, confira:
   - o status do **Servidor Python** está conectado;
   - o **Arduino** está conectado (se não estiver, escolha a porta no card de conexão serial e conecte);
   - em *Status dos Sensores*, a câmera e o LiDAR online.
7. Teste devagar: um toque nos botões de direção ou WASD, depois o modo autônomo.

Sem o José: `./start.sh` (sem `--voz`).

## 4. Falando com o José

Para andar o formato é **"José, \<comando\>"**, e não usa IA (só um dicionário de palavras):

| Fala | O robô |
|------|--------|
| "José, **frente**" | Anda para frente 1,5 s e para |
| "José, **trás**" | Anda para trás 1,5 s |
| "José, **direita**" / "José, **esquerda**" | Anda para o lado 1,5 s |
| "José, **gira**" | Gira no lugar uma volta |
| **"Pare"** / **"Para"** | Para na hora (vale sozinho, sem "José"; só se for a única palavra) |
| "José, **história**" | Conta histórias ("próxima", "volta", "para") |
| "José, **conversa**" | Conversa livre com o Gemini ("voltar" sai). Precisa de internet e da `GEMINI_API_KEY` ([voz/README.md](voz/README.md)) |

- Se disser só **"José"**, o rosto desliza e a **próxima palavra** ("frente") já basta, por 6 s. **Depois de cada comando é preciso dizer "José" de novo** (palavra solta nunca move o robô).
- Se disser "frente" sem "José", aparece a dica **"Diga José antes do comando"** e o robô não se mexe.
- O dicionário de palavras e variações está em [`comandos_voz.json`](comandos_voz.json): se um comando não for entendido, acrescente a palavra que ele ouviu. Para ver o que ele ouviu, abra o rosto com `?debug=1`: http://localhost:8090/?debug=1 (normalmente a cara não mostra mensagens).

O painel também ouve: botão *Microfone do navegador* no card **Voz** (só no Chrome ou Edge, precisa de internet). Os dois reconhecedores ouvem ao mesmo tempo e **o primeiro que detectar executa** (o outro é ignorado por 1,5 s).

## 5. Controlar pelo celular

```bash
./start.sh --voz --controle
```

O terminal mostra uma linha como `📱 Controle do celular: http://10.189.148.202:8100`. Abra esse endereço no celular, **ligado no mesmo Wi-Fi do notebook**. É uma tela só com os botões de movimento:

- No topo da tela aparece o **preview da C270 ao vivo**, na largura toda; os botões ficam embaixo, menores.
- **Segure** um botão para andar; ao **soltar**, o robô **freia** (em 1 s a velocidade cai à metade e então ele para). Se o Wi-Fi cair ou a tela apagar, o backend corta os motores sozinho em 0,6 s.
- **PARAR** (vermelho, no topo) para os motores e desliga o modo autônomo.
- O controle de velocidade fica na própria tela e é lembrado.
- O celular recebe só o estado e a imagem da C270 (sem LiDAR nem a D435), então pesa pouco no Wi-Fi.

O painel (8080) e o rosto do José (8090) continuam abertos **só no notebook**. Com `--controle`, o backend (porta 8765) e o controle (8100) ficam acessíveis na rede: qualquer aparelho no mesmo Wi-Fi consegue mover o robô. Use em rede confiável (não em Wi-Fi público).

Quando só existe uma porta serial (fora a do LiDAR), o Arduino conecta sozinho ao iniciar, sem precisar do painel.

## 6. Freio suave ("ABS")

Para não derrapar nem parar de uma vez, ao **terminar um comando**, **soltar o botão** (celular) ou **trocar de direção**, o robô **reduz a velocidade à metade em 1 segundo e só então para** (ou vira, na troca de direção). Vale para os comandos de voz e para o controle manual (painel e celular). **Parada de emergência não freia**: o botão PARAR, o "pare" por voz e o celular sem sinal cortam os motores na hora. O modo autônomo não usa o freio (ele precisa reagir rápido a obstáculos).

## 7. Esconder sensores da interface

Cada câmera e o LiDAR têm um interruptor no canto do card. Desligado, o item some da tela (e do resumo de obstáculos), por exemplo para apresentar só com a C270. Isso **só esconde**: o robô continua lendo todos os sensores. A escolha fica salva no navegador.

## 8. Usar pelo tablet

```bash
./start.sh --lan --voz
```

No tablet, na mesma rede Wi-Fi (descubra o IP do notebook com `hostname -I`):

- carinha de status: `http://<ip-do-notebook>:8080/tablet`
- rosto do José: `http://<ip-do-notebook>:8090`

Com `--lan`, qualquer pessoa na mesma rede consegue controlar o robô. Use só em rede confiável.

## 9. Andar nas 8 direções e calibrar os motores

O robô tem **3 rodas omnidirecionais a 120°**: **M2 na frente**, **M1 atrás à esquerda** e **M3 atrás à direita**. Quem calcula o PWM de cada motor é o sistema ([`backend/kinematics.py`](backend/kinematics.py)); o Arduino continua só recebendo `m1,m2,m3` e **não foi alterado**.

**Teclado numérico** (no painel, em *Controle manual*; só o valor da tecla é enviado):

```
7 ↖   8 ↑   9 ↗
4 ←   5 ■   6 →      5 para o robô
1 ↙   2 ↓   3 ↘      Q / E giram no lugar
```

W A S D e as setas continuam valendo (= 8, 4, 2, 6). No celular os botões têm a mesma disposição.

### Os limites de PWM (e por que dependem da velocidade)

Na **velocidade padrão 60**, os motores trabalham **entre 50 e 100**: o mais forte (o da frente) no mínimo, **50**, e o mais fraco (o da direita) no máximo, **100**, no limite de **2 para 1** de diferença para não acelerar demais. Abaixo de 50 o motor não gira. Se a velocidade sobe, **o mínimo e o máximo sobem juntos** (na 100: ~83 a ~167). A velocidade vai de 60 a 100 (abaixo de 60 o motor da frente não giraria).

Valores que o sistema envia com a calibração inicial:

| Tecla | Direção | M1 (trás-esq.) | M2 (frente) | M3 (trás-dir.) | velocidade 100: M1 / M2 / M3 |
|-------|---------|---:|---:|---:|---|
| `8` | ↑ frente (**acertada no robô**) | 67 | 0 | -59 | 112 / 0 / -98 |
| `9` | ↗ frente-direita | 50 | 50 | -97 | 50 / 59 / -161 |
| `6` | → direita | -50 | 50 | -50 | -76 / 83 / -83 |
| `3` | ↘ trás-direita | -88 | 50 | 50 | -146 / 59 / 50 |
| `2` | ↓ trás (**o inverso da frente**) | -67 | 0 | 59 | -112 / 0 / 98 |
| `1` | ↙ trás-esquerda | -50 | -50 | 97 | -50 / -59 / 161 |
| `4` | ← esquerda | 50 | -50 | 50 | 76 / -83 / 83 |
| `7` | ↖ frente-esquerda | 88 | -50 | -50 | 146 / -59 / -50 |
| `cw` | ↻ giro horário | 91 | 50 | 100 | 152 / 83 / 167 |
| `ccw` | ↺ giro anti-horário | -91 | -50 | -100 | -152 / -83 / -167 |

**O que mudou em relação à tabela antiga:** "esquerda/direita" era `(0, ±s, ∓s)`, que zera uma roda e dá uma **diagonal** (e é o que você viu: o botão de lado ia para frente-direita / trás-esquerda). De lado de verdade, a roda da frente faz a força maior e as **duas de trás ajudam, metade cada, no sentido oposto**. Além disso, como os motores têm forças diferentes, o PWM de cada um é dividido pela sua força (motor forte recebe menos), o que compensa o desvio para a esquerda ao ir para frente/trás (o motor da esquerda é um pouco mais forte).

### Calibrar na prática (cartão *Calibração dos motores* no painel)

**Já acertado no robô:** a **frente** (`8` = `67, 0, -59`) foi achada na prática, e a **trás** (`2`) é o **inverso exato** dela. As duas ficam gravadas como valores por tecla (marcadas *manual*). Mexer na força dos motores e nas correções globais para acertar a frente piorou todas as outras teclas, por isso o ajuste ficou só nessas duas. O **lado** (`4`/`6`) ainda vai ser calculado.

Os outros valores iniciais são **estimativas**: força `M1 = 1,10 · M2 = 2,00 · M3 = 1,00` (só a proporção importa). Cada ajuste vale na hora e fica gravado em `backend/calibracao_robo.json`.

1. **Rodas fora do chão** (robô levantado), botão de parada física à mão. Aperte cada tecla e confira que **as rodas certas giram no sentido certo** (a tabela acima): `8` = M1 e M3 (M2 parada); `6` e `4` = as três; `5` para tudo.
2. **No chão**, em espaço livre, nível 60, tecla `8` por uns 2 s:
   - **puxa para a esquerda** (ou direita): ajuste a força de **M1 contra M3** (suba M1 se puxa para a esquerda) ou use a **correção lateral** (positivo = empurra para a direita);
   - **curva em vez de ir reto**: **correção de giro** (positivo = gira horário).
3. Repita com `2` (trás).
4. **Lados** (`4` e `6`): se ele ainda vai para frente/trás enquanto anda de lado, é a proporção **M1 contra M3**; se ele gira andando de lado, é a força de **M2 (frente)** contra M1 e M3.
5. **Diagonais** (`7 9 1 3`): são as mais sensíveis. A `9` e a `1` são o espelho da `7` e da `3`: uma roda que só precisa ajudar um pouco **recebe o mínimo (50) e não fica parada**, porque com só uma roda de trás empurrando o robô pivota (era o giro grande da `9` e da `1`).

### Ajustar uma tecla na mão (tabela *Valores por tecla*)

A estimativa de força dos motores não acerta tudo. Para acertar **uma tecla na prática**, edite os três valores dela no cartão (M1 M2 M3): vale na hora, escala com a velocidade, fica gravado em `backend/calibracao_robo.json` e a linha vira **manual** (o ícone ↺ volta à conta). Vale também para a voz e o modo autônomo; teclas *manual* ignoram a força dos motores e as correções globais. A opção **inverso na tecla oposta** põe, ao editar uma tecla, o valor com o sinal trocado na tecla oposta (como foi feito da frente para a trás). Cada motor: 0 ou de 50 a 100 (nível 60). O simulador (`--sim`) não usa nem grava esses ajustes.

Como ler o que o robô faz:
- **Anda de lado (`4`/`6`) mas gira junto (arco aberto):** a soma dos três motores, nos sentidos em que empurram, não dá zero. Gira no sentido horário → reduza M1 e M3 (ou suba o módulo de M2); anti-horário → o contrário.
- **Anda para frente/trás (`8`/`2`) puxando para um lado:** é a proporção entre M1 e M3 (hoje `79 : 87`). Puxa para a esquerda → reduza o módulo de M1 (ou suba o de M3).
- Anote os valores que ficaram bons e me passe: eu coloco como padrão.

**Limites que valem saber:** a correção lateral ao andar para frente/trás só liga a roda da frente a partir de ~25% (ela não gira com menos de 50), então abaixo disso ela atua só pelas rodas de trás. A diferença máxima de força entre motores é **2:1** (o cartão recusa mais que isso).

### Freio ao trocar de direção

Ao **trocar de direção** com o robô andando, ele freia antes de virar, e o tempo é **proporcional à velocidade**: 0,4 s com o motor mais exigido em PWM 100 (0,2 s em PWM 50). Antes era 1 s fixo. Fim de comando e soltar o botão no celular continuam freando em 1 s; parada de emergência corta na hora.

## 10. Desligar

`Ctrl+C` no terminal do `start.sh`. Os motores recebem a ordem de parar, e o backend, o painel e o José fecham juntos. Depois desligue a bateria.

## Emergência

- **Tecla espaço** no painel, ou o botão de **parada de emergência** no card do modo autônomo.
- Diga **"Para!"** ao José.
- Se nada estiver conectado ao backend (nenhuma aba do painel e nenhum José), ele manda parar sozinho. Com o José aberto, fechar só as abas **não** para o robô.
- Último recurso: `Ctrl+C` no terminal ou desligar a bateria.

## Problemas comuns

| Problema | O que fazer |
|----------|-------------|
| `Could not open requirements file` | Rode o `pip` de dentro de `~/ras-2.0` |
| `PortAudio library not found` | `sudo apt install libportaudio2` |
| Porta do Arduino não aparece | Confira o cabo; `ls /dev/ttyUSB* /dev/ttyACM*`; usuário no grupo `dialout` |
| LiDAR não detectado | `./start.sh --lidar ld06 --lidar-port /dev/ttyUSB1` (ou `--lidar rplidar`) |
| Radar do LiDAR girado ou espelhado | `--lidar-offset 180` ou `--lidar-flip` |
| Câmera errada | `v4l2-ctl --list-devices` e depois `--camera-device /dev/videoN` |
| José não entende | Fale perto do microfone e espere o rosto mudar depois de "José". A transcrição aparece no canto superior esquerdo do rosto |
| Rosto diz "José não está respondendo" | O `jose.py` fechou: veja o erro no terminal |
| Porta 8080, 8090 ou 8765 em uso | Já tem outro `start.sh` rodando: feche-o (`Ctrl+C`) ou `pkill -f start.sh` |
| Robô gira demais ou de menos na meia volta | Ajuste os tempos em `VOICE_MOVES` em `backend/robot_autonomous_control.py` |

Para conferir que nada quebrou depois de mexer no código: `./test.sh` (não precisa do robô).
