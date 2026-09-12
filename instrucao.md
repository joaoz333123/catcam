# 🐱 CatCam AI Monitor — Manual de Arquitetura Técnica e Metodologia Operacional

---

## 1. VISÃO GERAL E FLUXO OPERACIONAL

O **CatCam AI Monitor** é um sistema autônomo, **100% local, privado e sem custos de API ou assinaturas de nuvem**, projetado para monitoramento contínuo, visão computacional e inteligência comportamental de pets (especificamente calibrado para as gatas **Beatriz** e **Serena**). O sistema opera sobre a seguinte cadeia de processamento:

```text
[ Câmera Tuya / Positivo 360° Bot ] (Wi-Fi Local)
                   │
                   │ Protocolo Tuya / RTSP Nativo
                   ▼
       [ go2rtc Gateway de Vídeo ] (bin/go2rtc.exe)
        ├── RTSP Local (rtsp://localhost:8554/cat_cam) ──► [ Worker de IA (detector.py) ]
        └── API / WebRTC (127.0.0.1:1984) ◄── (Proxy Reverso Interno via httpx/websockets)
                                                              │
                                                              ▼
                                               [ Backend FastAPI (Porta 8000) ]
                                                ├── Autenticação Server-Side (SHA-256 + Salt)
                                                ├── WebSocket Telemetria 60 FPS (/ws/detections)
                                                ├── Proxy Reverso WebRTC & Streams (/go2rtc/...)
                                                ├── API REST de ROI, Métricas e Gravações
                                                └── Notificações Push (ntfy.sh c/ Foto + Windows Toast)
                                                              │
                     ┌────────────────────────────────────────┴────────────────────────────────────────┐
                     ▼                                                                                 ▼
         [ Frontend Web Moderno ]                                                          [ Acesso Remoto Seguro ]
   - Stream WebRTC Sub-segundo                                                        - Túnel SSH (localhost.run / HTTPS)
   - Overlay Vetorial IA (Canvas 60 FPS)                                              - Unificado na Porta 8000
   - Editor Visual de Polígono Normalizado                                            - QR Code Dinâmico no Painel
   - Player H.264 c/ Scrubbing e Histórico SQLite
```

1. **Ingestão e Gateway de Vídeo:** O executável **go2rtc** conecta diretamente à câmera Tuya (firmware original de fábrica via protocolo Tuya ou RTSP local), distribuindo o fluxo em WebRTC (para visualização no navegador) e RTSP de baixa latência (para processamento de IA).
2. **Worker Anti-Lag com Zero Latência:** Um leitor dedicado (`FreshFrameReader`) em thread separada consome continuamente o RTSP sem buffer (`CAP_PROP_BUFFERSIZE = 1` e transporte TCP), garantindo que o detector processe apenas o quadro presente instantâneo, descartando acúmulo de atraso.
3. **Inferência Ultralytics YOLO11n + Intel OpenVINO:** Detecção em tempo real acelerada na GPU integrada **Intel Iris Xe** ou CPU i7, operando em cadência suave configurável (**8 a 12 FPS**) com controle rigoroso de concorrência OpenMP para eliminar o aquecimento por spin-wait.
4. **Suíte Supervision (v0.30.2):** Rastreamento de objetos persistente (`sv.ByteTrack`), controle espacial poligonal da caixa de areia (`sv.PolygonZone` com coordenadas normalizadas) e anotações visuais dinâmicas.
5. **Classificação Cromática Individual dos Pets (HSV):** Módulo especialista que analisa a assinatura cromática do animal recortado (Beatriz = pelagem amarela/laranja com dominância de canal vermelho vs. Serena = cinza neutro ou cinza-ardósia/azul britânico), com detecção automática de modo noturno infravermelho.
6. **Gravação Sincronizada em Velocidade Real (H.264 Web 1.0x):** Gravação automática de eventos de visita através de `cv2.VideoWriter`, seguida de transcodificação assíncrona via `ffmpeg` (`libx264`, `pix_fmt yuv420p`, `+faststart`) com sincronização da taxa de quadros real (`real_fps`), eliminando aceleração e permitindo reprodução com scrubbing em qualquer navegador.
7. **Notificações em Tempo Real:** Disparo instantâneo via **ntfy.sh** direto no smartphone com foto anotada e link para a live stream, somado a notificações nativas do Windows 11 via **winotify**.
8. **Persistência de Dados (SQLite):** Registro detalhado das visitas na tabela `visits` em `data/events.db` (horário de entrada, saída, duração, arquivo de vídeo e identificação do visitante).
9. **Proxy Reverso Unificado & Segurança:** O backend FastAPI (porta `8000`) atua como proxy reverso transparente para o go2rtc, unificando WebRTC, WebSocket de telemetria, APIs e arquivos sob uma única porta protegida por autenticação server-side (cookie HttpOnly).
10. **Operação em Segundo Plano no Windows:** Executável invisível com **System Tray** (`catcam_tray.py` via `pythonw.exe`), atalho no Desktop e gerenciamento completo de inicialização e parada limpa.

---

## 2. PARÂMETROS HOMOLOGADOS DA MÁQUINA (WINDOWS 11)

- **Processador:** Intel(R) Core(TM) i7-1185G7 @ 3.00GHz (4 Núcleos / 8 Threads).
- **GPU Integrada:** Intel(R) Iris(R) Xe Graphics (Aceleração via **OpenVINO**).
- **Memória RAM:** 16 GB DDR4/LPDDR4x.
- **Rede Local:** Sub-rede `192.168.3.0/24` (IP do host servidor: `192.168.3.2`).
- **Alocação de Portas e Serviços:**
  - `8000` — **Porta Única de Entrada Pública e Local:** Dashboard Web, API REST, WebSockets e Proxy Reverso do go2rtc (WebRTC / Streams).
  - `1984` — go2rtc API & WebRTC Gateway (acessado internamente pelo servidor FastAPI em `127.0.0.1:1984`).
  - `8554` — go2rtc Gateway RTSP local (`rtsp://localhost:8554/cat_cam`).
  - `8555` — go2rtc WebRTC signaling port.
- **Ambiente Python Homologado:** **Python 3.14.2 / 3.12** configurado no ambiente virtual `.venv` local com pacotes pré-compilados.

---

## 3. PILHA TECNOLÓGICA E DEPENDÊNCIAS HOMOLOGADAS

| Componente | Biblioteca / Ferramenta | Versão Homologada | Finalidade Técnica |
| :--- | :--- | :--- | :--- |
| **Framework Web** | `fastapi` | `0.141.1` | Roteamento assíncrono, injeção de dependências, endpoints REST e WebSockets. |
| **Servidor ASGI** | `uvicorn[standard]` | `0.52.4` | Servidor HTTP/WebSocket de alta performance com uvloop e httptools. |
| **Visão / IA** | `ultralytics` | `8.4.148` | Execução do modelo YOLO11n com exportação e inferência OpenVINO. |
| **Runtime de IA** | `openvino` | `2026.3.1` | Compilação e execução otimizada do grafo YOLO na CPU/iGPU Intel Iris Xe. |
| **CV Toolkit** | `supervision` | `0.30.2` | `PolygonZone`, `ByteTrack`, `TraceAnnotator`, `BoxAnnotator` e `LabelAnnotator`. |
| **Processamento Imagem** | `opencv-python` | `5.0.0.93` | Leitura RTSP com captura TCP, redimensionamento, análise de canais HSV e gravação. |
| **Transcodificação** | `ffmpeg` (CLI) | Estável (Path) | Conversão para codec H.264 (avc1), yuv420p, faststart e sincronização de 1.0x FPS real. |
| **Cliente Proxy** | `httpx` | `0.28.1` | Proxy reverso assíncrono transparente para rotas HTTP do go2rtc. |
| **WebSocket Proxy** | `websockets` | `17.1` | Túnel bidirecional de sinalização WebRTC entre frontend e go2rtc. |
| **Notificações Push** | `requests` / `ntfy.sh` | `2.34.2` | Disparo HTTP PUT com payload de imagem JPEG anotada e headers de controle. |
| **Notificações Desktop** | `winotify` | `1.1.0` | Disparo de notificações Toast nativas do Windows 11 com áudio e botão interativo. |
| **System Tray** | `pystray` + `Pillow` | `0.19.5` / `12.3.0` | Ícone na barra de tarefas do Windows, menu de contexto e controle de serviços. |
| **QR Code** | `qrcode[pil]` | `8.2` | Geração dinâmica de QR Code PNG no endpoint `/api/qrcode` para pareamento móvel. |
| **Persistência** | `sqlite3` (Nativo) | Embutido | Banco de dados relacional transacional em `data/events.db`. |

---

## 4. OTIMIZAÇÕES CRÍTICAS DE HARDWARE E RUNTIME

A estabilidade em regime contínuo (24/7) depende de configurações rigorosas no topo dos módulos `main.py` e `detector.py`:

### 4.1. Eliminação do Spin-Wait de CPU (Intel OpenMP / oneTBB)
Por padrão, bibliotecas de deep learning com OpenMP mantêm threads ativas em spin-wait após cada inferência, causando consumo de 400% a 600% de CPU com a máquina ociosa. O CatCam anula essa anomalia:
```python
os.environ["KMP_BLOCKTIME"] = "0"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
```
Isso força a suspensão imediata das threads de cálculo no milissegundo em que a inferência termina, mantendo o consumo de CPU em níveis mínimos (~5% a 15%).

### 4.2. Limitação de Concorrência e Afinidade OpenVINO
Para impedir saturação dos núcleos de cálculo do i7-1185G7 e reservar largura de banda para o streaming WebRTC e renderização:
```python
import openvino as ov
_orig_ov_core_init = ov.Core.__init__
def _custom_ov_core_init(self, *args, **kwargs):
    _orig_ov_core_init(self, *args, **kwargs)
    try:
        self.set_property("CPU", {"INFERENCE_NUM_THREADS": 2, "ENABLE_CPU_PINNING": False})
    except Exception:
        pass
ov.Core.__init__ = _custom_ov_core_init
```

---

## 5. ESTRUTURA DO WORKSPACE E DIRETÓRIOS

```text
catcam/
├── assets/                  # Ícones visuais (.png, .ico) para bandeja e atalhos
├── bin/
│   └── go2rtc.exe           # Executável do gateway de vídeo WebRTC/RTSP
├── config/
│   ├── auth.json            # Hash SHA-256 e sal da senha de acesso (ignorado no git)
│   ├── auth.example.json    # Modelo público de configuração de autenticação
│   ├── go2rtc.yaml          # Configuração dos streams Tuya/RTSP (ignorado no git)
│   ├── go2rtc.example.yaml  # Modelo público de conexão da câmera Tuya
│   └── roi_config.json      # Polígono normalizado, debounce, FPS, filtros e ntfy
├── backend/
│   ├── __init__.py
│   ├── auth.py              # Gerenciador de segurança, hash, tokens e guards de rotas
│   ├── database.py          # Camada de persistência SQLite, migrações e agregações
│   ├── detector.py          # Motor de visão computacional, FreshFrameReader e OpenVINO
│   └── main.py              # API FastAPI, Proxy Reverso go2rtc e WebSockets
├── frontend/
│   └── index.html           # SPA responsiva, WebRTC player, canvas vetorial 60 FPS e ROI
├── data/
│   ├── events.db            # Banco de dados de histórico de eventos e métricas
│   └── recordings/          # Gravações MP4 sincronizadas em velocidade real (H.264)
├── scripts/
│   ├── create_shortcut.py   # Gerador de atalho oficial (.lnk) no Desktop do usuário
│   ├── iniciar_catcam.bat   # Inicialização limpa em 1 clique via bandeja do Windows
│   └── parar_catcam.bat     # Finalização limpa e liberação forçada de portas
├── catcam_tray.py           # Aplicação de bandeja do Windows com controle de processos
├── yolo11n.pt               # Pesos originais do modelo YOLO11 nano
└── yolo11n_openvino_model/  # Grafo compilado e otimizado para Intel OpenVINO
```

---

## 6. ESPECIFICAÇÃO DETALHADA DOS MÓDULOS

### 6.1. Pipeline de Visão Computacional (`backend/detector.py`)

#### A. Leitor Anti-Lag (`FreshFrameReader`)
- Executa em uma thread daemon separada.
- Define `OPENCV_FFMPEG_CAPTURE_OPTIONS = "rtsp_transport;tcp"` para evitar perda de pacotes e artefatos de compressão UDP.
- Configura `cv2.CAP_PROP_BUFFERSIZE = 1`.
- Mantém apenas o último frame decodificado sob um lock reentrante, garantindo que o detector não acumule fila de processamento.

#### B. Redimensionamento e Inferência Otimizada
- Converte o frame bruto para largura proporcional de 640px (`infer_w = 640`, mantendo aspect ratio).
- Realiza a inferência YOLO11n com o modelo exportado para OpenVINO:
  ```python
  results = self.model.predict(
      frame,
      classes=target_classes,
      conf=self.confidence_threshold,
      device="cpu",
      verbose=False
  )[0]
  ```

#### C. Rastreamento e Espaço Poligonal com Supervision
- **`sv.ByteTrack`**: Calibrado com ativação de rastro em `0.18`, buffer de perda de 60 quadros e persistência contínua.
- **`sv.PolygonZone`**: O polígono é armazenado no `roi_config.json` em coordenadas normalizadas (`0.0` a `1.0`):
  ```python
  pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in self.polygon_normalized], dtype=np.int32)
  self.zone = sv.PolygonZone(polygon=pts)
  ```
  Isso desacopla a área monitorada da resolução da câmera e do tamanho da viewport.

#### D. Classificação Cromática Individual de Pets (`identify_cat_individual`)
Para distinguir individualmente felinos de mesma espécie na caixa de areia:
1. **Verificação de Infravermelho:** Se os canais R, G e B do frame completo apresentarem variância média inferior a `4.0`, o ambiente está em visão noturna infravermelha (classificado automaticamente como `"Gato (Noturno)"`).
2. **Core Crop:** Aplica um recorte central de 10% nas bordas do animal detectado para eliminar interferência de pisos, caixas ou móveis de fundo.
3. **Assinatura Cromática de Beatriz (Amarela/Laranja):**
   - Matiz HSV entre `8` e `34` (faixa do laranja/amarelo quente).
   - Saturação $\ge 50$ e Brilho $\ge 48$.
   - Dominância do canal vermelho sobre o azul: $R > B + 26$.
4. **Assinatura Cromática de Serena (Cinza / Azul Ardósia):**
   - Ramo A (Cinza Neutro): Saturação baixa ($S \le 40$) e Brilho entre $35$ e $220$.
   - Ramo B (Azul Ardósia / Britânico): Canal azul frio dominante ($B \ge R - 5$), matiz HSV entre $70$ e $135$, e saturação entre $15$ e $100$.
5. **Memória de Rastreamento:** A identidade confirmada é vinculada ao `tracker_id` do ByteTrack, evitando flutuações durante movimentações rápidas ou cabeceios.

#### E. Gravação Fluida e Sincronização H.264 a 1.0x Real
- Durante a visita, os quadros são gravados via `cv2.VideoWriter(..., fourcc="mp4v")`.
- Ao término do evento (com debounce configurável de 5 a 15 segundos após a saída da zona), a duração real em segundos e a quantidade total de frames gravados determinam o FPS efetivo:
  $$\text{real\_fps} = \frac{\text{visit\_frames\_written}}{\text{duration\_seconds}}$$
- A função assíncrona `convert_video_to_h264` executa o `ffmpeg`:
  ```bash
  ffmpeg -y -r <real_fps> -i entrada.mp4 -c:v libx264 -r 25 -preset ultrafast -pix_fmt yuv420p -movflags +faststart saida.mp4
  ```
  Essa etapa garante:
  - **Sincronização 1.0x:** O vídeo reproduz no tempo exato em que ocorreu no mundo real, sem acelerar.
  - **Compatibilidade Universal:** `pix_fmt yuv420p` e codec `H.264 (avc1)` reproduzem nativamente em Chrome, Safari, Firefox e iOS/Android sem travamentos.
  - **Início Instantâneo:** O parâmetro `+faststart` move o átomo `moov` para o início do arquivo, permitindo scrubbing e streaming progressivo instantâneo.

---

### 6.2. Persistência de Dados e Métricas (`backend/database.py`)

O banco SQLite local (`data/events.db`) implementa a tabela `visits`:

```sql
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    video_filename TEXT,
    tracker_id INTEGER,
    visitor_name TEXT DEFAULT 'Gato',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- **Mapeamento de Consultas:** Suporta agregações automáticas (`get_visits_breakdown`) por períodos (`today`, `yesterday`, `week`), entregando ao painel contagem por pet (ex: Beatriz, Serena, Noturno) e duração média de permanência na caixa de areia.

---

### 6.3. Segurança e Autenticação Server-Side (`backend/auth.py`)

- **Armazenamento Seguro:** As credenciais são guardadas em `config/auth.json` sob a estrutura:
  ```json
  {
    "auth_enabled": true,
    "salt": "<16-bytes-hex>",
    "password_hash": "<sha256(salt + password)>",
    "secret_key": "<32-bytes-hex>"
  }
  ```
- **Proteção contra Inspeção no Navegador:** A senha nunca transita para o frontend nem fica em variáveis de JavaScript legíveis via Developer Tools (F12).
- **Sessões HttpOnly:** O endpoint `POST /api/login` valida o hash no servidor Python e injeta o cookie seguro `catcam_session` (`HttpOnly=True`, `SameSite=Lax`), com duração de 30 dias.
- **Proteção de Rotas e WebSockets:** Todos os endpoints REST, downloads de gravações, streaming MJPEG e WebSockets (`/ws/detections` e `/go2rtc/api/ws`) validam a autenticação antes de aceitar a conexão.

---

### 6.4. Proxy Reverso Integrado e Acesso Remoto (`backend/main.py`)

Para permitir acesso local e remoto (via internet) sem complexidade de redirecionamento de portas ou certificados duplicados:

1. **Proxy HTTP Transparente (`/go2rtc/{path:path}`):** Instância assíncrona de `httpx.AsyncClient` conectada ao go2rtc na porta interna `127.0.0.1:1984`.
2. **Ponte WebSocket Bidirecional (`/go2rtc/api/ws`):** Tunela a sinalização WebRTC entre o navegador e o go2rtc com verificação do token de autenticação.
3. **Unificação na Porta 8000:** Tanto o painel visual quanto os fluxos de vídeo WebRTC fluem pela porta 8000. Qualquer ferramenta de túnel reverso (como `localhost.run` via SSH ou Cloudflare Tunnel) requer apenas o redirecionamento de `80:localhost:8000`.
4. **Gerador Dinâmico de QR Code (`/api/qrcode`):** Gera um QR Code em PNG com alto contraste apontando para o link público detectado pelo túnel, permitindo que o usuário escaneie com a câmera do celular para acessar imediatamente o painel com WebRTC.

---

### 6.5. Telemetria Vetorial a 60 FPS (`/ws/detections`)

Em vez de recomprimir o vídeo em um stream pesado de MJPEG para exibir os retângulos de detecção, o CatCam utiliza uma arquitetura híbrida de alto desempenho:
1. **Vídeo:** O stream de vídeo chega nativo a 30-60 FPS via WebRTC diretamente do go2rtc (aceleração por hardware no navegador).
2. **Dados Vetoriais:** O endpoint `/ws/detections` transmite periodicamente via WebSocket as caixas delimitadoras e o status do polígono em formato JSON leve:
   ```json
   {
     "objects": [
       {
         "id": 1,
         "box": [0.65, 0.42, 0.88, 0.91],
         "class_id": 15,
         "label": "Beatriz (Amarela) #1",
         "name": "Beatriz (Amarela)",
         "conf": 0.89,
         "in_zone": true
       }
     ],
     "in_zone": true,
     "in_zone_count": 1,
     "polygon": [[0.63, 0.31], [0.99, 0.28], [0.97, 0.98], [0.62, 0.97]],
     "fps": 11.8,
     "inference_ms": 32.4,
     "ts": 1741785000.123
   }
   ```
3. **Renderização no Frontend:** Um elemento `<canvas>` sobreposto ao vídeo desenha as caixas com suavização vetorial e cores dinâmicas (Verde = livre, Vermelho = na caixa de areia), poupando banda e proporcionando nitidez cristalina.

---

### 6.6. Sistema de Notificações em Tempo Real

1. **Notificações Push no Celular (ntfy.sh):**
   - Configurado via `roi_config.json` ou diretamente no painel web.
   - Ao detectar a entrada de um pet na caixa de areia, o worker envia uma requisição `PUT` ao servidor `ntfy.sh`:
     - **Título:** `🐱 CatCam AI • Beatriz (Amarela) na Caixa de Areia`
     - **Imagem Anotada:** Envio da imagem instantânea (`image/jpeg`) com a caixa desenhada.
     - **Click URL:** Link da URL pública HTTPS do CatCam para abertura imediata do streaming ao vivo no celular.
2. **Notificações Desktop (Windows 11):**
   - Disparo assíncrono via biblioteca `winotify`.
   - Toast interativo com som padrão do sistema e botão de ação direta "Ver ao Vivo".

---

### 6.7. Aplicativo de Bandeja do Windows (`catcam_tray.py`)

Gerencia os ciclos de vida dos processos sem expor janelas pretas de console:
- **Execução Oculta:** Utiliza a flag `CREATE_NO_WINDOW = 0x08000000` em todos os subprocessos.
- **Orquestração Automática:**
  1. Verifica se a porta `1984` está livre; se sim, instancia `bin/go2rtc.exe`.
  2. Verifica se a porta `8000` está livre; se sim, instancia `uvicorn backend.main:app`.
  3. Inicia thread com túnel SSH (`localhost.run`) e extrai a URL HTTPS pública retornada.
  4. Abre o navegador padrão em `http://localhost:8000`.
- **Menu da Bandeja (Perto do Relógio):**
  - Status em tempo real (`🟢 Ativo`).
  - *Abrir Painel (Local)*: `http://localhost:8000`.
  - *Abrir Link Online*: Acessa o endereço HTTPS do túnel remoto.
  - *Copiar Link de Acesso*: Copia a URL pública para a área de transferência do Windows.
  - *Abrir Pasta de Gravações*: Abre o Windows Explorer em `data/recordings/`.
  - *Encerrar CatCam*: Executa encerramento coordenado dos processos filhos e liberação das portas.

---

## 7. GUIA DE CONFIGURAÇÃO E IMPLANTAÇÃO PASSO A PASSO

### Passo 1: Inicialização do Ambiente Virtual e Instalação

Abra o terminal PowerShell no diretório do projeto:

```powershell
# Criação do ambiente virtual
python -m venv .venv

# Ativação do ambiente virtual
.\.venv\Scripts\Activate.ps1

# Atualização do gerenciador de pacotes
python -m pip install --upgrade pip

# Instalação das dependências homologadas
pip install ultralytics openvino supervision fastapi "uvicorn[standard]" opencv-python aiofiles websockets winotify requests qrcode[pil] pystray
```

### Passo 2: Configuração do Gateway de Vídeo go2rtc

1. Certifique-se de que o executável oficial para Windows x64 está posicionado em `bin/go2rtc.exe`.
2. Duplique o arquivo de exemplo para criar o arquivo ativo:
   ```powershell
   Copy-Item config\go2rtc.example.yaml config\go2rtc.yaml
   ```
3. Edite `config/go2rtc.yaml` inserindo o URI da câmera Tuya:
   ```yaml
   api:
     listen: ":1984"

   rtsp:
     listen: ":8554"

   webrtc:
     listen: ":8555"

   streams:
     cat_cam:
       - "tuya://protect-us.ismartlife.me?device_id=SEU_DEVICE_ID&email=seu_email@dominio.com&password=SUA_SENHA"
   ```

### Passo 3: Configuração da Autenticação Inicial

O sistema inicializa automaticamente com a senha padrão `catcam2026` no primeiro boot gerando `config/auth.json`. Você pode alterar essa senha a qualquer momento diretamente pelo botão **Alterar Senha** no cabeçalho do painel web.

### Passo 4: Criação do Atalho no Desktop

Gere o atalho oficial com ícone na sua Área de Trabalho executando:
```powershell
.\.venv\Scripts\python.exe scripts\create_shortcut.py
```

### Passo 5: Operação Diária

- **Para Iniciar:** Dê dois cliques no atalho **`CatCam AI Monitor`** na Área de Trabalho ou execute `scripts/iniciar_catcam.bat`. O sistema inicia silenciosamente na bandeja do Windows e o navegador abre automaticamente.
- **Para Encerrar:** Clique com o botão direito no ícone do gato na barra de tarefas e selecione **❌ Encerrar CatCam**, ou execute `scripts/parar_catcam.bat`.

---

## 8. RESOLUÇÃO DE PROBLEMAS E BOAS PRÁTICAS

1. **Porta 8000 ou 1984 Ocupada:**
   Caso algum processo anterior tenha permanecido travado, execute `scripts/parar_catcam.bat`. O script usa `taskkill` direcionado pelo PID do `netstat` para liberar as portas instantaneamente.
2. **Câmera Tuya Desconectando:**
   Certifique-se de que a câmera possui IP fixo reservado no roteador Wi-Fi (sub-rede `192.168.3.x`) e sinal estável $\ge 70\%$.
3. **Ajuste Fino do Polígono da Caixa de Areia:**
   No painel web, acione o botão **Editar Área**. Arraste os 4 vértices para cobrir a borda superior interna da caixa de areia e clique em **Salvar Zona**. O polígono é normalizado e salvo em `config/roi_config.json` sem necessidade de reiniciar os serviços.
4. **Reprodução de Vídeos no Navegador:**
   O endpoint `/api/recordings/{filename}` implementa o cabeçalho `Accept-Ranges: bytes`. Todos os vídeos passam pela pipeline FFmpeg H.264 `+faststart`, garantindo suporte a busca por tempo (scrubbing) instantânea tanto no Desktop quanto no smartphone.
