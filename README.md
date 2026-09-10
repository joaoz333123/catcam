# 🐱 CatCam AI Vision Monitor

Sistema autônomo, **100% local e gratuito** de monitoramento e visão computacional em tempo real para pets e detecção de objetos com **YOLO11**, aceleração **Intel OpenVINO** e suíte **Supervision**.

Projetado para operar com câmeras compatíveis com o ecossistema Tuya (como a **Positivo Smart Câmera 360° Bot**) com firmware de fábrica, sem custos de nuvem ou assinaturas de API.

---

## ✨ Principais Recursos

- **Zero Custo de Nuvem:** Operação 100% offline no seu computador local, sem envio de imagens para serviços externos.
- **Aceleração Intel OpenVINO:** Inferência ultrarrápida (~30 ms) otimizada para gráficos integrados **Intel Iris Xe** e processadores Intel Core, mantendo o computador frio e consumindo pouca energia.
- **Streaming WebRTC de Baixa Latência & Alta Fluidez:** Gateway de vídeo integrado via **go2rtc**, servindo WebRTC nativo (25–30 FPS) com aceleração por hardware de vídeo no navegador.
- **Overlay IA em Tempo Real (60 FPS):** Em vez de reencodar vídeo lento em MJPEG (que causa perda de quadros nos navegadores), o dashboard renderiza o stream nativo WebRTC a 30 FPS e projeta as caixas de detecção e zona de interesse através de uma camada vetorial acelerada por GPU a 60 FPS via WebSocket de baixa latência (<2ms).
- **Arquitetura Anti-Lag (Zero Buffer Delay):** Leitor de frames desacoplado em thread dedicada que descarta acúmulos de buffer RTSP, garantindo análise instantânea do momento presente.
- **Suíte Supervision Completa:**
  - `PolygonZone`: Delimitação precisa de áreas de interesse (caixa de areia, portão, vaga, etc.).
  - `ByteTrack`: Rastreamento contínuo com ID estável para evitar contagens duplicadas.
  - `TraceAnnotator` & `BoxAnnotator`: Rastro de movimento e enquadramento visual.
- **Multi-Modos de Detecção Selecionáveis:**
  - 🐱 **Gatos:** Monitoramento de pets e uso de caixa de areia.
  - 🚗 **Veículos:** Contagem de trânsito (carros, motos, ônibus e caminhões).
  - 👤 **Pessoas:** Segurança e monitoramento de passagens.
  - 🐶 **Cachorros** e todas as 80 classes do COCO Dataset.
- **Filtro de Cor Integrado:** Possibilidade de filtrar objetos por cor (ex: detectar e contar **apenas carros brancos**).
- **Taxa de Quadros Ajustável (FPS):** Controle dinâmico de 2 FPS (máxima economia) até 25 FPS (rastreamento ultra fluido).
- **Buffer de Suavização (Jitter Buffer):** Armazena uma fila contínua de quadros na memória com cadência uniforme para gravações de clipes e compatibilidade de feed.
- **Gravação Automática com Debounce:** Grava clipes em MP4 das visitas/eventos e salva no banco **SQLite** local.
- **Dashboard Web Moderno:** Interface visual com abas de transmissão instantânea (**Visão IA Fluida**, **Ao Vivo Puro** e **MJPEG Legado**), métricas ao vivo, histórico com player de vídeo modal e **editor interativo de ROI** para arrastar os vértices da zona diretamente na tela.
- **Inicialização em 1 Clique:** Scripts `.bat` para ligar e desligar todos os serviços sem complicações.

---

## 🏗️ Arquitetura do Sistema

```text
[ Câmera Positivo 360° Bot (App Tuya Smart) ]
                      │
                      │ Protocolo Tuya / RTSP
                      ▼
             [ go2rtc Gateway (Portas 1984 / 8554) ]
              ├──► WebRTC Stream (1984) ──► [ Dashboard Web (Porta 8000) ]
              │
              ▼ RTSP Local (rtsp://localhost:8554/cat_cam)
[ Worker Python: Anti-Lag Capture + Supervision + YOLO11n (OpenVINO) ]
    ├── Thread de Leitura: Consome RTSP sem buffer (Zero Latência)
    ├── Cadência de IA: 15 FPS (Configurável no Dashboard)
    ├── Detector: YOLO11n acelerado por Intel OpenVINO
    ├── Rastreamento: sv.ByteTrack (Persistência do ID do objeto)
    ├── Delimitação Espacial: sv.PolygonZone (Área configurável na tela)
    ├── Gravação do Evento: Grava clipe MP4 em /data/recordings/
    │
    ▼ Evento Finalizado (Debounce de saída)
[ Banco SQLite (/data/events.db) ]
    ▲
    │ Consulta de Histórico e Clipes
[ API FastAPI / Dashboard ] (Exibe Live Stream + Histórico + Player de Clipes + Editor de ROI)
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
pip install ultralytics openvino supervision fastapi "uvicorn[standard]" opencv-python aiofiles websockets
```

### 3. Baixar o Gateway de Vídeo (go2rtc)
Baixe o executável oficial para Windows da versão mais recente do [go2rtc (AlexxIT)](https://github.com/AlexxIT/go2rtc/releases/latest) e salve em:
`bin/go2rtc.exe`

### 4. Parear a Câmera e Configurar o Stream
1. No seu celular, instale o aplicativo gratuito oficial **Tuya Smart** (ícone laranja).
2. Crie uma conta usando seu e-mail e defina uma senha (evite botões de login social para permitir autenticação direta pela API).
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

## 🎮 Como Usar

### Inicialização Rápida (1 Clique):
Basta dar **dois cliques** no arquivo executável:
👉 **`scripts/iniciar_catcam.bat`**

O script irá:
1. Iniciar o gateway `go2rtc` em segundo plano.
2. Abrir automaticamente o Dashboard no navegador em `http://localhost:8000`.
3. Iniciar o servidor FastAPI e o detector de IA com aceleração OpenVINO.

### Para Encerrar:
Dê dois cliques no arquivo:
👉 **`scripts/parar_catcam.bat`**

---

## 🖥️ Usando o Dashboard Web

Acesse `http://localhost:8000` no seu navegador:

1. **Ajuste da Área de Interesse:**
   * Clique em **`📐 Ajustar Área de Interesse`**.
   * Arraste os 4 círculos nos cantos sobre a imagem da câmera para contornar a caixa de areia (ou a área da rua/vaga).
   * Clique em **`💾 Salvar Área`**.

2. **Configurações da Inteligência Artificial:**
   * Clique no botão **`⚙️ Configurações da IA`** no topo direito.
   * Escolha o objeto a ser detectado: **Gatos**, **Carros/Veículos**, **Pessoas**, etc.
   * Ative filtros de cor se desejar (ex: apenas carros brancos).
   * Ajuste o slider de FPS (2 a 25 FPS) para calibrar a fluidez do processamento.

3. **Histórico e Clipes de Vídeo:**
   * Toda vez que um objeto entra na zona demarcada e permanece por mais de 3 segundos, um clipe em MP4 é gravado.
   * Clique no botão **`▶️ Clipe`** em qualquer registro para assistir ao vídeo gravado diretamente no modal da página.

---

## 📁 Estrutura de Pastas

```text
catcam/
├── bin/                   # Executável do go2rtc (go2rtc.exe)
├── config/
│   ├── go2rtc.example.yaml# Modelo de configuração do gateway
│   ├── go2rtc.yaml        # Configuração com credenciais locais (ignorado no git)
│   └── roi_config.json    # Coordenadas da zona de interesse e parâmetros da IA
├── backend/
│   ├── database.py        # Módulo SQLite para persistência do histórico
│   ├── detector.py        # Worker de visão computacional (OpenVINO + Supervision)
│   └── main.py            # Servidor FastAPI e rotas de API
├── frontend/
│   └── index.html         # Dashboard moderno com WebRTC, métricas e canvas ROI
├── data/
│   ├── events.db          # Banco de dados SQLite de visitas
│   └── recordings/        # Clipes gravados em formato MP4
└── scripts/
    ├── iniciar_catcam.bat # Script de inicialização automática
    └── parar_catcam.bat   # Script de parada limpa dos processos
```

---

## 🛡️ Segurança e Privacidade

- **Proteção de Credenciais:** Arquivos com senhas e dados de rede (`config/go2rtc.yaml`, bancos SQLite e vídeos gravados) estão bloqueados no `.gitignore` para garantir que nenhuma informação pessoal seja enviada a repositórios públicos.
- **Processamento 100% Offline:** Nenhuma gravação, imagem ou telemetria é enviada para a nuvem da Positivo, Tuya ou provedores de IA.

---

## 📄 Licença

Este projeto está sob licença MIT. Sinta-se livre para usar, estudar e modificar!
