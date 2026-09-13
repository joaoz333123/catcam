---
trigger: always_on
---

# Regra: Modo YOLO, Segurança do Sistema e Documentação Atualizada

## 1. Modo YOLO & Execução no Terminal
- **Autorização Total e Contínua:** Executar todos os comandos no terminal (PowerShell, CMD, Bash) automaticamente de forma AUTO-APPROVED, sem pausar para solicitar confirmação ou pedir autorização prévia ao usuário.
- **Fluxo Ágil:** Manter o fluxo de execução contínuo, realizando comandos locais e comandos remotos do GitHub necessários para o projeto de forma autônoma.

## 2. Restrições Estritas de Segurança do Sistema Operacional
- **Proteção do Sistema Operacional (OS):** É estritamente proibido alterar, criar, modificar ou apagar arquivos, diretórios, registros ou configurações do sistema operacional (ex: `C:\Windows`, `C:\Program Files`, registros de sistema), EXCETO se expressamente aprovado pelo usuário.
- **Escopo do Projeto:** Limitar todas as operações ao diretório do projeto e seus subdiretórios autorizados.

## 3. Comunicação Prévia de Ações e Ferramentas
- **Verificação de Capacidade do Usuário:** Sempre perguntar ao usuário ANTES de solicitar qualquer ação manual ou dado técnico, verificando previamente se ele possui ferramentas ou condições de obter aquela informação ou realizar a etapa no computador.

## 4. Consulta Obrigatória à Documentação Oficial Atualizada
- **Sempre Buscar Docs Oficiais:** Antes de sugerir, adotar ou alterar qualquer biblioteca, ferramenta, framework ou plataforma, pesquisar na documentação oficial da última versão estável para evitar erros e incompatibilidades.
- **Alinhamento com o Modelo Atual (Gemini 3.8 Flash):** Garantir que nenhuma função, sintaxe ou padrão obsoleto (deprecated) seja utilizado, adotando as práticas e recursos vigentes da API.
