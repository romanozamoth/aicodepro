# Diagrama de Relações e Fluxo do Sistema Webinar-Matery-Agents

```mermaid
graph TB
    %% Arquivos principais
    start[start.js] --> index[src/index.js]
    
    %% Classe principal e componentes
    index --> WhatsAppAISystem
    
    %% Componentes principais
    WhatsAppAISystem --> WhatsAppBot[src/whatsapp/bot.js]
    WhatsAppAISystem --> MultiAgentSystem[src/ai/multiagent-system.js]
    WhatsAppAISystem --> SupabaseExecutor[src/supabase/executor.js]
    WhatsAppAISystem --> ResponseFormatter[src/formatters/response.js]
    
    %% Fluxo de inicialização
    subgraph "Fluxo de Inicialização"
        start_verify[Verificações de Ambiente] --> start_deps[Verificação de Dependências]
        start_deps --> start_system[Inicialização do Sistema]
    end
    
    start --> start_verify
    
    %% Fluxo de processamento de mensagens
    subgraph "Fluxo de Processamento de Mensagens"
        message[Mensagem do WhatsApp] --> WhatsAppBot
        WhatsAppBot --> MultiAgentSystem
        MultiAgentSystem --> SupabaseExecutor
        SupabaseExecutor --> MultiAgentSystem
        MultiAgentSystem --> WhatsAppBot
        WhatsAppBot --> ResponseFormatter
        ResponseFormatter --> response[Resposta Formatada]
    end
    
    %% Dependências externas
    subgraph "Dependências Externas"
        whatsapp_web[whatsapp-web.js]
        anthropic[Anthropic API]
        supabase[Supabase API]
        express[Express]
    end
    
    WhatsAppBot --> whatsapp_web
    MultiAgentSystem --> anthropic
    SupabaseExecutor --> supabase
    WhatsAppAISystem --> express
    
    %% Estilo
    classDef primary fill:#f9f,stroke:#333,stroke-width:2px
    classDef secondary fill:#bbf,stroke:#333,stroke-width:1px
    classDef external fill:#bfb,stroke:#333,stroke-width:1px
    
    class start,index primary
    class WhatsAppBot,MultiAgentSystem,SupabaseExecutor,ResponseFormatter secondary
    class whatsapp_web,anthropic,supabase,express external
```

## Explicação do Fluxo de Execução

1. **Inicialização do Sistema**:
   - `start.js` é o ponto de entrada que verifica o ambiente, dependências e configurações
   - `start.js` carrega o arquivo `.env` e verifica variáveis obrigatórias
   - Após as verificações, `start.js` importa e executa `src/index.js`

2. **Estrutura Principal**:
   - `src/index.js` define a classe `WhatsAppAISystem` que orquestra todos os componentes
   - Inicializa os quatro componentes principais: WhatsAppBot, MultiAgentSystem, SupabaseExecutor e ResponseFormatter
   - Configura um servidor Express para monitoramento e status

3. **Componentes Principais**:
   - **WhatsAppBot** (`src/whatsapp/bot.js`): Gerencia a conexão com o WhatsApp usando whatsapp-web.js
   - **MultiAgentSystem** (`src/ai/multiagent-system.js`): Implementa o sistema de IA usando a API da Anthropic (Claude)
   - **SupabaseExecutor** (`src/supabase/executor.js`): Gerencia a conexão e consultas ao Supabase
   - **ResponseFormatter** (`src/formatters/response.js`): Formata as respostas para envio ao WhatsApp

4. **Fluxo de Processamento de Mensagens**:
   - Mensagem recebida pelo WhatsAppBot
   - WhatsAppBot encaminha para o MultiAgentSystem
   - MultiAgentSystem analisa a intenção e consulta o SupabaseExecutor quando necessário
   - Resposta é formatada pelo ResponseFormatter
   - WhatsAppBot envia a resposta formatada de volta ao usuário

5. **Dependências Externas**:
   - whatsapp-web.js para comunicação com WhatsApp
   - API da Anthropic (Claude) para processamento de linguagem natural
   - Supabase para armazenamento e consulta de dados
   - Express para servidor web de monitoramento
```
