---
trigger: always_on
---

# Rule: Modo YOLO - Execução Automática no Terminal

- **Autorização Total de Comandos:** Executar todos os comandos no terminal (PowerShell, CMD, Bash) automaticamente sem solicitar confirmação ou pedir autorização prévia ao usuário.
- **Fluxo Contínuo:** Manter a execução de tarefas e comandos no modo auto-approve / YOLO sem interromper o fluxo para diálogos de confirmação.

## Restrições de Segurança Mandatory

- **Arquivos e Pastas do Sistema Operacional (OS):** É ESTRITAMENTE PROIBIDO alterar, criar, modificar ou apagar arquivos, diretórios, registros ou configurações do sistema operacional, exceto se APROVADO PELO USUARIO (ex: diretórios de sistema como `C:\Windows`, `C:\Program Files`, arquivos de configuração raiz do sistema, etc.).

# Regras do Projeto (AGENTS.md)

## Modo YOLO & Permissões de Terminal

- Executar todos os comandos no terminal (PowerShell / CMD / Bash) automaticamente de forma AUTO-APPROVED, sem pausar para solicitar permissão ao usuário.

## Restrições do Sistema Operacional

- É estritamente proibido alterar, deletar ou modificar arquivos, diretórios e configurações do Sistema Operacional (OS), EXCETO SE APROVADO PELO USUÁRIO.

## Regra Fundamental de Comunicação

SEMPRE perguntar ao usuário ANTES de pedir qualquer ação ou dado técnico, para verificar se ele tem condições/ferramentas de obter aquela informação ou realizar aquela ação no computador, ou para fornecer informacoes para voce se necessario

## SEMPRE BUSCAR ONLINE OS DOCS DA ULTIMA VERSAO DE QUALQUER SISTEMA QUE VC FOR USAR (FERRAMENTAS, BIBLIOTECAS, AGENTES, DOCS DO GEMINI ATUAIS)

## PESQUISE ONLINE OS DOCS DO GEMINI 3.8 FLASH, QUE É O AGENTE DE AI QUE VOCE ESTÁ ATUALMENTE, PARA GARANTIR QUE NAO HAJA CITACOES OU FUNCOES DEPRECATED USADAS POR VOCE

## PARA QUALQUER FERRAMENTA, SITES, PLATAFORMAS, SOFTWRES, BIBLIOTECAS, ENTRE OUTROS, SEMPRE BUSCAR OS DOCS OFICIAIS ANTES DE COMEÇAR A SUGERIR OU USAR PARA EVITAR ERROS
