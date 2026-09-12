# 🐱 CatCam AI Monitor

Sistema autônomo, **100% local e gratuito** de monitoramento e visão computacional para pets com **YOLO11**, aceleração **Intel OpenVINO** e suíte **Supervision**.

Projetado para operar com câmeras compatíveis com o ecossistema Tuya (como a **Positivo Smart Câmera 360° Bot**) com firmware de fábrica, sem custos de nuvem ou assinaturas.

---

## ✨ Destaques do Projeto

- **Privacidade Absoluta & Zero Custo:** Todo o processamento de vídeo e IA roda no seu computador local, sem envio de imagens para terceiros.
- **Acesso Seguro com Senha:** Autenticação no servidor (Python) com hash SHA-256 + salt e cookie de sessão seguro. Todas as rotas de API, streams e WebSockets são blindados contra inspeção no navegador (F12).
- **Acesso Local e Remoto Simultâneo:** Acesse via rede local (`http://localhost:8000`) e pela internet através de túnel seguro com HTTPS.
- **QR Code Dinâmico no Painel:** O painel exibe um QR Code interativo que atualiza automaticamente conforme a URL pública, permitindo conectar o smartphone apenas apontando a câmera.
- **Streaming WebRTC & Overlay IA a 60 FPS:** Transmissão fluida em tempo real acelerada por hardware via **go2rtc** com overlay vetorial acelerado por GPU.
- **Identificação Individual de Pets (HSV):** Distinção visual e cromática em tempo real para múltiplos pets (ex: Beatriz vs. Serena).
- **Notificações Push com Foto no Celular:** Disparo instantâneo via **ntfy.sh** direto no seu celular com foto anotada e link para a live.
- **Gravação Automática H.264 Web:** Gravação em MP4 otimizada com reprodução nativa no histórico SQLite do painel.
- **Aplicativo de Bandeja do Windows (System Tray):** Execução 100% silenciosa em segundo plano com atalho oficial no Desktop e menu de clique direito perto do relógio.

---

## 🚀 Inicialização Rápida

### 🌟 Pelo Atalho no Desktop (Recomendado)
Dê dois cliques no ícone **`CatCam AI Monitor`** na Área de Trabalho:
1. Os serviços iniciam em segundo plano sem abrir janelas pretas de terminal.
2. O ícone do CatCam aparece na **bandeja do Windows** (ao lado do relógio).
3. O painel web abre automaticamente no seu navegador.
4. Clique com o **botão direito** no ícone da bandeja para abrir o painel local, acessar o link remoto ou encerrar tudo com um clique.

### 📂 Pelos Scripts de Terminal (`scripts/`)
- **Iniciar:** Dê dois cliques em **`scripts/iniciar_catcam.bat`**.
- **Parar:** Dê dois cliques em **`scripts/parar_catcam.bat`**.

---

## 📋 Instalação e Configuração

### 1. Clonar e Instalar Dependências
```bash
git clone https://github.com/joaoz333123/catcam.git
cd catcam
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install ultralytics openvino supervision fastapi "uvicorn[standard]" opencv-python aiofiles websockets winotify requests qrcode[pil] pystray
```

### 2. Baixar o Gateway de Vídeo (go2rtc)
Baixe o executável para Windows do [go2rtc (AlexxIT)](https://github.com/AlexxIT/go2rtc/releases/latest) e coloque em:
`bin/go2rtc.exe`

### 3. Configurar a Câmera
Copie o modelo de configuração e preencha com as credenciais da câmera Tuya:
```bash
copy config\go2rtc.example.yaml config\go2rtc.yaml
```
*(O arquivo `config/go2rtc.yaml` é estritamente ignorado pelo `.gitignore` para proteger suas credenciais).*

### 4. Criar o Atalho no Desktop (Opcional)
Para gerar o atalho oficial com ícone na sua Área de Trabalho:
```bash
.\.venv\Scripts\python.exe scripts/create_shortcut.py
```

---

## 🔒 Segurança e Privacidade

- **Blindagem de Credenciais:** Arquivos sensíveis (`config/go2rtc.yaml`, `config/auth.json`, banco `data/events.db` e gravações `data/recordings/`) estão permanentemente no `.gitignore` e **nunca** são enviados ao GitHub.
- **Proteção do Histórico Git:** O repositório passa por auditorias regulares de histórico para assegurar que nenhum token, senha ou dado de rede seja exposto remotamente.
- **Operação Local:** Nenhuma gravação ou imagem é transmitida para servidores de nuvem de fabricantes.

---

## 📄 Licença

Distribuído sob licença MIT. Livre para uso pessoal e modificação.
