
## 1. OBJETIVO DO AGENTE

O fluxo opera **sem custos de API, sem nuvem externa e sem chatbot**:
1. O **go2rtc** atua como gateway de vídeo conectando à câmera Tuya e distribuindo WebRTC (para o navegador) e RTSP (para o processamento).
2. Um worker Python realiza a captura em tempo real sem atraso de buffer e processa a detecção com **YOLO11n**, acelerado pela GPU integrada **Intel Iris Xe (via OpenVINO)** a 1–2 FPS.
3. A suíte **Supervision (v0.30.2+)** gerencia a zona poligonal da caixa de areia (`PolygonZone`), rastreamento contínuo (`ByteTrack`) e gravação fluida do clipe da visita em MP4 (`VideoSink`).
4. Os eventos de visita (horário de entrada, saída, duração e clipe) são salvos em um banco **SQLite** local.
5. Uma interface web moderna em **FastAPI** (porta `8000`) exibe o stream ao vivo WebRTC, os clipes gravados e o histórico de visitas, além de permitir o ajuste visual da área da caixa de areia.

---

## 2. PARÂMETROS HOMOLOGADOS DA MÁQUINA (WINDOWS 11)

- **Processador:** Intel(R) Core(TM) i7-1185G7 @ 3.00GHz (4 Cores / 8 Threads).
- **GPU:** Intel(R) Iris(R) Xe Graphics (Aceleração via **OpenVINO** para execução na iGPU/CPU sem aquecimento).
- **Memória RAM:** 15.73 GB Total (~8.5 GB Livres).
- **Rede Local:** Interface Wi-Fi no IP `192.168.3.2` (Sub-rede `192.168.3.0/24`).
- **Portas Alocadas:**
  - `1984` — go2rtc API & Stream WebRTC (latência sub-segundo).
  - `8554` — go2rtc Gateway RTSP local para o detector.
  - `8000` — Dashboard Web & Backend FastAPI.
- **Versão de Python Requerida:** **Python 3.11 ou 3.12** (Versões consolidadas com instaladores binários de PyTorch, OpenCV e OpenVINO, evitando erros de compilação de C++).



## 4. ARQUITETURA TÉCNICA DO SISTEMA

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
    ├── Cadência de IA: 1 a 2 FPS (Economia máxima de energia)
    ├── Detector: YOLO11n acelerado por Intel OpenVINO (Filtro class_id == 15 ['cat'])
    ├── Rastreamento: sv.ByteTrack (Persistência do ID do felino)
    ├── Delimitação Espacial: sv.PolygonZone (Área configurável da Caixa de Areia)
    ├── Overlays Visuais:
    │     ├── sv.PolygonZoneAnnotator (Verde = livre / Vermelho = ocupada)
    │     ├── sv.BoxAnnotator e sv.LabelAnnotator (Destaque do gato com ID)
    │     └── sv.TraceAnnotator (Rastro de movimento)
    ├── Gravação do Evento: sv.VideoSink (Grava clipe MP4 fluido em /data/recordings/)
    │
    ▼ Evento Finalizado (Debounce de 5s após saída)
[ Banco SQLite (/data/events.db) ]
    ▲
    │ Consulta de Histórico e Clipes
[ API FastAPI / Dashboard ] (Exibe Live Stream + Histórico + Player de Clipes + Editor de ROI)
```

---

## 5. PLANO DE EXECUÇÃO DETALHADO

### ETAPA 1: Setup do Workspace e Ambiente Python (3.11 / 3.12)

1. **Estrutura de Pastas:**
   ```text
   catcam/
   ├── bin/             # Executável do go2rtc (go2rtc.exe)
   ├── config/          # go2rtc.yaml e roi_config.json
   ├── backend/         # API FastAPI, Banco SQLite e Worker de Visão Computacional
   ├── frontend/        # Interface Web (HTML5, CSS moderno, JS puro com WebRTC)
   ├── data/
   │   ├── events.db    # Banco de dados de histórico
   │   └── recordings/  # Clipes MP4 gravados das visitas
   └── scripts/         # Scripts de automação (.bat) para inicialização em 1 clique
   ```

2. **Criação do Ambiente Virtual:**
   - Verificar a presença de Python 3.11 ou 3.12 no sistema:
     `py -3.11 --version` ou `py -3.12 --version` ou `python --version`
   - Criar e ativar o ambiente virtual:
     `py -3.11 -m venv .venv` (ou versão compatível disponível)
     `.\.venv\Scripts\Activate.ps1`

3. **Instalação das Dependências Homologadas:**
   ```bash
   pip install --upgrade pip
   pip install ultralytics openvino supervision fastapi uvicorn[standard] opencv-python aiofiles
   ```
   *Nota: `openvino` compila e executa o YOLO11n na iGPU Intel Iris Xe sem depender de CUDA/NVIDIA.*

---

### ETAPA 2: Gateway de Vídeo go2rtc (Integração Tuya)

1. **Download do go2rtc:**
   - Baixar a versão executável estável para Windows x64 (`go2rtc.exe`) e salvar em `bin/go2rtc.exe`.

2. **Pareamento e Credenciais da Câmera:**
   - A câmera é pareada pelo aplicativo **Tuya Smart** (ou Smart Life) conectado à mesma rede Wi-Fi (`192.168.3.x`).
   - Obter o ID do dispositivo (`Device ID`) e as credenciais ou utilizar o assistente WebRTC do `go2rtc`.

3. **Configuração do `/config/go2rtc.yaml`:**
   ```yaml
   api:
     listen: ":1984"
   rtsp:
     listen: ":8554"
   webrtc:
     listen: ":8555"

   streams:
     cat_cam:
       # Suporta tuya:// com credenciais do app ou RTSP direto se ativado
       - "tuya://protect-us.ismartlife.me" # Ajustado com as credenciais obtidas no pareamento
   ```

4. **Validação:**
   - Iniciar `bin/go2rtc.exe -config config/go2rtc.yaml`.
   - Acessar `http://localhost:1984` no navegador e validar a exibição do vídeo ao vivo sem travas.

---

### ETAPA 3: Pipeline de Visão Computacional (Supervision + YOLO11n OpenVINO)

1. **Definição da Área da Caixa de Areia (`/config/roi_config.json`):**
   ```json
   {
     "polygon": [[150, 200], [550, 200], [550, 600], [150, 600]],
     "confidence_threshold": 0.5,
     "debounce_seconds": 5
   }
   ```

2. **Desenvolvimento do Worker Anti-Lag (`/backend/detector.py`):**
   - **Classe `FreshFrameReader`:** Thread paralela dedicada a ler continuamente o stream RTSP `rtsp://localhost:8554/cat_cam`, garantindo que o detector sempre pegue o frame atual instantâneo, com buffer zero.
   - **Aceleração OpenVINO:** Carregar o modelo `yolo11n.pt` e exportar/executar com formato `openvino` (`device='GPU'` ou `device='CPU'`), otimizado para o i7-1185G7 / Iris Xe.
   - **Integração Supervision:**
     - `sv.PolygonZone` alimentado pelas coordenadas do `roi_config.json`.
     - `sv.ByteTrack` para acompanhar o gato de forma estável.
     - Filtrar estritamente `class_id == 15` (`cat`).
     - `sv.PolygonZoneAnnotator` para feedback visual imediato (verde = livre, vermelho = ocupada).
     - `sv.BoxAnnotator` e `sv.LabelAnnotator` mostrando a confiança e o ID de rastreamento.
   - **Lógica de Visita e Gravação de Vídeo:**
     - Quando o gato entra na zona delimitada: inicia o contador de visita e o `sv.VideoSink` para salvar em `data/recordings/visita_{data_hora}.mp4`.
     - Quando o gato sai da zona e permanece ausente por **5 segundos contínuos (debounce)**: finaliza a gravação, calcula a duração e salva o registro no banco SQLite.

---

### ETAPA 4: Persistência de Dados (SQLite)

1. **Estrutura do Banco (`/data/events.db`):**
   - Criação automática da tabela `visits`:
     - `id` INTEGER PRIMARY KEY AUTOINCREMENT
     - `start_time` TEXT (Formato ISO: YYYY-MM-DD HH:MM:SS)
     - `end_time` TEXT
     - `duration_seconds` INTEGER
     - `video_filename` TEXT
     - `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
2. **Módulo de Acesso a Dados (`/backend/database.py`):**
   - Funções simples para inserir visita e listar visitas com filtros (Hoje, Ontem, Últimos 7 dias).

---

### ETAPA 5: Backend FastAPI e Dashboard Web Moderno

1. **Serviço Backend (`/backend/main.py`):**
   - Serve a página do frontend estática.
   - Endpoint `GET /api/visits`: Retorna o histórico de visitas em JSON.
   - Endpoint `GET /api/videos/{filename}`: Permite reproduzir ou baixar o clipe MP4 gravado.
   - Endpoint `GET /api/roi` e `POST /api/roi`: Lê e atualiza as coordenadas da caixa de areia dinamicamente sem reiniciar o sistema.
   - Endpoint `GET /api/status`: Retorna o status atual (Câmera online, Caixa Ocupada ou Livre).

2. **Frontend Responsivo e Bonito (`/frontend/index.html`):**
   - **Player WebRTC ao vivo:** Incorpora o stream de ultrabaixa latência vindo do `go2rtc` (porta `1984`).
   - **Card de Status em Tempo Real:** Indicador visual (badge verde "Caixa Livre" ou vermelho piscante "Gata na Caixa").
   - **Tabela Interativa:** Lista histórico de visitas com data, horário de entrada, horário de saída, duração e botão modal para assistir ao clipe gravado.
   - **Editor Visual da Zona (ROI):** Canvas sobreposto ao vídeo permitindo arrastar os 4 pontos para ajustar o retângulo da caixa de areia diretamente pela tela.

---
