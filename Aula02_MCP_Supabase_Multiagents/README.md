# 🤖 Sistema WhatsApp + IA + Supabase
## Análise Inteligente de Dados via WhatsApp com Multiagentes

### 📋 Visão Geral

Este projeto implementa um sistema avançado de análise de dados que permite consultar um banco Supabase através de mensagens em linguagem natural via WhatsApp, utilizando um sistema multiagentes baseado em Claude 4.

### 🏗️ Arquitetura do Sistema

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   WhatsApp      │───▶│  Sistema         │───▶│   Supabase      │
│   (Interface)   │    │  Multiagentes    │    │   (Dados)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Claude 4       │
                    │   (Inteligência) │
                    └──────────────────┘
```

### 🤖 Sistema Multiagentes

O sistema utiliza 5 agentes especializados que trabalham em conjunto:

#### 1. **Agente Coordenador**
- Analisa a intenção do usuário
- Determina que tipo de análise é necessária
- Planeja a execução da consulta

#### 2. **Agente Schema**
- Descobre dinamicamente a estrutura das tabelas
- Obtém metadados e amostras de dados
- Mantém cache para otimização

#### 3. **Agente Query**
- Constrói consultas SQL inteligentes
- Executa operações no Supabase
- Adapta estratégias conforme complexidade

#### 4. **Agente Analyst**
- Analisa os resultados obtidos
- Gera insights de negócio
- Identifica padrões e tendências

#### 5. **Agente Formatter**
- Formata respostas para WhatsApp
- Adiciona emojis e formatação
- Estrutura informações de forma clara

### 🚀 Funcionalidades

- ✅ **Descoberta Automática**: Identifica tabelas e colunas dinamicamente
- ✅ **Linguagem Natural**: Processa perguntas em português
- ✅ **Análises Complexas**: Suporta agregações, filtros e joins
- ✅ **Insights Inteligentes**: Gera análises de negócio automaticamente
- ✅ **Cache Inteligente**: Otimiza performance com cache de metadados
- ✅ **Respostas Formatadas**: Saída otimizada para WhatsApp

### 📊 Exemplos de Uso

```
👤 "quais tabelas temos?"
🤖 Lista todas as tabelas disponíveis com contadores

👤 "quantos leads temos?"
🤖 Conta registros na tabela de leads

👤 "qual foi o registro mais recente na tabela aula_views?"
🤖 Busca e analisa o último registro com insights detalhados

👤 "leads com email gmail"
🤖 Filtra e conta leads com domínio Gmail

👤 "média de visualizações por usuário"
🤖 Calcula agregações complexas com análise
```

### 🛠️ Tecnologias Utilizadas

- **Node.js** - Runtime JavaScript
- **Claude 4** - LLM para inteligência artificial
- **Supabase** - Banco de dados PostgreSQL
- **WhatsApp Web.js** - Interface WhatsApp
- **Express.js** - Servidor web
- **Anthropic SDK** - Integração com Claude

### 📦 Instalação

1. **Clone o repositório**
```bash
git clone <repository-url>
cd whatsapp-ia-supabase
```

2. **Instale as dependências**
```bash
npm install
```

3. **Configure as variáveis de ambiente**
```bash
cp .env.example .env
```

4. **Configure o arquivo .env**
```env
# Claude (Principal)
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_MAX_TOKENS=1500

# Supabase
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-service-role-key

# WhatsApp
WHATSAPP_SESSION_PATH=./whatsapp-session-unified
WHATSAPP_CLIENT_ID=unified-ai-assistant

# Servidor
PORT=8080
```

5. **Execute o sistema**
```bash
npm start
```

### 🗄️ Configuração do Supabase

#### ⚠️ Funções SQL Obrigatórias

**IMPORTANTE**: Para o sistema funcionar corretamente, você DEVE criar estas funções RPC no seu banco Supabase. Acesse o SQL Editor no painel do Supabase e execute cada função:

#### 1. **Função list_tables**
```sql
CREATE OR REPLACE FUNCTION list_tables()
RETURNS TABLE(table_name text) AS $$
BEGIN
    RETURN QUERY
    SELECT t.table_name::text
    FROM information_schema.tables t
    WHERE t.table_schema = 'public'
    AND t.table_type = 'BASE TABLE'
    ORDER BY t.table_name;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### 2. **Função list_columns**
```sql
CREATE OR REPLACE FUNCTION list_columns(table_name text)
RETURNS TABLE(
    column_name text,
    data_type text,
    is_nullable text
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.column_name::text,
        c.data_type::text,
        c.is_nullable::text
    FROM information_schema.columns c
    WHERE c.table_schema = 'public'
    AND c.table_name = $1
    ORDER BY c.ordinal_position;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### 3. **Função get_table_stats**
```sql
CREATE OR REPLACE FUNCTION get_table_stats(table_name text)
RETURNS TABLE(
    table_name text,
    row_count bigint,
    size_bytes bigint
) AS $$
DECLARE
    query_text text;
    row_count_result bigint;
BEGIN
    -- Conta registros dinamicamente
    query_text := format('SELECT COUNT(*) FROM %I', $1);
    EXECUTE query_text INTO row_count_result;
    
    RETURN QUERY
    SELECT 
        $1::text,
        row_count_result,
        pg_total_relation_size(format('%I', $1)::regclass)::bigint;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### 4. **Função execute_custom_query**
```sql
CREATE OR REPLACE FUNCTION execute_custom_query(
    query_text text,
    query_params text[] DEFAULT '{}'
)
RETURNS json AS $$
DECLARE
    result json;
BEGIN
    -- Validação de segurança - apenas SELECT permitido
    IF query_text !~* '^select' THEN
        RAISE EXCEPTION 'Apenas queries SELECT são permitidas';
    END IF;
    
    -- Remove comentários e caracteres perigosos
    IF query_text ~* '(drop|delete|update|insert|create|alter|truncate)' THEN
        RAISE EXCEPTION 'Operações de modificação não são permitidas';
    END IF;
    
    -- Executa query e retorna resultado como JSON
    EXECUTE format('SELECT row_to_json(t) FROM (%s) t', query_text) INTO result;
    RETURN result;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Erro na execução da query: %', SQLERRM;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### 5. **Função refresh_unified_leads** (se aplicável)
```sql
CREATE OR REPLACE FUNCTION refresh_unified_leads()
RETURNS void AS $$
BEGIN
    -- Atualiza tabela unificada de leads
    -- Implementar lógica específica do seu negócio
    RAISE NOTICE 'Unified leads refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### 🔍 **Verificação das Funções RPC**

Após criar as funções, teste se estão funcionando:

```sql
-- Teste 1: Verificar se list_tables funciona
SELECT * FROM list_tables();

-- Teste 2: Verificar se list_columns funciona (substitua 'sua_tabela' por uma tabela real)
SELECT * FROM list_columns('sua_tabela');

-- Teste 3: Verificar se get_table_stats funciona
SELECT * FROM get_table_stats('sua_tabela');

-- Teste 4: Verificar se execute_custom_query funciona
SELECT execute_custom_query('SELECT 1 as teste');
```

**Status esperado**: Todas as funções devem retornar resultados sem erro.

### 🔐 Configuração de Segurança

#### Row Level Security (RLS)

Para tabelas sensíveis, configure políticas RLS:

```sql
-- Exemplo para tabela unified_leads
ALTER TABLE unified_leads ENABLE ROW LEVEL SECURITY;

-- Política para service_role (usado pelo sistema)
CREATE POLICY "service_role_access" ON unified_leads
FOR ALL TO service_role
USING (true);

-- Política para usuários autenticados (se necessário)
CREATE POLICY "authenticated_read" ON unified_leads
FOR SELECT TO authenticated
USING (true);
```

### 📁 Estrutura do Projeto

```
src/
├── ai/
│   ├── agent.js              # Agente IA original (legacy)
│   └── multiagent-system.js  # Sistema multiagentes principal
├── formatters/
│   └── response.js           # Formatação de respostas
├── mcp/
│   └── supabase-server.js    # Servidor MCP (futuro)
├── supabase/
│   └── executor.js           # Executor de queries Supabase
├── utils/
│   └── helpers.js            # Funções auxiliares
├── whatsapp/
│   └── bot.js                # Bot WhatsApp
└── index.js                  # Ponto de entrada principal
```

### 🔄 Fluxo de Processamento

1. **Recepção**: WhatsApp recebe mensagem do usuário
2. **Coordenação**: Agente Coordenador analisa a intenção
3. **Descoberta**: Agente Schema obtém estrutura das tabelas
4. **Execução**: Agente Query constrói e executa consultas
5. **Análise**: Agente Analyst gera insights dos dados
6. **Formatação**: Agente Formatter prepara resposta para WhatsApp
7. **Resposta**: Sistema envia análise formatada ao usuário

### 📈 Exemplos de Análises Geradas

O sistema gera análises como:

```
📊 *REGISTRO MAIS RECENTE - AULA VIEWS*

🕐 *Data/Hora:* 15 de maio de 2025, às 13:20
👤 *Usuário:* marco@rdantas.com.br
🎯 *Aula Acessada:* Aula 1

---

🔍 *DETALHES DO ACESSO:*
• *Navegação:* Aula 2 → Aula 1 (retorno/revisão)
• *Plataforma:* Windows Desktop + Chrome
• *Tipo:* Acesso direto (sem UTM de campanha)
• *Session ID:* session_422awu3oy9625p4ex5nu1a

---

💡 *INSIGHTS IMPORTANTES:*

🎯 *Comportamento do Usuário:*
• Padrão de revisão ativa - voltou da aula 2 para aula 1
• Indica engajamento e busca por reforço do conteúdo base
• Acesso orgânico (não veio de campanha)

✅ *Para o Negócio:*
• Usuário demonstra alta retenção...
```

### 🚀 Deploy e Produção

#### Variáveis de Ambiente de Produção
```env
NODE_ENV=production
PORT=8080
ANTHROPIC_API_KEY=sua-chave-producao
SUPABASE_URL=sua-url-producao
SUPABASE_KEY=sua-chave-producao
```

#### Monitoramento
- Logs estruturados para cada agente
- Métricas de performance de queries
- Cache hit/miss ratios
- Tempo de resposta por tipo de análise

### 🎓 Para Educadores

Este projeto demonstra:

- **Arquitetura Multiagentes**: Como dividir responsabilidades
- **Integração de APIs**: WhatsApp, Claude, Supabase
- **Processamento de Linguagem Natural**: Análise de intenções
- **Descoberta Dinâmica**: Sistema que se adapta aos dados
- **Análise de Dados**: Geração automática de insights
- **UX Conversacional**: Interface natural via chat

### 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

### 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para detalhes.

### 🔧 Troubleshooting

#### Problemas Comuns com Funções RPC

**❌ Erro: "Could not find the function public.list_tables()"**
- **Causa**: Função RPC não foi criada no Supabase
- **Solução**: Execute as funções SQL na seção "Configuração do Supabase"

**❌ Erro: "permission denied for function list_tables"**
- **Causa**: Função criada sem `SECURITY DEFINER`
- **Solução**: Recrie a função com `SECURITY DEFINER` no final

**❌ Erro: "RPC list_tables não disponível"**
- **Causa**: Service role key incorreta ou função não existe
- **Solução**:
  1. Verifique se `SUPABASE_KEY` é a service_role key (não anon key)
  2. Teste as funções no SQL Editor do Supabase

**❌ Sistema usa fallback em vez de RPC**
- **Causa**: Funções RPC não estão funcionando
- **Solução**: Execute os testes de verificação da seção anterior

### 🆘 Suporte

Para dúvidas ou problemas:
- Abra uma issue no GitHub
- Consulte a documentação do Supabase
- Verifique os logs do sistema
- Execute os testes de verificação das funções RPC

---

**Desenvolvido com ❤️ para demonstrar o poder da IA aplicada à análise de dados**