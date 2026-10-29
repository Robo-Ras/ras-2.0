# Voz — assistente José

Assistente de voz do RAS, trazido de [KimberlyRotman/RAS-CommandPerVoice](https://github.com/KimberlyRotman/RAS-CommandPerVoice) (autora: Kimberly Rotman, commit `3147c11`).

O José escuta o microfone o tempo todo, transcreve offline com [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (português) e reage com um rosto. No RAS 2.0:

- o rosto é uma **página web própria em http://localhost:8090** (antes era uma janela tkinter), separada do painel do robô (8080);
- ele **manda os comandos para o backend**, que move o robô e avisa o painel.

## Instalação

```bash
sudo apt install libportaudio2
~/L515/bin/pip install -r ~/ras-2.0/voz/requirements.txt     # mesmo venv do backend
```

Na primeira execução o faster-whisper baixa o modelo `small` (~500 MB). Na primeira vez que entrar no modo conversa, baixa também o `large-v3-turbo` (~1,6 GB).

### Chave do Gemini (modo conversa)

1. Entre em https://aistudio.google.com/apikey com uma conta Google e clique em **Create API key** (plano gratuito, sem cartão).
2. No notebook do robô, salve a chave no `~/.bashrc` (não coloque no git):

   ```bash
   echo 'export GEMINI_API_KEY="cole-a-chave-aqui"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. Teste: `~/L515/bin/python -c "from google import genai; print(genai.Client().models.generate_content(model='gemini-3.8-flash', contents='oi').text)"`

No plano gratuito o Google pode usar as conversas para melhorar os produtos dele, e há limite de pedidos por minuto e por dia. O modo conversa (Gemini e voz) precisa de internet; os outros modos continuam offline.

As histórias (`historinhas/*.mp3`, ~260 MB) **não ficam no git**. Baixe da [pasta historinhas do repositório original](https://github.com/KimberlyRotman/RAS-CommandPerVoice/tree/main/historinhas) e coloque em `voz/historinhas/`.

## Como rodar

```bash
./start.sh --voz            # backend + frontend + José
./start.sh --sim --voz      # com o robô simulado

# ou separado, com o backend já rodando:
cd ~/ras-2.0/voz
~/L515/bin/python jose.py                       # rosto em http://localhost:8090, backend em ws://127.0.0.1:8765
~/L515/bin/python jose.py --porta 8091          # outra porta para o rosto
~/L515/bin/python jose.py --host 0.0.0.0        # abrir o rosto de outro aparelho (tablet)
~/L515/bin/python jose.py --backend ws://192.168.0.10:8765
~/L515/bin/python jose.py --sem-robo            # só o rosto, sem mandar comandos
```

O navegador abre sozinho no rosto (`--no-browser` evita). **Clique na página para tela cheia**; `Esc` sai. A página consulta `/estado` a cada 100 ms; se o José for fechado, ela avisa e volta sozinha quando ele subir de novo.

O áudio das histórias toca no computador onde o `jose.py` roda, não no navegador.

O endereço do backend também pode vir de `RAS_WS_URL`. Se o backend não estiver no ar, o José continua funcionando e tenta reconectar a cada 3 s (comandos falados nesse meio-tempo são descartados, para o robô não sair andando depois).

## Fluxo

1. **Acordado** — mostra `joseacordado.png`.
2. **Ouvindo** — ao ouvir **"José"**, o rosto desliza para a esquerda e troca para `joseouvindo.png`.
3. **Comando** — com o backend no ar, mostra `Josefechado.png` com o comando, **para de escutar** até o robô terminar o movimento e volta direto a ouvir (sem precisar dizer "José"). Sem backend, mostra o comando e espera "obrigado", como antes.
4. **Obrigado/Obrigada** — (só sem backend) mostra "Ao seu dispor" por 3 s e volta ao rosto acordado.

Sem backend, enquanto um comando está na tela, dizer **"para"/"pare"** para o robô sem precisar chamar "José" de novo. Com o backend, os movimentos duram no máximo 4 s e param sozinhos; para parar antes use o painel (espaço).

## Comandos e o que o robô faz

| Fala | id enviado | No robô |
|------|-----------|---------|
| "Vai pra frente / trás / direita / esquerda" | `frente`, `tras`, `direita`, `esquerda` | Anda 1,5 s e para |
| "Dê meia volta" | `meia_volta` | Gira no lugar 2 s |
| "Dê volta completa" | `volta_completa` | Gira no lugar 4 s |
| "Para" / "Pare" / "Parar" | `parar` | Para na hora e desliga o modo autônomo |
| "Me segue" | `me_segue` | Ainda não implementado (só aparece no painel) |
| "Fica do meu lado direito / esquerdo" | `lado_direito`, `lado_esquerdo` | Ainda não implementado |

Os tempos e a velocidade ficam em `VOICE_MOVES` e `VOICE_SPEED` em `backend/robot_autonomous_control.py`. Os tempos de giro são estimativas: **calibre no robô real**.

Mensagem enviada pelo WebSocket:

```json
{"type": "voice_command", "command": "frente", "text": "José, vai pra frente", "source": "jose"}
```

O backend responde a todos os clientes com o mesmo `type`, mais `status` (`ok`, `no_robot`, `not_implemented`, `unknown`) e `running` (`true` se um movimento começou). Quando o movimento termina (ou é interrompido) ele manda `{"type": "voice_command_done", "command": "frente"}`; é isso que o José espera para voltar a ouvir. O card **Controle por Voz** do painel mostra o último comando recebido, venha ele do José ou do microfone do navegador; os dois usam o mesmo vocabulário (`frontend/src/lib/voiceCommands.ts`).

## Modo conversa

Diga **"Conversa"** enquanto o José está ouvindo.

| Tela | Quando |
|------|--------|
| `Josefechado` + "carregando..." | Só na primeira vez: carrega o modelo de fala maior (`large-v3-turbo`, fica na memória depois) |
| `joseacordado` + "ouvindo..." | Grava até você ficar 1 s em silêncio (máx. 30 s) |
| `Josefechado` + "pensando..." | Transcreve e pergunta ao Gemini (microfone desligado) |
| `joseresponde` + "respondendo..." | Fala a resposta com a voz `pt-BR-AntonioNeural` (microfone desligado) |

- O Gemini recebe o áudio e a transcrição. Pelo tom de voz ele identifica a emoção; se não for neutra, a resposta começa com "Notei que você parece um pouco triste/feliz/...".
- Ele lembra as últimas perguntas enquanto a conversa durar; **"Voltar"** apaga a memória e volta ao menu (ouvindo comandos, sem precisar dizer "José").
- **"História"** e os comandos de movimento também funcionam na conversa; depois do movimento ele volta a conversar.
- Configurável por variáveis de ambiente: `GEMINI_API_KEY`, `JOSE_GEMINI_MODELO` (padrão `gemini-3.8-flash`), `JOSE_VOZ` (padrão `pt-BR-AntonioNeural`), `JOSE_MODELO_CONVERSA` (padrão `large-v3-turbo`; use `medium` ou `small` se ficar lento).
- A detecção de fim de fala usa o volume do microfone (`ENERGIA_MIN_VOZ`, `FATOR_VOZ` em `jose.py`). Em lugar muito barulhento ajuste esses valores.

## Modo história

Diga **"História"** enquanto o José está ouvindo. As histórias de `historinhas/` tocam em ordem sorteada, com título e barra de progresso.

| Fala | Ação |
|------|------|
| "Para" / "Parar" / "Pare" | Para a história e volta ao rosto acordado |
| "Próxima" | Pula para a próxima |
| "Volta" / "Voltar" | Volta para a anterior |

> O microfone também capta o áudio da história, então uma dessas palavras na narração pode disparar o comando.

## Arquivos

| Caminho | Conteúdo |
|---------|----------|
| `jose.py` | O assistente: microfone, transcrição, estados, histórias e o servidor do rosto (porta 8090) |
| `web/index.html` | Página do rosto (mesmas posições, cores e fontes da tela original) |
| `rostojose/` | Rostos 1920x1080: `joseacordado`, `joseouvindo`, `Josefechado`, `josehistoria`, `joseresponde` |
| `historinhas/` | Histórias `.mp3` (fora do git); o nome do arquivo vira o título |
| `requirements.txt` | Dependências Python |
