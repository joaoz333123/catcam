# 🐱 CatCam AI Vision Monitor

Sistema autônomo, **100% local e gratuito** de monitoramento e visão computacional em tempo real para pets e detecção de objetos com **YOLO11**, aceleração **Intel OpenVINO** e suíte **Supervision**.

Projetado para operar com câmeras compatíveis com o ecossistema Tuya (como a **Positivo Smart Câmera 360° Bot**) com firmware de fábrica, sem custos de nuvem ou assinaturas de API.

---

## ✨ Principais Recursos

- **Zero Custo de Nuvem:** Operação 100% offline no seu computador local, sem envio de imagens para serviços externos.
- **Acesso Seguro com Senha (Protegido contra F12/Inspecionar):** Autenticação robusta no backend em Python via hash criptográfico SHA-256 + salt exclusivo e cookies `HttpOnly` com validade de 30 dias. Nenhum segredo ou verificação de senha fica exposto no código JavaScript do frontend. Todas as rotas de API, histórico, WebSockets e streaming de vídeo exigem autenticação ativa.
- **Acesso Simultâneo Local e Remoto (Internet):** Acesse simultaneamente via rede local (`http://localhost:8000` ou IP local) e pela internet (via túnel seguro criptografado com TLS/HTTPS) de qualquer lugar do mundo (4G/5G/Wi-Fi externo) sem necessidade de abrir portas no roteador.
- **Aceleração Intel OpenVINO:** Inferência ultrarrápida (~30 ms) otimizada para gráficos integrados **Intel Iris Xe** e processadores Intel Core, mantendo o computador frio e consumindo pouca energia.
- **Streaming WebRTC de Baixa Latência & Alta Fluidez:** Gateway de vídeo integrado via **go2rtc**, servindo WebRTC nativo (25–30 FPS) com aceleração por hardware de vídeo no navegador.
- **Overlay IA em Tempo Real (60 FPS):** O dashboard renderiza o stream nativo WebRTC a 30 FPS e projeta as caixas de detecção e zona de interesse através de uma camada vetorial acelerada por GPU a 60 FPS via WebSocket de baixa latência (<2ms).
- **Indicador de FPS Real no Player:** Badge em tempo real sobreposto ao vídeo com monitoramento contínuo nas 3 abas de transmissão:
  - ⚡ **Visão IA (WebRTC Fluido):** Medição de FPS da renderização cliente + telemetria do detector.
  - 📹 **Ao Vivo Puro:** Taxa de quadros do stream WebRTC nativo com aceleração de hardware.
  - 🎞️ **Feed MJPEG:** Taxa de quadros do stream de buffer do detector.
- **Modo Tela Cheia (Fullscreen) Nativo:** Botão integrado no player para expandir a transmissão para tela inteira com redimensionamento vetorial dinâmico do overlay e das áreas demarcadas.
- **Configurações Integradas na Tela Principal com Auto-Save:** Painel de controle diretamente acessível na lateral do vídeo com salvamento automático e feedback visual instantâneo (`✓ Salvo automaticamente`), sem necessidade de modais ou botões manuais.
- **Painel de Histórico & Gravações em Largura Total:** Bloco de eventos posicionado na parte inferior da interface, oferecendo ampla visibilidade dos clipes gravados com filtros temporais (Hoje, Ontem, 7 Dias, Todas) e player modal.
- **Contadores de Movimentações por Alvo no Topo:** Barra dinâmica no topo do dashboard com a contagem instantânea de registros do dia agrupados por alvo configurado (**Beatriz**, **Serena**, **Ambos**, **Pessoas**, etc.).
- **Seleção de Alvos via Checkboxes Múltiplos:** Formato prático de seleção simultânea em caixas de marcação:
  - `[x] 🧡 Beatriz (Gata Amarela / Laranja)`
  - `[x] 🩶 Serena (Gata Cinza)`
  - `[ ] 🐱 Outro Gato / Qualquer Gato`
  - `[ ] 👤 Pessoas`
  - `[ ] 🚗 Veículos`
  - `[ ] 🐶 Cachorros`
- **Multi-Select de Classes Adicionais (80 Objetos COCO):** Seletor interativo para adicionar objetos extras à busca (como Ônibus, Bicicletas, Mochilas, Pássaros, Barcos, etc.) exibidos em tags dinâmicas removíveis (`[Ônibus ✕]`).
- **Identificação Individual de Pets (Beatriz vs. Serena):** Reconhecimento cromático em tempo real via análise HSV que identifica quem visitou a área demarcada e grava no histórico (**Beatriz**, **Serena** ou **Ambos**).
- **Notificações Push com Foto no Celular (ntfy.sh):** Disparo em tempo real de alerta push nativo no seu smartphone (Android/iOS) com a foto anotada do momento exato em que o alvo (Beatriz, Serena, etc.) entrou na área demarcada, com link de toque para abrir a live.
- **Proxy Reverso Unificado:** Toda a comunicação de vídeo WebRTC/MSE, WebSockets e API passa por uma única porta (`8000`), garantindo 100% de compatibilidade tanto local quanto remota.
- **Notificações Imediatas com Balão do Windows & Chime Sonoro:** Disparo instantâneo de alerta sonoro e notificação nativa no canto da tela do Windows assim que qualquer alvo configurado (ex: Beatriz, Serena, Pessoas, etc.) entra na área demarcada, com link direto para o dashboard.
- **Botão Liga/Desliga de Notificações no Painel:** Chave toggle integrada diretamente no painel de configurações para pausar ou reativar alertas sonoros e notificações a qualquer momento, salvo automaticamente.
- **Rastreamento Anti-Flicker com Interpolação Lerp:** Elimina caixas piscando ou sumindo entre frames; a caixa acompanha o alvo com interpolação contínua a 60 FPS e persistência de 650ms.
- **Filtro de Cor Integrado:** Possibilidade de filtrar objetos por cor (ex: detectar e contar **apenas carros brancos**).
- **Taxa de Quadros Ajustável (FPS):** Controle dinâmico de 2 FPS (máxima economia) até 25 FPS (rastreamento ultra fluido).
- **Gravação Automática com Conversão Web H.264:** Grava clipes em MP4 das visitas/eventos, converte automaticamente em background para H.264 com `+faststart` (reprodução nativa imediata no navegador sem erros MIME) e persiste no banco **SQLite** local.
- **Suíte Supervision Completa:**
  - `PolygonZone`: Delimitação precisa de áreas de interesse (caixa de areia, portão, vaga, etc.).
  - `ByteTrack`: Rastreamento contínuo com ID estável para evitar contagens duplicadas.
  - `TraceAnnotator` & `BoxAnnotator`: Rastro de movimento e enquadramento visual.
- **Inicialização em 1 Clique:** Scripts `.bat` para ligar, desligar e iniciar o acesso local ou remoto sem complicações.

---

## 🏗️ Arquitetura do Sistema

```text
[ Câmera Positivo 360° Bot (App Tuya Smart) ]
                      │
                      │ Protocolo Tuya / RTSP
                      ▼
             [ go2rtc Gateway (Portas 1984 / 8554) ]
              ├──► WebRTC Stream (1984) ──► [ Dashboard Web (Porta 8000) ]
              │                                      ▲
              ▼ RTSP Local (rtsp://localhost:8554/cat_cam) │ Proxy Reverso + Auth (Cookie HttpOnly)
[ Worker Python: Anti-Lag Capture + Supervision + YOLO11n (OpenVINO) ]
    ├── Thread de Leitura: Consome RTSP sem buffer (Zero Latência)
    ├── Cadência de IA: 15–25 FPS (Ajuste dinâmico no Dashboard com Auto-Save)
    ├── Detector: YOLO11n acelerado por Intel OpenVINO (Classes filtradas dinamicamente)
    ├── Rastreamento: sv.ByteTrack (Persistência do ID do objeto)
    ├── Delimitação Espacial: sv.PolygonZone (Área configurável na tela)
    ├── Classificação Cromática: Análise HSV em tempo real (Beatriz vs. Serena)
    ├── Alerta Push: Disparo imediato via ntfy.sh com foto anexada
    ├── Gravação do Evento: Grava clipe MP4 e converte em H.264 Web (+faststart)
    │
    ▼ Evento Finalizado (Debounce de saída)
[ Banco SQLite (/data/events.db) ]
    ▲
    │ Consulta de Histórico, Métricas e Clipes
[ API FastAPI / Dashboard ] (Live Stream + Fullscreen + Contadores + Auto-Save + ROI + Login Seguro)
```

---

## 📋 Pré-requisitos

- **Sistema Operacional:** Windows 10/11 (ou Linux x64)
- **Processador:** Intel Core de 11ª geração ou superior (com GPU Intel Iris Xe recomendada)
- **Python:** Versão 3.11, 3.12 ou 3.14 (64-bit)
- **Câmera:** Positivo Smart Câmera 360° Bot ou qualquer câmera compatível com a plataforma Tuya
- **Rede Local:** Câmera e computador conectados na mesma rede Wi-Fi

---

## 🚀 Como Instalar e Rodar

### 1. Clonar o Repositório
```bash
git clone https://github.com/joaoz333123/catcam.git
cd catcam
```

### 2. Configurar o Ambiente Virtual Python
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install ultralytics openvino supervision fastapi "uvicorn[standard]" opencv-python aiofiles websockets winotify requests
```

### 3. Baixar o Gateway de Vídeo (go2rtc)
Baixe o executável oficial para Windows da versão mais recente do [go2rtc (AlexxIT)](https://github.com/AlexxIT/go2rtc/releases/latest) e salve em:
`bin/go2rtc.exe`

### 4. Parear a Câmera e Configurar o Stream
1. No celular, instale o aplicativo gratuito oficial **Tuya Smart** (ícone laranja).
2. Crie uma conta usando seu e-mail e defina uma senha.
3. Resete a câmera e pareie-a pelo QR Code no app Tuya Smart na mesma rede Wi-Fi do computador.
4. Crie seu arquivo de configuração local a partir do exemplo:
   * Copie o arquivo `config/go2rtc.example.yaml` para `config/go2rtc.yaml`.
   * Preencha com o ID virtual da sua câmera (visível em *Informações do Dispositivo* no app Tuya), seu e-mail e senha:
   ```yaml
   streams:
     cat_cam:
       - "tuya://protect-us.ismartlife.me?device_id=SEU_DEVICE_ID&email=seu_email@dominio.com&password=SUA_SENHA"
   ```
   *(Nota: `config/go2rtc.yaml` é ignorado pelo `.gitignore` para proteger suas credenciais).*

---

## 🔒 Segurança e Senha de Acesso

O sistema conta com um módulo de autenticação integrado:
- **Senha Padrão Inicial:** `catcam2026`
- **Como alterar a senha:**
  1. Copie `config/auth.example.json` para `config/auth.json` (se ainda não existir).
  2. O CatCam gera automaticamente o hash SHA-256 e o salt na primeira inicialização.
  3. Para trocar a senha via terminal, execute:
     ```bash
     python -c "from backend.auth import auth_manager; auth_manager.set_password('SUA_NOVA_SENHA_AQUI')"
     ```
  4. Ou altere pela própria API autenticada em `POST /api/auth/change-password`.
- **Privacidade Absoluta:** O arquivo `config/auth.json` nunca é enviado ao GitHub (está devidamente listado no `.gitignore`).

---

## 📲 Notificações no Celular com Foto (ntfy.sh)

Para receber alertas push no smartphone sempre que o pet entrar na área:
1. Instale o app **ntfy** (disponível gratuitamente na Google Play Store e Apple App Store).
2. No app, clique no botão **`+`** para se inscrever em um tópico.
3. Escolha um nome exclusivo para o tópico (exemplo: `catcam_beatriz_99812`).
4. No arquivo `config/roi_config.json`, configure o campo `"ntfy_topic"` com o mesmo nome do tópico:
   ```json
   {
     "ntfy_topic": "catcam_beatriz_99812"
   }
   ```
5. Pronto! Você receberá alertas push instantâneos com a foto capturada pela IA.

---

## 🌐 Acesso Remoto pela Internet

O CatCam suporta acesso simultâneo pela rede local e pela internet.

Para gerar uma URL pública com HTTPS sem abrir portas no roteador:
```powershell
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run
```
Ou utilizando o **Cloudflare Tunnel** (gratuito) ou **Tailscale**.
Ao abrir o link no celular ou outro computador, a tela de login seguro será exibida solicitando a senha.

---

## 🎮 Como Usar

### Inicialização Rápida:
Execute no terminal ou crie um atalho para:
```powershell
# Iniciar o gateway go2rtc
.\bin\go2rtc.exe -config config\go2rtc.yaml

# Em outro terminal, iniciar o backend CatCam
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Acesse `http://localhost:8000` no seu navegador.

### Encerrar:
Basta pressionar `Ctrl+C` nos terminais correspondentes.

---

## 🖥️ Usando o Dashboard Web

1. **Autenticação:**
   * Digite a senha de acesso (padrão: `catcam2026`). O dashboard será desbloqueado e a sessão permanecerá ativa por 30 dias.
   * Para deslogar, utilize o botão **`🔒 Sair`** no canto superior direito.

2. **Ajuste da Área de Interesse (ROI):**
   * Clique em **`📐 Ajustar Área de Interesse`**.
   * Arraste os 4 círculos nos cantos sobre a imagem da câmera para contornar a caixa de areia ou área monitorada.
   * Clique em **`💾 Salvar Área`**.

3. **Configuração de Alvos e Auto-Save:**
   * No painel lateral direito, marque os alvos desejados através dos **Checkboxes** (Beatriz, Serena, Pessoas, Veículos, etc.).
   * Para incluir outras classes, selecione no menu **Adicionar Outros Itens** (80 classes do COCO) e clique em `➕ Adicionar`.
   * Ajuste FPS, sensibilidade e debounce. Todas as alterações são salvas automaticamente no mesmo instante.

4. **Modo Tela Cheia:**
   * Clique no botão **`⛶ Tela Cheia`** no canto inferior direito do vídeo para visualizar em tela cheia.

5. **Histórico e Clipes de Vídeo:**
   * Toda vez que um objeto configurado entra na zona demarcada e permanece por mais de 3 segundos, um clipe em MP4 H.264 é gravado.
   * Clique no botão **`▶️ Clipe`** para assistir ao vídeo gravado no próprio navegador.

---

## 📁 Estrutura de Pastas

```text
catcam/
├── bin/                    # Executável do go2rtc (go2rtc.exe)
├── config/
│   ├── auth.example.json   # Modelo de configuração de autenticação (público)
│   ├── auth.json           # Senha e credenciais criptografadas locais (ignorado no git)
│   ├── go2rtc.example.yaml # Modelo de configuração do gateway (público)
│   ├── go2rtc.yaml         # Configuração com credenciais Tuya locais (ignorado no git)
│   └── roi_config.json     # Coordenadas da zona de interesse, alvos e parâmetros da IA
├── backend/
│   ├── auth.py             # Módulo de autenticação segura, SHA-256 + salt e cookies HttpOnly
│   ├── database.py         # Módulo SQLite para persistência e agregação do histórico
│   ├── detector.py         # Worker de visão computacional (OpenVINO + Supervision + HSV + ntfy)
│   └── main.py             # Servidor FastAPI com rotas protegidas, WebSockets e proxy reverso
├── frontend/
│   └── index.html          # Dashboard moderno com WebRTC, Fullscreen, Auto-Save, Canvas e Modal Auth
├── data/
│   ├── events.db           # Banco de dados SQLite de visitas (ignorado no git)
│   └── recordings/         # Clipes gravados em formato MP4 (H.264) (ignorado no git)
└── scripts/
    ├── iniciar_catcam.bat  # Script de inicialização automática
    └── parar_catcam.bat    # Script de parada limpa dos processos
```

---

## 🛡️ Segurança e Privacidade

- **Proteção Absoluta de Credenciais:** Arquivos sensíveis (`config/auth.json`, `config/go2rtc.yaml`, bancos SQLite `data/events.db` e vídeos gravados `data/recordings/`) estão devidamente bloqueados no `.gitignore` para garantir que nenhuma informação pessoal ou chave seja enviada a repositórios públicos.
- **Processamento 100% Local:** Nenhuma gravação, imagem ou telemetria é enviada para servidores de terceiros ou nuvens de IA.
- **Blindagem no Frontend:** Toda a verificação de acesso é executada no backend; inspecionar o código-fonte via DevTools (F12) não revela senhas nem permite burlar a proteção dos streams.

---

## 📄 Licença

Este projeto está sob licença MIT. Sinta-se livre para usar, estudar e modificar!
