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

1. Diga **"José"**: o rosto desliza e fica ouvindo.
2. Diga o comando:

| Fala | O robô |
|------|--------|
| "Vai pra frente / trás / direita / esquerda" | Anda 1,5 s e para |
| "Dê meia volta" / "Dê volta completa" | Gira no lugar |
| **"Para"** / **"Pare"** | Para na hora (funciona sem chamar "José" de novo) |
| "História" | Conta histórias ("próxima", "volta", "para") |
| "Obrigado" | "Ao seu dispor" e volta a esperar |

"Me segue" e "Fica do meu lado" aparecem na tela, mas o robô ainda não faz nada com eles.

O último comando recebido aparece no card **Controle por Voz** do painel. Lá também dá para falar pelo microfone do navegador (botão *Ativar Voz*, só no Chrome ou Edge).

## 5. Usar pelo tablet

```bash
./start.sh --lan --voz
```

No tablet, na mesma rede Wi-Fi (descubra o IP do notebook com `hostname -I`):

- carinha de status: `http://<ip-do-notebook>:8080/tablet`
- rosto do José: `http://<ip-do-notebook>:8090`

Com `--lan`, qualquer pessoa na mesma rede consegue controlar o robô. Use só em rede confiável.

## 6. Desligar

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
