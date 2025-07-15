# Fluxo Detalhado de Processamento de Mensagem

Este diagrama ilustra o caminho detalhado que uma pergunta percorre no sistema, destacando os aspectos técnicos avançados implementados.

## 🔄 Fluxo de Processamento de Mensagem com Destaques Técnicos

```mermaid
flowchart TD
    %% Entrada da mensagem
    start([Mensagem do Usuário]) --> whatsapp[WhatsApp Bot\nbot.js]
    
    %% Processamento inicial
    whatsapp --> |"1. Recebe mensagem"| preprocess[Pré-processamento\n- Detecção de idioma\n- Análise de sentimento\n- Verificação de contexto]
    
    %% Sistema Multi-agente
    preprocess --> |"2. Encaminha para IA"| ai_system[Sistema Multi-agente\nmultiagent-system.js]
    
    %% Cache multinível - DESTAQUE TÉCNICO 1
    ai_system --> cache{Cache Multinível}
    cache --> |"HIT: Resposta em cache"| format_cached[Formatação\nde Resposta em Cache]
    cache --> |"MISS: Processamento completo"| intention[Análise de Intenção\n- Classificação de consulta\n- Identificação de entidades\n- Detecção de operação]
    
    %% Processamento contextual - DESTAQUE TÉCNICO 2
    intention --> context_proc[Processamento Contextual\n- Histórico de conversa\n- Preferências do usuário\n- Consultas anteriores\n- Contexto empresarial]
    
    %% Transformação em SQL
    context_proc --> sql_gen[Geração de SQL\n- Templates dinâmicos\n- Validação de segurança\n- Otimização de consulta]
    
    %% Execução no Supabase
    sql_gen --> supabase[Executor Supabase\nexecutor.js]
    
    %% Otimização de consulta - DESTAQUE TÉCNICO 3
    supabase --> query_opt[Otimização de Consulta\n- Índices específicos\n- Paginação inteligente\n- Limitação de resultados\n- Ordenação otimizada]
    
    %% Execução e resultados
    query_opt --> db[(Supabase DB)]
    db --> results[Resultados Brutos]
    
    %% Análise de dados - DESTAQUE TÉCNICO 4
    results --> data_analysis[Análise de Dados\n- Agregação inteligente\n- Detecção de anomalias\n- Insights automáticos\n- Métricas relevantes]
    
    %% Formatação para WhatsApp
    data_analysis --> formatter[Formatador de Resposta\nresponse.js]
    formatter --> whatsapp_format[Formatação WhatsApp\n- Emojis contextuais\n- Formatação markdown\n- Quebras de texto\n- Priorização de informação]
    
    %% Resposta final
    whatsapp_format --> final_response[Resposta Final]
    format_cached --> final_response
    final_response --> whatsapp_send[Envio via WhatsApp]
    whatsapp_send --> end([Mensagem Entregue])
    
    %% Estilo
    classDef highlight fill:#f9a,stroke:#333,stroke-width:2px;
    classDef standard fill:#d4f1f9,stroke:#333,stroke-width:1px;
    classDef database fill:#b5e7a0,stroke:#333,stroke-width:1px;
    
    class cache,context_proc,query_opt,data_analysis highlight;
    class whatsapp,preprocess,ai_system,intention,sql_gen,supabase,results,formatter,whatsapp_format,final_response,whatsapp_send standard;
    class db database;
```

## 💡 Destaques Técnicos Avançados

### 1. Cache Multinível
- **Implementação**: Sistema de cache hierárquico com diferentes políticas para tipos de dados
- **Benefício**: Redução drástica de latência (de segundos para milissegundos)
- **Código**: Utiliza cache em memória para respostas frequentes e armazenamento em arquivo para persistência
- **Diferencial**: Políticas de TTL dinâmicas que se ajustam com base em padrões de uso

### 2. Processamento Contextual
- **Implementação**: Análise de histórico de conversa e contexto do usuário
- **Benefício**: Respostas mais precisas e personalizadas
- **Código**: Mantém estado conversacional entre mensagens para referências implícitas
- **Diferencial**: Considera consultas anteriores para resolver ambiguidades

### 3. Otimização de Consultas
- **Implementação**: Geração inteligente de SQL com otimizações específicas
- **Benefício**: Consultas mais rápidas e eficientes mesmo em grandes volumes de dados
- **Código**: Utiliza índices específicos e estratégias de paginação adaptativas
- **Diferencial**: Ajusta automaticamente limites e ordenação com base no tipo de consulta

### 4. Análise de Dados Inteligente
- **Implementação**: Processamento pós-consulta para extrair insights relevantes
- **Benefício**: Transforma dados brutos em informações acionáveis
- **Código**: Aplica algoritmos de agregação e detecção de padrões
- **Diferencial**: Gera automaticamente métricas relevantes para o contexto da pergunta
```
