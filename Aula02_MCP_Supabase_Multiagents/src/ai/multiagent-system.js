const Anthropic = require('@anthropic-ai/sdk');

/**
 * Sistema Multiagentes para Análise de Dados Supabase
 * Arquitetura: Coordenador + Agentes Especializados
 */
class MultiAgentSystem {
    constructor(supabaseExecutor) {
        this.supabaseExecutor = supabaseExecutor;
        
        // Inicializa Claude
        this.anthropic = new Anthropic({
            apiKey: process.env.ANTHROPIC_API_KEY,
        });
        
        this.model = process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-20250514';
        this.maxTokens = parseInt(process.env.ANTHROPIC_MAX_TOKENS) || 1500;
        
        // Cache de metadados para otimização
        this.schemaCache = new Map();
        this.lastCacheUpdate = null;
        
        // Contexto de conversa para melhor interpretação
        this.conversationContext = {
            lastEmail: null,
            lastTable: null,
            lastOperation: null,
            recentQueries: []
        };
        
        // Inicializa servidor MCP interno
        this.initializeMCPServer();
        
        console.log('🤖 Sistema Multiagentes inicializado com MCP');
    }

    initializeMCPServer() {
        try {
            const SupabaseMCPServer = require('../mcp/supabase-server.js');
            this.mcpServer = new SupabaseMCPServer();
            console.log('🔧 Servidor MCP interno inicializado');
        } catch (error) {
            console.warn('⚠️ Não foi possível inicializar servidor MCP:', error.message);
            this.mcpServer = null;
        }
    }

    /**
     * Ponto de entrada principal - coordena todos os agentes
     */
    async processMessage(messageText, userContext) {
        try {
            console.log(`🧠 Coordenador processando: "${messageText}"`);

            // 1. Agente Coordenador analisa a intenção
            const intention = await this.coordinatorAgent(messageText);
            console.log(`🎯 Intenção identificada:`, intention);

            // Atualiza contexto de conversa
            this.updateConversationContext(intention, messageText);

            // 2. Agente Schema descobre estrutura necessária
            const schema = await this.schemaAgent(intention.tables_needed);
            console.log(`📋 Schema obtido para ${schema.length} tabelas`);

            // 3. Agente Query constrói e executa consultas
            const queryResult = await this.queryAgent(intention, schema);
            console.log(`🔍 Query executada:`, queryResult.success ? 'Sucesso' : 'Erro');

            // 4. Agente Analyst analisa os resultados
            const analysis = await this.analystAgent(queryResult, intention, messageText);
            console.log(`📊 Análise concluída`);

            // 5. Agente Formatter cria resposta para WhatsApp
            const response = await this.formatterAgent(analysis, queryResult, messageText);
            console.log(`💬 Resposta formatada: ${response.length} caracteres`);

            return {
                intention: intention,
                schema: schema,
                queryResult: queryResult,
                analysis: analysis,
                response: response,
                userContext: userContext
            };

        } catch (error) {
            console.error('❌ Erro no sistema multiagentes:', error);
            return {
                intention: { error: true },
                response: `🤖 Desculpe, encontrei um erro ao analisar sua solicitação: ${error.message}`,
                userContext: userContext
            };
        }
    }

    /**
     * AGENTE COORDENADOR - Analisa intenção e planeja execução
     */
    async coordinatorAgent(messageText) {
        // Primeiro descobre as tabelas disponíveis dinamicamente
        const availableTables = await this.discoverAvailableTables();
        
        // Detecta referências contextuais
        const contextualInfo = this.extractContextualReferences(messageText);
        
        const prompt = `Você é o Agente Coordenador de um sistema de análise de dados.

TABELAS DESCOBERTAS DINAMICAMENTE:
${availableTables.map(table =>
    `- ${table.table_name} (${table.row_count} registros, ${table.columns.length} colunas)`
).join('\n')}

CONTEXTO DA CONVERSA:
${this.conversationContext.lastEmail ? `- Último email consultado: ${this.conversationContext.lastEmail}` : ''}
${this.conversationContext.lastTable ? `- Última tabela consultada: ${this.conversationContext.lastTable}` : ''}
${this.conversationContext.lastOperation ? `- Última operação: ${this.conversationContext.lastOperation}` : ''}

REFERÊNCIAS DETECTADAS NA MENSAGEM:
${contextualInfo.email ? `- Email mencionado: ${contextualInfo.email}` : ''}
${contextualInfo.table ? `- Tabela mencionada: ${contextualInfo.table}` : ''}
${contextualInfo.sameEmail ? '- Referência ao "mesmo email" detectada' : ''}
${contextualInfo.sameTable ? '- Referência à "mesma tabela" detectada' : ''}

INSTRUÇÕES CRÍTICAS:
1. Se detectar "mesmo email", "esse email", use: ${this.conversationContext.lastEmail || 'email anterior'}
2. Se detectar "mesma tabela", "essa tabela", use: ${this.conversationContext.lastTable || 'tabela anterior'}
3. Para busca de email específico, use analysis_type: "list" e operations: ["filter"]
4. Para contagens, use analysis_type: "count" e operations: ["count"]
5. Para listagem de tabelas, use analysis_type: "list" e operations: ["metadata_query"]

EXEMPLOS DE ANÁLISE CORRETA:
- "buscar email X na tabela Y" → {"analysis_type": "list", "tables_needed": ["Y"], "operations": ["filter"]}
- "dados do mesmo email na tabela Z" → {"analysis_type": "list", "tables_needed": ["Z"], "operations": ["filter"]}
- "quantos registros tem" → {"analysis_type": "count", "tables_needed": ["tabela"], "operations": ["count"]}

RESPONDA APENAS EM JSON VÁLIDO (sem markdown, sem explicações extras):
{
  "analysis_type": "count|list|aggregate|join|complex_analysis",
  "tables_needed": ["tabela1", "tabela2"],
  "operations": ["count", "filter", "join", "group_by", "metadata_query"],
  "complexity": "simple|medium|complex",
  "explanation": "Explicação do que será feito",
  "confidence": 0.95
}

SOLICITAÇÃO DO USUÁRIO: "${messageText}"`;

        try {
            const response = await this.anthropic.messages.create({
                model: this.model,
                max_tokens: 500,
                temperature: 0.1,
                messages: [{ role: 'user', content: prompt }]
            });

            const analysisText = response.content[0].text;
            return this.parseJSON(analysisText, {
                analysis_type: "list",
                tables_needed: availableTables.length > 0 ? [availableTables[0].table_name] : [],
                operations: ["count"],
                complexity: "simple",
                explanation: "Análise básica com descoberta dinâmica",
                confidence: 0.5
            });

        } catch (error) {
            console.error('❌ Erro no Agente Coordenador:', error);
            
            // Fallback inteligente baseado em contexto
            const smartFallback = this.createSmartFallback(messageText, availableTables, contextualInfo);
            return smartFallback;
        }
    }

    extractContextualReferences(messageText) {
        const text = messageText.toLowerCase();
        
        return {
            email: this.extractEmailFromText(text),
            table: this.extractTableFromText(text),
            sameEmail: /mesmo email|esse email|este email|email anterior/.test(text),
            sameTable: /mesma tabela|essa tabela|esta tabela|tabela anterior/.test(text),
            isSearch: /buscar|procurar|encontrar|localizar|verificar/.test(text),
            isCount: /quantos|quantidade|contar|total/.test(text),
            isList: /listar|mostrar|trazer|dados|informações/.test(text)
        };
    }

    extractEmailFromText(text) {
        const emailMatch = text.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
        return emailMatch ? emailMatch[1] : null;
    }

    extractTableFromText(text) {
        const tableKeywords = [
            'qualified_leads', 'engaged_leads', 'unified_leads', 'aula_views',
            'aula_navigations', 'script_downloads', 'social_actions', 'whatsapp_actions'
        ];
        
        for (const table of tableKeywords) {
            if (text.includes(table)) {
                return table;
            }
        }
        return null;
    }

    createSmartFallback(messageText, availableTables, contextualInfo) {
        const text = messageText.toLowerCase();
        
        // Detecta tipo de operação baseado em palavras-chave
        let analysis_type = "list";
        let operations = ["filter"];
        let tables_needed = [];
        
        if (contextualInfo.isCount) {
            analysis_type = "count";
            operations = ["count"];
        } else if (contextualInfo.isList && !contextualInfo.isSearch) {
            analysis_type = "list";
            operations = ["metadata_query"];
        }
        
        // Detecta tabela
        if (contextualInfo.table) {
            tables_needed = [contextualInfo.table];
        } else if (contextualInfo.sameTable && this.conversationContext.lastTable) {
            tables_needed = [this.conversationContext.lastTable];
        } else if (availableTables.length > 0) {
            // Se menciona email, provavelmente quer qualified_leads ou engaged_leads
            if (contextualInfo.email || contextualInfo.sameEmail) {
                const emailTables = availableTables.filter(t =>
                    t.table_name.includes('leads') || t.table_name.includes('qualified') || t.table_name.includes('engaged')
                );
                tables_needed = emailTables.length > 0 ? [emailTables[0].table_name] : [availableTables[0].table_name];
            } else {
                tables_needed = [availableTables[0].table_name];
            }
        }
        
        return {
            analysis_type,
            tables_needed,
            operations,
            complexity: "simple",
            explanation: `Fallback inteligente: ${analysis_type} em ${tables_needed.join(', ')}`,
            confidence: 0.7
        };
    }

    /**
     * AGENTE SCHEMA - Descobre estrutura das tabelas necessárias
     */
    async schemaAgent(tablesNeeded) {
        const schemas = [];

        for (const tableName of tablesNeeded) {
            try {
                // Verifica cache primeiro
                const cacheKey = `schema_${tableName}`;
                if (this.schemaCache.has(cacheKey)) {
                    const cached = this.schemaCache.get(cacheKey);
                    if (Date.now() - cached.timestamp < 300000) { // 5 minutos
                        schemas.push(cached.data);
                        continue;
                    }
                }

                // Busca schema real
                const result = await this.supabaseExecutor.describeTable(tableName);
                
                if (result.success) {
                    const schema = {
                        table_name: tableName,
                        columns: result.data.columns,
                        row_count: result.data.row_count,
                        sample_data: await this.getSampleData(tableName)
                    };
                    
                    schemas.push(schema);
                    
                    // Atualiza cache
                    this.schemaCache.set(cacheKey, {
                        data: schema,
                        timestamp: Date.now()
                    });
                    
                    console.log(`📋 Schema ${tableName}: ${schema.columns.length} colunas`);
                } else {
                    console.warn(`⚠️ Não foi possível obter schema de ${tableName}`);
                }

            } catch (error) {
                console.error(`❌ Erro ao obter schema de ${tableName}:`, error);
            }
        }

        return schemas;
    }

    /**
     * AGENTE SQL - Constrói queries SQL precisas e inteligentes
     */
    async queryAgent(intention, schemas) {
        const prompt = `Você é um Agente SQL Expert que constrói queries PostgreSQL perfeitas para Supabase.

SCHEMAS DISPONÍVEIS:
${schemas.map(s => `
Tabela: ${s.table_name}
Colunas: ${s.columns.join(', ')}
Registros: ${s.row_count}
Amostra: ${JSON.stringify(s.sample_data?.slice(0, 1) || [])}
`).join('\n')}

CONTEXTO DA CONVERSA:
${this.conversationContext.lastEmail ? `- Email em contexto: ${this.conversationContext.lastEmail}` : ''}
${this.conversationContext.lastTable ? `- Tabela em contexto: ${this.conversationContext.lastTable}` : ''}

INTENÇÃO ANALISADA:
${JSON.stringify(intention, null, 2)}

INSTRUÇÕES CRÍTICAS:
1. Se intention.operations inclui "filter" e há email em contexto, USE WHERE email = '${this.conversationContext.lastEmail || 'email_contexto'}'
2. Para "quantidade distintas" ou "emails únicos" → USE COUNT(DISTINCT coluna)
3. Para "últimos registros" → USE ORDER BY timestamp/created_at DESC LIMIT N
4. Para "filtros" → USE WHERE com condições apropriadas
5. Para "agregações" → USE SUM, AVG, MAX, MIN conforme necessário
6. Para "joins" → USE INNER/LEFT JOIN quando necessário

EXEMPLOS CONTEXTUAIS:
- Se buscar dados do "mesmo email" → USE WHERE email = '${this.conversationContext.lastEmail || 'email_anterior'}'
- Se buscar na "mesma tabela" → USE FROM ${this.conversationContext.lastTable || 'tabela_anterior'}

RESPONDA APENAS EM JSON VÁLIDO (sem markdown):
{
  "sql_query": "SELECT * FROM qualified_leads WHERE email = 'exemplo@email.com'",
  "query_type": "count_distinct|simple_count|list|aggregation|complex",
  "explanation": "Query SQL construída baseada no contexto",
  "expected_result": "dados do email específico"
}`;
try {
    const response = await this.anthropic.messages.create({
        model: this.model,
        max_tokens: 800,
        temperature: 0.1,
        messages: [{ role: 'user', content: prompt }]
    });

    const sqlResponseText = response.content[0].text;
    const sqlStrategy = this.parseJSON(sqlResponseText, {
        sql_query: `SELECT COUNT(*) FROM ${intention.tables_needed[0] || 'qualified_leads'}`,
        query_type: "simple_count",
        explanation: "Query básica de fallback",
        expected_result: "contagem simples"
    });

    console.log(`🔍 SQL gerado: ${sqlStrategy.sql_query}`);

    // Executa a query SQL diretamente
    const result = await this.executeSQLQuery(sqlStrategy.sql_query);

    return {
        success: true,
        sql_strategy: sqlStrategy,
        results: [result],
        total_queries: 1
    };

} catch (error) {
    console.error('❌ Erro no Agente SQL:', error);
    return {
        success: false,
        error: error.message,
        sql_strategy: null,
        results: []
    };
}
    }

    /**
     * AGENTE ANALYST - Analisa resultados e gera insights
     */
    async analystAgent(queryResult, intention, originalMessage) {
        if (!queryResult.success) {
            return {
                insights: [],
                summary: "Não foi possível analisar os dados devido a erro na consulta",
                recommendations: []
            };
        }

        const prompt = `Você é o Agente Analyst especialista em análise de dados de negócio.

DADOS ANALISADOS:
${JSON.stringify(queryResult.results, null, 2)}

CONTEXTO DA SOLICITAÇÃO:
Pergunta original: "${originalMessage}"
Intenção: ${JSON.stringify(intention)}

REGRAS ESTRITAS:
1. Insights DEVEM ser baseados APENAS nos dados fornecidos
2. NÃO faça suposições ou inferências além dos dados
3. Use APENAS métricas quantificáveis
4. Máximo de 3 insights por análise
5. Máximo de 2 recomendações por análise
6. NÃO use linguagem subjetiva ou emocional

RESPONDA EM JSON:
{
  "insights": [
    {
      "metric": "nome_da_metrica",
      "value": "valor_numerico",
      "comparison": "comparacao_com_anterior",
      "significance": "alta|media|baixa"
    }
  ],
  "summary": "Resumo técnico dos dados (máximo 100 caracteres)",
  "recommendations": [
    {
      "action": "acao_especifica",
      "metric_target": "metrica_alvo",
      "expected_impact": "impacto_esperado"
    }
  ],
  "key_metrics": {
    "metric1": "valor_numerico",
    "metric2": "valor_numerico"
  }
}`;

        try {
            const response = await this.anthropic.messages.create({
                model: this.model,
                max_tokens: 500,
                temperature: 0.3,
                messages: [{ role: 'user', content: prompt }]
            });

            const analysisText = response.content[0].text;
            return this.parseJSON(analysisText, {
                insights: [{
                    metric: "total_records",
                    value: queryResult.results[0]?.data?.count || 0,
                    comparison: "n/a",
                    significance: "baixa"
                }],
                summary: "Análise básica dos dados",
                recommendations: [],
                key_metrics: {
                    total: queryResult.results[0]?.data?.count || 0
                }
            });

        } catch (error) {
            console.error('❌ Erro no Agente Analyst:', error);
            return {
                insights: [{
                    metric: "error",
                    value: "n/a",
                    comparison: "n/a",
                    significance: "baixa"
                }],
                summary: "Erro na análise dos dados",
                recommendations: [],
                key_metrics: {}
            };
        }
    }

    /**
     * AGENTE FORMATTER - Formata resposta para WhatsApp
     */
    async formatterAgent(analysis, queryResult, originalMessage) {
        const prompt = `Você é o Agente Formatter especialista em comunicação via WhatsApp.

ANÁLISE GERADA:
${JSON.stringify(analysis, null, 2)}

RESULTADOS DAS QUERIES:
${JSON.stringify(queryResult.results, null, 2)}

PERGUNTA ORIGINAL: "${originalMessage}"

TAREFA: Crie uma resposta amigável e clara para WhatsApp.

DIRETRIZES:
- Use emojis apropriados
- Destaque números importantes com *negrito*
- Seja conciso mas informativo
- Máximo 4000 caracteres
- Estruture com títulos e listas
- Inclua insights de negócio

RESPONDA APENAS O TEXTO FORMATADO (sem JSON):`;

        try {
            const response = await this.anthropic.messages.create({
                model: this.model,
                max_tokens: 1200,
                temperature: 0.7,
                messages: [{ role: 'user', content: prompt }]
            });

            return response.content[0].text.trim();

        } catch (error) {
            console.error('❌ Erro no Agente Formatter:', error);
            
            // Fallback para formatação básica
            if (queryResult.success && queryResult.results.length > 0) {
                const result = queryResult.results[0];
                if (result.data && typeof result.data.count === 'number') {
                    return `📊 *Resultado*\n\n🔢 Total: *${result.data.count.toLocaleString('pt-BR')}* registros\n\n💡 Dados obtidos com sucesso!`;
                }
                return `📊 *Resultado*\n\n✅ Consulta executada com sucesso\n📋 ${queryResult.results.length} resultado(s) encontrado(s)`;
            }
            
            return `❌ *Erro*\n\nNão foi possível processar sua solicitação. Tente reformular a pergunta.`;
        }
    }

    /**
     * MÉTODOS AUXILIARES
     */
    async discoverAvailableTables() {
        try {
            const result = await this.supabaseExecutor.listTables();
            if (result.success && result.data) {
                return result.data;
            }
            return [];
        } catch (error) {
            console.error('❌ Erro ao descobrir tabelas:', error);
            return [];
        }
    }

    async executeSQLQuery(sqlQuery) {
        try {
            console.log(`🔍 Executando SQL: ${sqlQuery}`);
            
            // Para COUNT DISTINCT, usa fetch direto para SQL real
            if (sqlQuery.toLowerCase().includes('count(distinct')) {
                return await this.executeCountDistinctSQL(sqlQuery);
            }
            
            // Para outras queries, converte para operação Supabase
            const result = await this.convertSQLToSupabaseOperation(sqlQuery);
            
            console.log(`✅ SQL convertido e executado:`, result);
            return result;

        } catch (error) {
            console.error('❌ Erro ao executar SQL:', error);
            return {
                success: false,
                error: error.message,
                data: null
            };
        }
    }

    async executeCountDistinctSQL(sqlQuery) {
        try {
            // Executa SQL direto via fetch para COUNT DISTINCT preciso
            const response = await fetch(`${this.supabaseExecutor.supabaseUrl}/rest/v1/rpc/count_distinct_emails`, {
                method: 'POST',
                headers: {
                    'apikey': this.supabaseExecutor.supabaseKey,
                    'Authorization': `Bearer ${this.supabaseExecutor.supabaseKey}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    table_name: this.extractTableFromSQL(sqlQuery),
                    column_name: this.extractColumnFromSQL(sqlQuery)
                })
            });

            if (response.ok) {
                const result = await response.json();
                return {
                    success: true,
                    data: { count: result },
                    sql_query: sqlQuery
                };
            } else {
                // Fallback: usa método JavaScript mas com ALL records
                return await this.executeCountDistinctFallback(sqlQuery);
            }

        } catch (error) {
            console.error('❌ Erro SQL direto, usando fallback:', error);
            return await this.executeCountDistinctFallback(sqlQuery);
        }
    }

    async executeCountDistinctFallback(sqlQuery) {
        const table = this.extractTableFromSQL(sqlQuery);
        const column = this.extractColumnFromSQL(sqlQuery);
        
        console.log(`🔍 COUNT DISTINCT fallback: ${table}.${column}`);
        
        // Usa o método corrigido do executor com paginação
        const result = await this.supabaseExecutor.performAggregation(table, {
            type: 'count_distinct',
            column: column
        });
        
        if (result.success) {
            return {
                success: true,
                data: {
                    count: result.data.result,
                    operation: 'count_distinct',
                    table: table,
                    column: column
                },
                sql_query: sqlQuery
            };
        }

        return {
            success: false,
            error: result.error || 'Erro na contagem',
            data: null
        };
    }

    extractTableFromSQL(sql) {
        const match = sql.toLowerCase().match(/from\s+(\w+)/);
        return match ? match[1] : 'unknown';
    }

    extractColumnFromSQL(sql) {
        const match = sql.toLowerCase().match(/count\(distinct\s+(\w+)\)/);
        return match ? match[1] : 'email';
    }

    async convertSQLToSupabaseOperation(sqlQuery) {
        // REMOVIDO: Hardcode de parsing SQL
        // NOVA ABORDAGEM: Usar MCP diretamente para execução SQL
        console.log(`🔄 Executando SQL via MCP: ${sqlQuery}`);
        
        try {
            // Usa o servidor MCP para executar SQL diretamente
            const result = await this.executeSQLViaMCP(sqlQuery);
            return result;
        } catch (error) {
            console.error('❌ Erro ao executar SQL via MCP:', error);
            return {
                success: false,
                error: error.message,
                data: null
            };
        }
    }

    async executeSQLViaMCP(sqlQuery) {
        try {
            console.log(`🔧 Executando via MCP: ${sqlQuery}`);
            
            // Primeiro tenta execute_sql do MCP
            try {
                const result = await this.callMCPTool('execute_sql', { query: sqlQuery });
                if (result && result.success !== false) {
                    return {
                        success: true,
                        data: result.result || result.data || result,
                        message: 'Query executada via MCP execute_sql'
                    };
                }
            } catch (mcpError) {
                console.log('⚠️ MCP execute_sql não disponível, tentando alternativa...');
            }

            // Fallback: Converte SQL para operação MCP apropriada
            const mcpQuery = this.convertSQLToMCPQuery(sqlQuery);
            if (mcpQuery) {
                let result;
                
                // Usa a operação MCP apropriada baseada no tipo de query
                if (mcpQuery.operation === 'count_records') {
                    result = await this.callMCPTool('count_records', mcpQuery);
                } else {
                    result = await this.callMCPTool('query_records', mcpQuery);
                }
                
                return {
                    success: true,
                    data: result.records || result.data || result,
                    count: result.count || (result.records ? result.records.length : 0),
                    message: `Query executada via MCP ${mcpQuery.operation || 'query_records'}`
                };
            }

            throw new Error('Não foi possível executar a query via MCP');

        } catch (error) {
            console.error('❌ Erro na execução MCP:', error);
            throw error;
        }
    }

    async callMCPTool(toolName, args) {
        if (!this.mcpServer) {
            throw new Error('Servidor MCP não disponível');
        }

        try {
            console.log(`🔧 Chamando MCP tool: ${toolName}`, args);
            
            // Chama diretamente os métodos do servidor MCP
            let response;
            switch (toolName) {
                case 'query_records':
                    response = await this.mcpServer.queryRecords(args);
                    break;
                case 'execute_sql':
                    response = await this.mcpServer.executeSQL(args.query, args.parameters || []);
                    break;
                case 'count_records':
                    response = await this.mcpServer.countRecords(args.table_name, args.filters || []);
                    break;
                case 'aggregate_data':
                    response = await this.mcpServer.aggregateData(args);
                    break;
                default:
                    throw new Error(`Tool MCP não suportada: ${toolName}`);
            }

            if (response.isError) {
                throw new Error(response.content[0].text);
            }

            // Parse do resultado JSON
            const resultText = response.content[0].text;
            return JSON.parse(resultText);
            
        } catch (error) {
            console.error(`❌ Erro ao chamar MCP tool ${toolName}:`, error);
            throw error;
        }
    }

    convertSQLToMCPQuery(sqlQuery) {
        const sql = sqlQuery.toLowerCase();
        
        // Extrai informações básicas da SQL
        const tableMatch = sql.match(/from\s+(\w+)/);
        if (!tableMatch) return null;
        
        const table = tableMatch[1];
        const query = { table_name: table };
        
        // Para COUNT queries, usa count_records do MCP
        if (sql.includes('count(')) {
            // Detecta WHERE simples para filtros
            if (sql.includes('where')) {
                const whereMatch = sql.match(/where\s+(\w+)\s*=\s*'([^']+)'/);
                if (whereMatch) {
                    query.filters = [{
                        column: whereMatch[1],
                        operator: 'eq',
                        value: whereMatch[2]
                    }];
                }
            }
            return { operation: 'count_records', ...query };
        }
        
        // Para SELECT simples
        const selectMatch = sql.match(/select\s+(.*?)\s+from/);
        if (selectMatch && selectMatch[1] !== '*') {
            const columns = selectMatch[1].split(',').map(col => col.trim());
            // Remove funções SQL complexas que o Supabase não suporta
            const validColumns = columns.filter(col =>
                !col.includes('(') && !col.includes('case') && !col.includes('when')
            );
            if (validColumns.length > 0) {
                query.columns = validColumns;
            }
        }
        
        // Detecta WHERE simples
        if (sql.includes('where')) {
            const whereMatch = sql.match(/where\s+(\w+)\s*=\s*'([^']+)'/);
            if (whereMatch) {
                query.filters = [{
                    column: whereMatch[1],
                    operator: 'eq',
                    value: whereMatch[2]
                }];
            }
        }
        
        // Detecta LIMIT
        const limitMatch = sql.match(/limit\s+(\d+)/);
        if (limitMatch) {
            query.limit = parseInt(limitMatch[1]);
        } else {
            query.limit = 100; // Limite padrão
        }
        
        return query;
    }

    async getSampleData(tableName) {
        try {
            const result = await this.supabaseExecutor.listRecords(tableName, { limit: 2 });
            return result.success ? result.data : [];
        } catch (error) {
            return [];
        }
    }

    async executeQuery(query) {
        try {
            switch (query.operation) {
                case 'count':
                    return await this.supabaseExecutor.countRecords(query.table, query.filters || []);
                
                case 'list':
                    return await this.supabaseExecutor.listRecords(query.table, {
                        filters: query.filters || [],
                        limit: query.limit || 10,
                        orderBy: query.order_by,
                        columns: query.columns
                    });
                
                case 'aggregate':
                    return await this.supabaseExecutor.performAggregation(query.table, {
                        type: query.aggregation_type,
                        column: query.column,
                        filters: query.filters || []
                    });
                
                default:
                    return await this.supabaseExecutor.countRecords(query.table);
            }
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }

    parseJSON(text, fallback) {
        try {
            // Múltiplas tentativas de limpeza
            let cleanText = text.trim();
            
            // Remove markdown
            if (cleanText.includes('```json')) {
                cleanText = cleanText.replace(/```json\s*/, '').replace(/\s*```$/, '');
            }
            if (cleanText.includes('```')) {
                cleanText = cleanText.replace(/```\s*/, '').replace(/\s*```$/, '');
            }
            
            // Remove texto antes e depois do JSON
            const jsonStart = cleanText.indexOf('{');
            const jsonEnd = cleanText.lastIndexOf('}');
            if (jsonStart !== -1 && jsonEnd !== -1 && jsonEnd > jsonStart) {
                cleanText = cleanText.substring(jsonStart, jsonEnd + 1);
            }
            
            // Primeira tentativa
            try {
                return JSON.parse(cleanText);
            } catch (firstError) {
                // Segunda tentativa: corrige aspas simples
                const fixedQuotes = cleanText.replace(/'/g, '"');
                try {
                    return JSON.parse(fixedQuotes);
                } catch (secondError) {
                    // Terceira tentativa: remove comentários
                    const noComments = cleanText.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');
                    return JSON.parse(noComments);
                }
            }
        } catch (error) {
            console.warn('⚠️ Erro ao fazer parse JSON após múltiplas tentativas, usando fallback');
            console.warn('📝 Texto original:', text.substring(0, 200));
            return fallback;
        }
    }

    updateConversationContext(intention, messageText) {
        // Atualiza contexto baseado na intenção identificada
        if (intention.tables_needed && intention.tables_needed.length > 0) {
            this.conversationContext.lastTable = intention.tables_needed[0];
        }
        
        if (intention.operations && intention.operations.length > 0) {
            this.conversationContext.lastOperation = intention.operations[0];
        }
        
        // Extrai email da mensagem
        const email = this.extractEmailFromText(messageText.toLowerCase());
        if (email) {
            this.conversationContext.lastEmail = email;
        }
        
        // Mantém histórico das últimas 5 queries
        this.conversationContext.recentQueries.unshift({
            message: messageText,
            intention: intention,
            timestamp: Date.now()
        });
        
        if (this.conversationContext.recentQueries.length > 5) {
            this.conversationContext.recentQueries.pop();
        }
    }

    async testAI() {
        try {
            const response = await this.anthropic.messages.create({
                model: this.model,
                max_tokens: 50,
                messages: [
                    {
                        role: 'user',
                        content: 'Teste de conexão - responda apenas "OK"'
                    }
                ]
            });

            console.log('🧠 Sistema Multiagentes respondeu:', response.content[0].text);
            return true;
        } catch (error) {
            console.error('❌ Erro no teste do Sistema Multiagentes:', error);
            return false;
        }
    }
}

module.exports = MultiAgentSystem;