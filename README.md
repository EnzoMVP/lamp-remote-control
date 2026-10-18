# LampRemote

Controle da lâmpada **Elgin 15W Smart Color** (Tuya, Wi‑Fi) pela bandeja do Windows, via rede local
(`tinytuya`), sem passar pela nuvem.

- Clique esquerdo no ícone abre o painel; clique fora ou `Esc` fecha.
- Clique direito: **Iniciar com o Windows** e **Sair**.
- Painel: liga/desliga, brilho, luz branca (temperatura quente ↔ frio), cor (matiz + saturação),
  4 cenas (Leitura, Relaxar, Foco, Noite), com uma lâmpada 3D que acende na cor atual.
- O ícone da bandeja mostra o estado: preenchido na cor da lâmpada (ligada), só contorno
  (desligada), apagado com ponto laranja (offline).
- Segue o tema claro/escuro do Windows.

## Estrutura

```
app/
  main.py             entrada: instância única, log, thread do worker, bandeja
  config.py           lê/valida %APPDATA%\LampRemote\config.json
  bulb_state.py       modelo de estado + codificação dos DPS Tuya (lógica pura)
  backends.py         TuyaBackend (tinytuya) e FakeBackend (modo demo/testes)
  bulb_worker.py      QThread: fila "último valor vence", polling, reconexão com backoff
  bulb_controller.py  ponte QML ↔ worker: atualização otimista + throttle dos sliders
  flyout.py           janela do painel: posicionamento sobre o ícone, foco, Esc
  tray.py             ícone dinâmico da bandeja + menu
  autostart.py        "Iniciar com o Windows" (registro HKCU\...\Run)
  lathe.py            geometria 3D da lâmpada (perfil revolucionado)
  import_devices.py   gera o config.json a partir do devices.json do wizard
  qml/                interface (Flyout, Bulb3D, sliders, tiles, tema)
tests/                testes (lógica, worker em thread real, interação com o painel)
LampRemote.spec       build do PyInstaller
```

## 1. Ambiente de desenvolvimento

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m app --demo     # abre com uma lâmpada simulada
.venv\Scripts\python -m pytest         # testes
```

## 2. Obter ID, IP, versão e local key

### 2.1 Achar a lâmpada na rede

```powershell
.venv\Scripts\python -m tinytuya scan
```

Deve aparecer algo como `Elgin ... Product ID = ... [Valid Broadcast]: Address = 192.168.0.xx
Device ID = eb... Local Key = ... Version = 3.3`. Anote o **IP**, o **Device ID** e a **Version**.

> **A lâmpada não aparece no scan?** Confira, nesta ordem:
>
> 1. O interruptor da parede está ligado? Desligada no interruptor, a lâmpada some da rede.
> 2. Ela aparece **online** no app (Smart Life / Tuya Smart / app do fabricante)?
> 3. Ela está no **mesmo roteador** que o PC? A lâmpada só usa 2,4 GHz. Se o roteador tem
>    redes separadas (ex.: `MinhaRede` e `MinhaRede_5G`), tudo bem: o PC pode ficar no 5 GHz e a
>    lâmpada no 2,4 GHz, porque as duas redes são do mesmo roteador. Agora, se a lâmpada estiver
>    no Wi‑Fi de **outro** aparelho (ex.: o modem da operadora, com o PC num segundo roteador),
>    elas ficam em sub‑redes diferentes e o controle local **não funciona**. Para mudar o Wi‑Fi
>    da lâmpada, remova‑a do app, resete (desligue e ligue 3 vezes no interruptor até piscar
>    rápido) e adicione de novo escolhendo a rede certa.
> 4. A rede não pode ser de **convidados** nem ter **isolamento de clientes (AP isolation)**.
> 5. Com o Wi‑Fi do PC no perfil **Público**, o Firewall do Windows bloqueia os anúncios UDP
>    usados pelo scan. Mude para **Privada**: *Configurações → Rede e Internet → Wi‑Fi →
>    (sua rede) → Tipo de perfil de rede*.

### 2.2 Gerar a local key com o wizard

A local key vem da nuvem Tuya, e só é preciso buscá‑la uma vez.

1. Crie uma conta em <https://platform.tuya.com> (antigo iot.tuya.com).
2. **Cloud → Development → Create Cloud Project**: Industry *Smart Home*, Development Method
   *Smart Home*, Data Center **Western America** (contas do Brasil normalmente ficam nele).
3. Aceite os serviços de API sugeridos (IoT Core, Authorization etc.).
4. No projeto, aba **Devices → Link App Account → Add App Account**: aparece um QR code.
   Abra o app no celular → *Eu/Perfil* → ícone de escanear (canto superior) → leia o QR.
   - O vínculo oficial funciona com **Smart Life** ou **Tuya Smart**. O app **Elgin Smart**
     pode não conseguir ler esse QR. Nesse caso, instale o Smart Life, remova a lâmpada do app
     Elgin e pareie de novo pelo Smart Life (a local key muda quando a lâmpada é pareada de novo).
5. Na aba **Overview**, copie o **Access ID/Client ID** e o **Access Secret**.
6. Na pasta do projeto:
   ```powershell
   .venv\Scripts\python -m tinytuya wizard
   ```
   Informe o ID e o Secret, a região `us`, e o Device ID da lâmpada (aparece em *Devices* no
   site). Responda **Y** para escanear a rede local. São gerados `devices.json`,
   `snapshot.json` e `tinytuya.json`.

   **Não compartilhe esses arquivos**: eles contêm a local key e o segredo da API (já estão
   no `.gitignore`).

Se o wizard não listar dispositivos, o data center escolhido provavelmente não é o da sua conta.
Crie o projeto em outra região (por exemplo *Eastern America*) e tente de novo. O plano IoT Core
gratuito expira em 1 mês, mas ele só é necessário para buscar a key. O controle local não depende
da nuvem.

### 2.3 Criar o config

```powershell
.venv\Scripts\python -m app.import_devices devices.json snapshot.json
```

Isso grava `%APPDATA%\LampRemote\config.json`. Se preferir fazer à mão, use o
`config.example.json` como modelo:

```json
{ "id": "eb...", "ip": "192.168.0.50", "local_key": "16 caracteres", "version": 3.3, "name": "Elgin Smart Color" }
```

Dica: reserve o IP da lâmpada no roteador (DHCP estático). Se o IP mudar mesmo assim, o app tenta
achar a lâmpada pelo ID na rede e atualiza o config sozinho.

## 3. Gerar o executável

```powershell
.venv\Scripts\python tools\make_icon.py
.venv\Scripts\pyinstaller LampRemote.spec --noconfirm
```

O resultado fica em `dist\LampRemote\` (pasta com ~155 MB; o `LampRemote.exe` fica dentro dela).
O build é em pasta, e não em arquivo único, porque abre bem mais rápido: o modo "onefile"
descompactaria o Qt inteiro a cada inicialização.

## 4. Instalar e usar

1. Copie a pasta `dist\LampRemote` para `%LOCALAPPDATA%\Programs\LampRemote`
   (ou outro lugar fixo; a opção de iniciar com o Windows aponta para esse caminho).
2. Rode `LampRemote.exe`. O ícone aparece na bandeja.
3. **Windows 11 esconde ícones novos** no menu `^`. Para deixá‑lo sempre visível: *Configurações
   → Personalização → Barra de tarefas → Outros ícones da bandeja → LampRemote: Ativado*
   (ou arraste o ícone do `^` para a barra).
4. Clique direito → **Iniciar com o Windows**.

Para atualizar: clique direito → Sair, substitua a pasta e abra de novo. Se você moveu a pasta,
marque "Iniciar com o Windows" outra vez.

## Solução de problemas

- **Log**: `%APPDATA%\LampRemote\lampremote.log`.
- **"Local key ou versão incorreta"**: a key mudou (a lâmpada foi pareada de novo) ou a versão
  está errada. Rode o wizard de novo e regenere o config.
- **"Lâmpada inacessível"**: veja a seção 2.1. O app continua tentando reconectar
  (1 s → 2 s → 5 s … até 30 s) e o botão "Tentar agora" força uma nova tentativa.
- **Só um app por vez**: a lâmpada aceita poucas conexões locais simultâneas. Se o app do celular
  ou o Home Assistant estiverem conectados localmente, pode haver falhas intermitentes.

## Decisões técnicas

- **PySide6 + Qt Quick (QML)**: cantos, sombras, animações e controles customizados ficam
  naturais em QML. O **Qt Quick 3D** já vem junto, então a lâmpada 3D é renderizada em tempo
  real (sólido de revolução gerado em `lathe.py`) na mesma pilha, sem imagens pré‑renderizadas.
- **Fonte Bahnschrift**: é a DIN que já vem no Windows, a mesma família visual da referência.
- **Threads**: toda chamada de rede acontece no `BulbWorker` (QThread). A UI só emite sinais.
- **Sliders**: atualização otimista na tela. Os comandos saem com *throttle* (no máximo 1 a cada
  150 ms durante o arraste, com envio imediato ao soltar) e o worker junta comandos pendentes
  (o último valor vence). Arrastar o slider de ponta a ponta gera poucos comandos, e o valor
  final sempre chega à lâmpada. Leituras da lâmpada não sobrescrevem um controle que você mexeu
  nos últimos 2 s, então o slider não "pula de volta".
- **Erros**: falhas viram um estado discreto no painel (topo "Offline", rodapé com contagem e
  "Tentar agora"), com reconexão automática em backoff. Após 3 falhas, o app procura a lâmpada
  pelo ID na rede, caso o IP tenha mudado.
