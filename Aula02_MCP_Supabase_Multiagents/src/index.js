const express = require('express');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const dotenv = require('dotenv');
const WhatsAppBot = require('./whatsapp/bot');
const MultiAgentSystem = require('./ai/multiagent-system');
const SupabaseExecutor = require('./supabase/executor');
const ResponseFormatter = require('./formatters/response');

// Carrega variáveis de ambiente
dotenv.config();

// Previne múltiplas inicializações
if (global.systemRunning) {
    console.log('⚠️ Sistema já está rodando!');
    return;
}
global.systemRunning = true;

class WhatsAppAISystem {
    constructor() {
        this.app = express();
        this.port = process.env.PORT || 8080;
        this.whatsappBot = null;
        this.aiAgent = null;
        this.supabaseExecutor = null;
        this.responseFormatter = null;
        
        this.setupMiddleware();
        this.setupRoutes();
    }

    setupMiddleware() {
        this.app.use(express.json());
        this.app.use(express.urlencoded({ extended: true }));
    }

    setupRoutes() {
        this.app.get('/', (req, res) => {
            res.json({
                status: 'running',
                message: 'WhatsApp + IA + Supabase System',
                timestamp: new Date().toISOString()
            });
        });

        this.app.get('/health', (req, res) => {
            res.json({
                status: 'healthy',
                whatsapp: this.whatsappBot?.isReady || false,
                supabase: this.supabaseExecutor?.isConnected || false,
                ai: this.aiAgent?.isReady || false
            });
        });
    }

    async initialize() {
        try {
            console.log('🚀 Inicializando sistema WhatsApp + IA + Supabase...');

            // Inicializa componentes
            this.responseFormatter = new ResponseFormatter();
            this.supabaseExecutor = new SupabaseExecutor();
            this.aiAgent = new MultiAgentSystem(this.supabaseExecutor);
            this.whatsappBot = new WhatsAppBot(this.aiAgent, this.responseFormatter);

            // Testa conexão com Supabase
            await this.supabaseExecutor.testConnection();
            console.log('✅ Conexão com Supabase estabelecida');

            // Inicializa WhatsApp Bot
            await this.whatsappBot.initialize();
            console.log('✅ WhatsApp Bot inicializado');

            // Inicia servidor Express
            this.app.listen(this.port, () => {
                console.log(`🌐 Servidor rodando na porta ${this.port}`);
                console.log(`📱 Sistema pronto para receber mensagens!`);
            });

        } catch (error) {
            console.error('❌ Erro ao inicializar sistema:', error);
            process.exit(1);
        }
    }

    async shutdown() {
        console.log('🛑 Encerrando sistema...');
        
        if (this.whatsappBot) {
            await this.whatsappBot.destroy();
        }
        
        process.exit(0);
    }
}

// Inicializa o sistema
const system = new WhatsAppAISystem();

// Handlers para encerramento gracioso
process.on('SIGINT', () => system.shutdown());
process.on('SIGTERM', () => system.shutdown());

// Inicia o sistema
system.initialize().catch(console.error);

module.exports = WhatsAppAISystem;