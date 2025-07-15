const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

class WhatsAppBot {
    constructor(aiAgent, responseFormatter) {
        this.aiAgent = aiAgent;
        this.responseFormatter = responseFormatter;
        this.client = null;
        this.isReady = false;
        this.sessionPath = process.env.WHATSAPP_SESSION_PATH || './whatsapp-session';
        this.clientId = process.env.WHATSAPP_CLIENT_ID || 'whatsapp-ai-bot';
    }

    async initialize() {
        console.log('📱 Inicializando WhatsApp Bot...');

        this.client = new Client({
            authStrategy: new LocalAuth({
                clientId: this.clientId,
                dataPath: this.sessionPath
            }),
            puppeteer: {
                headless: true,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu'
                ]
            }
        });

        this.setupEventHandlers();
        
        await this.client.initialize();
    }

    setupEventHandlers() {
        // QR Code para autenticação
        this.client.on('qr', (qr) => {
            console.log('📱 Escaneie o QR Code abaixo com seu WhatsApp:');
            qrcode.generate(qr, { small: true });
        });

        // Cliente pronto
        this.client.on('ready', () => {
            console.log('✅ WhatsApp Bot conectado e pronto!');
            this.isReady = true;
        });

        // Mensagem recebida
        this.client.on('message', async (message) => {
            await this.handleMessage(message);
        });

        // Desconectado
        this.client.on('disconnected', (reason) => {
            console.log('❌ WhatsApp desconectado:', reason);
            this.isReady = false;
        });

        // Erro de autenticação
        this.client.on('auth_failure', (msg) => {
            console.error('❌ Falha na autenticação:', msg);
        });
    }

    async handleMessage(message) {
        try {
            // Ignora mensagens próprias e de grupos (opcional)
            if (message.fromMe) return;
            
            const contact = await message.getContact();
            const chat = await message.getChat();
            
            console.log(`📨 Mensagem de ${contact.name || contact.number}: ${message.body}`);

            // Verifica se é uma mensagem de texto
            if (message.type !== 'chat') {
                await message.reply('🤖 Desculpe, eu só processo mensagens de texto no momento.');
                return;
            }

            // Mostra que está processando
            await chat.sendStateTyping();

            // Processa mensagem com IA
            const response = await this.processMessageWithAI(message.body, contact);
            
            // Envia resposta
            if (response) {
                await message.reply(response);
                console.log(`✅ Resposta enviada para ${contact.name || contact.number}`);
            }

        } catch (error) {
            console.error('❌ Erro ao processar mensagem:', error);
            await message.reply('🤖 Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente.');
        }
    }

    async processMessageWithAI(messageText, contact) {
        try {
            // Contexto do usuário
            const userContext = {
                name: contact.name || 'Usuário',
                number: contact.number,
                timestamp: new Date().toISOString()
            };

            // Processa com IA
            const aiResponse = await this.aiAgent.processMessage(messageText, userContext);
            
            // Formata resposta
            const formattedResponse = this.responseFormatter.format(aiResponse);
            
            return formattedResponse;

        } catch (error) {
            console.error('❌ Erro no processamento IA:', error);
            return '🤖 Desculpe, não consegui processar sua solicitação. Verifique se sua mensagem está clara e tente novamente.';
        }
    }

    async sendMessage(number, message) {
        try {
            if (!this.isReady) {
                throw new Error('WhatsApp Bot não está pronto');
            }

            const chatId = number.includes('@c.us') ? number : `${number}@c.us`;
            await this.client.sendMessage(chatId, message);
            
            return true;
        } catch (error) {
            console.error('❌ Erro ao enviar mensagem:', error);
            return false;
        }
    }

    async destroy() {
        if (this.client) {
            await this.client.destroy();
            console.log('🛑 WhatsApp Bot encerrado');
        }
    }

    // Métodos utilitários
    getStatus() {
        return {
            ready: this.isReady,
            clientId: this.clientId,
            sessionPath: this.sessionPath
        };
    }
}

module.exports = WhatsAppBot;