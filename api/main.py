// main.js - Selfbot Completo para Discord
// AVISO: Selfbots violam os Termos de Serviço do Discord. Use por sua conta e risco.

const { Client, GatewayIntentBits } = require('discord.js-selfbot-v13');
const { joinVoiceChannel, createAudioPlayer, createAudioResource, VoiceConnectionStatus, entersState } = require('@discordjs/voice');
const fs = require('fs');
const path = require('path');

// CONFIGURAÇÃO PRINCIPAL - EDITAR AQUI
const CONFIG = {
    // ⚠️ COLOQUE SEU TOKEN PRINCIPAL AQUI ⚠️
    MAIN_TOKEN: 'SEU_TOKEN_PRINCIPAL_AQUI',
    
    tokensFile: 'tokens.json',
    secondaryTokens: new Map(),
    status: {
        text: '24/7 Voice Chat',
        emoji: '🔊',
        type: 'LISTENING'
    },
    follow: {
        enabled: false,
        targetUserId: null,
        lastChannelId: null
    },
    random: {
        enabled: false,
        interval: 30, // minutos
        intervalId: null
    },
    delays: {
        min: 30000, // 30 segundos
        max: 60000  // 60 segundos
    }
};

// Classe para gerenciar cada conta secundária
class SecondaryAccount {
    constructor(token, id) {
        this.token = token;
        this.id = id;
        this.client = new Client({
            intents: [
                GatewayIntentBits.Guilds,
                GatewayIntentBits.GuildVoiceStates,
                GatewayIntentBits.GuildMessages,
                GatewayIntentBits.MessageContent
            ]
        });
        this.voiceConnection = null;
        this.currentChannel = null;
        this.isConnected = false;
        
        this.setupClient();
    }

    setupClient() {
        this.client.on('ready', () => {
            console.log(`[Secondary ${this.id}] Logado como ${this.client.user.tag}`);
            this.updateStatus();
        });

        this.client.on('voiceStateUpdate', (oldState, newState) => {
            this.handleVoiceStateUpdate(oldState, newState);
        });

        this.client.on('error', (error) => {
            console.error(`[Secondary ${this.id}] Erro:`, error);
        });
    }

    async updateStatus() {
        try {
            await this.client.user.setPresence({
                activities: [{
                    name: CONFIG.status.text,
                    type: CONFIG.status.type,
                    emoji: CONFIG.status.emoji
                }],
                status: 'online'
            });
            console.log(`[Secondary ${this.id}] Status atualizado`);
        } catch (error) {
            console.error(`[Secondary ${this.id}] Erro ao atualizar status:`, error);
        }
    }

    async changeAvatar(url) {
        try {
            const response = await fetch(url);
            const buffer = await response.arrayBuffer();
            await this.client.user.setAvatar(Buffer.from(buffer));
            console.log(`[Secondary ${this.id}] Avatar alterado com sucesso`);
        } catch (error) {
            console.error(`[Secondary ${this.id}] Erro ao alterar avatar:`, error);
        }
    }

    handleVoiceStateUpdate(oldState, newState) {
        // Verificar se é o usuário alvo do follow mode
        if (CONFIG.follow.enabled && newState.member && newState.member.id === CONFIG.follow.targetUserId) {
            this.handleFollowMode(newState);
        }
    }

    handleFollowMode(newState) {
        if (newState.channelId && newState.channelId !== this.currentChannel) {
            // Usuário entrou em um canal de voz
            console.log(`[Secondary ${this.id}] Usuário alvo entrou no canal ${newState.channelId}`);
            setTimeout(() => {
                this.joinVoiceChannel(newState.channelId, newState.guild.id);
                CONFIG.follow.lastChannelId = newState.channelId;
            }, this.getRandomDelay());
        } else if (!newState.channelId && CONFIG.follow.lastChannelId === this.currentChannel) {
            // Usuário saiu do canal
            console.log(`[Secondary ${this.id}] Usuário alvo saiu do canal`);
            this.leaveVoiceChannel();
            CONFIG.follow.lastChannelId = null;
        }
    }

    async joinVoiceChannel(channelId, guildId) {
        if (this.isConnected) {
            this.leaveVoiceChannel();
            await new Promise(resolve => setTimeout(resolve, 2000));
        }

        try {
            const guild = this.client.guilds.cache.get(guildId);
            if (!guild) {
                console.log(`[Secondary ${this.id}] Guild ${guildId} não encontrada`);
                return;
            }

            const channel = guild.channels.cache.get(channelId);
            if (!channel || !channel.isVoiceBased()) {
                console.log(`[Secondary ${this.id}] Canal ${channelId} inválido`);
                return;
            }

            // Verificar se já tem outra conta no canal
            const membersInChannel = channel.members.filter(member => 
                Array.from(CONFIG.secondaryTokens.values()).some(acc => acc.client.user && acc.client.user.id === member.id)
            );

            if (membersInChannel.size > 0) {
                console.log(`[Secondary ${this.id}] Já tem uma conta no canal ${channelId}`);
                return; // Já tem uma conta no canal
            }

            console.log(`[Secondary ${this.id}] Conectando ao canal ${channel.name} em ${guild.name}`);

            this.voiceConnection = joinVoiceChannel({
                channelId: channelId,
                guildId: guildId,
                adapterCreator: guild.voiceAdapterCreator,
                selfDeaf: false,
                selfMute: true
            });

            this.voiceConnection.on(VoiceConnectionStatus.Ready, () => {
                console.log(`[Secondary ${this.id}] Conectado ao canal de voz em ${guild.name}`);
                this.isConnected = true;
                this.currentChannel = channelId;
            });

            this.voiceConnection.on(VoiceConnectionStatus.Disconnected, async () => {
                console.log(`[Secondary ${this.id}] Desconectado do canal de voz`);
                this.isConnected = false;
                this.currentChannel = null;
                
                if (CONFIG.follow.enabled && CONFIG.follow.lastChannelId === channelId) {
                    // Tentar reconectar se ainda estiver no modo follow
                    console.log(`[Secondary ${this.id}] Tentando reconectar no modo follow`);
                    setTimeout(() => {
                        this.joinVoiceChannel(channelId, guildId);
                    }, this.getRandomDelay());
                } else if (CONFIG.random.enabled) {
                    // No modo aleatório, buscar novo canal após delay
                    setTimeout(() => {
                        this.findRandomVoiceChannel();
                    }, this.getRandomDelay());
                }
            });

            this.voiceConnection.on('error', (error) => {
                console.error(`[Secondary ${this.id}] Erro na conexão de voz:`, error);
            });

        } catch (error) {
            console.error(`[Secondary ${this.id}] Erro ao conectar no canal de voz:`, error);
        }
    }

    leaveVoiceChannel() {
        if (this.voiceConnection) {
            try {
                this.voiceConnection.destroy();
                console.log(`[Secondary ${this.id}] Conexão de voz destruída`);
            } catch (error) {
                console.error(`[Secondary ${this.id}] Erro ao destruir conexão:`, error);
            }
            this.voiceConnection = null;
        }
        this.isConnected = false;
        this.currentChannel = null;
    }

    async findRandomVoiceChannel() {
        if (!CONFIG.random.enabled || this.isConnected) return;

        try {
            const voiceChannels = [];
            
            for (const guild of this.client.guilds.cache.values()) {
                const channels = guild.channels.cache.filter(ch => 
                    ch.isVoiceBased() && ch.members.size > 0
                );
                
                for (const channel of channels.values()) {
                    // Verificar se já tem alguma conta no canal
                    const hasBot = channel.members.some(member => 
                        Array.from(CONFIG.secondaryTokens.values()).some(acc => 
                            acc.client.user && acc.client.user.id === member.id
                        )
                    );

                    if (!hasBot) {
                        voiceChannels.push({ channel, guild });
                    }
                }
            }

            if (voiceChannels.length > 0) {
                const randomChannel = voiceChannels[Math.floor(Math.random() * voiceChannels.length)];
                console.log(`[Secondary ${this.id}] Encontrado canal aleatório: ${randomChannel.channel.name}`);
                this.joinVoiceChannel(randomChannel.channel.id, randomChannel.guild.id);
            } else {
                console.log(`[Secondary ${this.id}] Nenhum canal de voz disponível encontrado`);
            }
        } catch (error) {
            console.error(`[Secondary ${this.id}] Erro ao buscar canal aleatório:`, error);
        }
    }

    getRandomDelay() {
        return Math.floor(Math.random() * (CONFIG.delays.max - CONFIG.delays.min + 1)) + CONFIG.delays.min;
    }

    async login() {
        try {
            await this.client.login(this.token);
        } catch (error) {
            console.error(`[Secondary ${this.id}] Erro ao fazer login:`, error);
        }
    }

    logout() {
        this.leaveVoiceChannel();
        if (this.client) {
            this.client.destroy();
        }
    }
}

// Classe principal para gerenciar o selfbot
class SelfBotManager {
    constructor() {
        this.mainClient = null;
        this.loadTokens();
        this.setupMainClient();
    }

    loadTokens() {
        try {
            if (fs.existsSync(CONFIG.tokensFile)) {
                const data = JSON.parse(fs.readFileSync(CONFIG.tokensFile, 'utf8'));
                
                if (data.secondaryTokens) {
                    data.secondaryTokens.forEach((token, index) => {
                        CONFIG.secondaryTokens.set(index + 1, new SecondaryAccount(token, index + 1));
                    });
                    console.log(`[Manager] ${CONFIG.secondaryTokens.size} contas secundárias carregadas`);
                }
            }
        } catch (error) {
            console.error('Erro ao carregar tokens:', error);
        }
    }

    saveTokens() {
        try {
            const data = {
                secondaryTokens: Array.from(CONFIG.secondaryTokens.values()).map(acc => acc.token)
            };
            fs.writeFileSync(CONFIG.tokensFile, JSON.stringify(data, null, 2));
            console.log('[Manager] Tokens salvos no arquivo');
        } catch (error) {
            console.error('Erro ao salvar tokens:', error);
        }
    }

    setupMainClient() {
        if (!CONFIG.MAIN_TOKEN || CONFIG.MAIN_TOKEN === 'SEU_TOKEN_PRINCIPAL_AQUI') {
            console.log('❌ Token principal não configurado! Edite o arquivo e coloque seu token.');
            process.exit(1);
        }

        this.mainClient = new Client({
            intents: [
                GatewayIntentBits.Guilds,
                GatewayIntentBits.GuildMessages,
                GatewayIntentBits.MessageContent
            ]
        });

        this.mainClient.on('ready', () => {
            console.log(`[Principal] Logado como ${this.mainClient.user.tag}`);
            // Conta principal NÃO altera status, apenas comanda
        });

        this.mainClient.on('messageCreate', (message) => {
            if (message.author.id !== this.mainClient.user.id) return;
            this.handleCommand(message);
        });

        this.mainClient.on('error', (error) => {
            console.error('[Principal] Erro:', error);
        });

        this.mainClient.login(CONFIG.MAIN_TOKEN).catch(error => {
            console.error('[Principal] Erro ao fazer login:', error);
            process.exit(1);
        });
    }

    handleCommand(message) {
        const args = message.content.slice(1).trim().split(/ +/);
        const command = args.shift().toLowerCase();

        switch (command) {
            case 'help':
                this.showHelp(message);
                break;
            case 'tokenadd':
                this.tokenAdd(message, args);
                break;
            case 'tokenlist':
                this.tokenList(message);
                break;
            case 'tokenremove':
                this.tokenRemove(message, args);
                break;
            case 'avatar':
                this.changeAvatar(message, args);
                break;
            case 'status':
                this.changeStatus(message, args);
                break;
            case 'follow':
                this.followUser(message, args);
                break;
            case 'unfollow':
                this.unfollowUser(message);
                break;
            case 'randomcalls':
                this.handleRandomCalls(message, args);
                break;
            default:
                // Comando não reconhecido
                break;
        }
    }

    showHelp(message) {
        const helpText = `
**Comandos Disponíveis:**

**Gerenciamento de Tokens:**
!tokenadd <token> - Adicionar nova conta secundária
!tokenlist - Listar contas com números de ID
!tokenremove <número> - Remover conta da lista

**Personalização (apenas secundárias):**
!avatar <url_da_imagem> - Mudar avatar das contas secundárias
!status <texto> [emoji] [tipo] - Configurar status das secundárias

**Modo Follow:**
!follow <userID> - Contas secundárias seguem usuário em calls
!unfollow - Parar de seguir

**Modo Aleatório 24/7:**
!randomcalls start <tempo_minutos> - Iniciar modo aleatório
!randomcalls stop - Parar todas as calls

**💡 A conta principal apenas comanda, não entra em calls nem altera status!**
        `;
        message.edit(helpText).catch(() => {});
    }

    tokenAdd(message, args) {
        if (args.length === 0) {
            message.edit('❌ Uso: !tokenadd <token>').catch(() => {});
            return;
        }

        const token = args[0];
        const newId = CONFIG.secondaryTokens.size + 1;
        
        const newAccount = new SecondaryAccount(token, newId);
        CONFIG.secondaryTokens.set(newId, newAccount);
        newAccount.login();
        
        this.saveTokens();
        message.edit(`✅ Conta secundária #${newId} adicionada com sucesso!`).catch(() => {});
    }

    tokenList(message) {
        if (CONFIG.secondaryTokens.size === 0) {
            message.edit('❌ Nenhuma conta secundária configurada.').catch(() => {});
            return;
        }

        let list = '**Contas Secundárias:**\n';
        CONFIG.secondaryTokens.forEach((account, id) => {
            const status = account.client.readyAt ? '✅ Online' : '❌ Offline';
            const connected = account.isConnected ? '🔊 Conectada' : '🔇 Desconectada';
            list += `#${id} - ${status} - ${connected}\n`;
        });

        message.edit(list).catch(() => {});
    }

    tokenRemove(message, args) {
        if (args.length === 0) {
            message.edit('❌ Uso: !tokenremove <número>').catch(() => {});
            return;
        }

        const id = parseInt(args[0]);
        if (!CONFIG.secondaryTokens.has(id)) {
            message.edit('❌ ID não encontrado.').catch(() => {});
            return;
        }

        const account = CONFIG.secondaryTokens.get(id);
        account.logout();
        CONFIG.secondaryTokens.delete(id);
        
        this.saveTokens();
        message.edit(`✅ Conta #${id} removida com sucesso!`).catch(() => {});
    }

    async changeAvatar(message, args) {
        if (args.length === 0) {
            message.edit('❌ Uso: !avatar <url_da_imagem>').catch(() => {});
            return;
        }

        const avatarUrl = args[0];
        message.edit('🔄 Alterando avatares das contas secundárias...').catch(() => {});

        const promises = Array.from(CONFIG.secondaryTokens.values()).map(account => 
            account.changeAvatar(avatarUrl)
        );

        await Promise.all(promises);
        message.edit('✅ Avatares das contas secundárias alterados com sucesso!').catch(() => {});
    }

    async changeStatus(message, args) {
        if (args.length === 0) {
            message.edit('❌ Uso: !status <texto> [emoji] [tipo]').catch(() => {});
            return;
        }

        CONFIG.status.text = args[0];
        if (args[1]) CONFIG.status.emoji = args[1];
        if (args[2]) CONFIG.status.type = args[2].toUpperCase();

        const promises = Array.from(CONFIG.secondaryTokens.values()).map(account => 
            account.updateStatus()
        );

        await Promise.all(promises);
        message.edit('✅ Status das contas secundárias atualizado!').catch(() => {});
    }

    followUser(message, args) {
        if (args.length === 0) {
            message.edit('❌ Uso: !follow <userID>').catch(() => {});
            return;
        }

        CONFIG.follow.enabled = true;
        CONFIG.follow.targetUserId = args[0];
        
        if (CONFIG.random.enabled) {
            this.stopRandomCalls();
        }

        message.edit(`✅ Modo follow ativado para o usuário ${args[0]}`).catch(() => {});
        
        // Iniciar follow imediatamente para contas conectadas
        CONFIG.secondaryTokens.forEach(account => {
            if (account.isConnected) {
                account.leaveVoiceChannel();
            }
        });
    }

    unfollowUser(message) {
        CONFIG.follow.enabled = false;
        CONFIG.follow.targetUserId = null;
        CONFIG.follow.lastChannelId = null;

        // Desconectar todas as contas secundárias
        CONFIG.secondaryTokens.forEach(account => {
            account.leaveVoiceChannel();
        });

        message.edit('✅ Modo follow desativado.').catch(() => {});
    }

    handleRandomCalls(message, args) {
        const subcommand = args[0]?.toLowerCase();

        switch (subcommand) {
            case 'start':
                const interval = args[1] ? parseInt(args[1]) : 30;
                this.startRandomCalls(message, interval);
                break;
            case 'stop':
                this.stopRandomCalls();
                message.edit('✅ Modo aleatório parado.').catch(() => {});
                break;
            default:
                message.edit('❌ Uso: !randomcalls start <tempo> ou !randomcalls stop').catch(() => {});
        }
    }

    startRandomCalls(message, interval) {
        if (CONFIG.follow.enabled) {
            message.edit('❌ Pare o modo follow primeiro usando !unfollow').catch(() => {});
            return;
        }

        CONFIG.random.enabled = true;
        CONFIG.random.interval = interval;

        // Iniciar conexões imediatamente para todas as contas secundárias
        CONFIG.secondaryTokens.forEach(account => {
            setTimeout(() => {
                account.findRandomVoiceChannel();
            }, account.getRandomDelay());
        });

        // Configurar intervalo para rotação
        CONFIG.random.intervalId = setInterval(() => {
            console.log('[Rotação] Iniciando rotação automática de canais...');
            CONFIG.secondaryTokens.forEach(account => {
                if (!account.isConnected) {
                    setTimeout(() => {
                        account.findRandomVoiceChannel();
                    }, account.getRandomDelay());
                }
            });
        }, interval * 60 * 1000);

        message.edit(`✅ Modo aleatório iniciado (rotação a cada ${interval} minutos)`).catch(() => {});
    }

    stopRandomCalls() {
        CONFIG.random.enabled = false;
        if (CONFIG.random.intervalId) {
            clearInterval(CONFIG.random.intervalId);
            CONFIG.random.intervalId = null;
        }

        // Desconectar todas as contas secundárias
        CONFIG.secondaryTokens.forEach(account => {
            account.leaveVoiceChannel();
        });
        
        console.log('[Manager] Modo aleatório parado');
    }
}

// Inicialização do bot
console.log(`
╔══════════════════════════════════════════════════════════════╗
║                   SELFBOT DISCORD - 24/7 VOICE              ║
║                                                              ║
║  ⚠️  AVISO: Selfbots violam os ToS do Discord!             ║
║      Use apenas com contas alternativas!                    ║
║      Risco alto de banimento permanente!                    ║
║                                                              ║
║  CONFIGURAÇÃO:                                               ║
║  • Conta Principal: Apenas comanda, NÃO entra em calls      ║
║  • Contas Secundárias: Entram em calls 24/7                 ║
║  • Status: Apenas secundárias alteram status                ║
║                                                              ║
║  Comandos: !help para ver lista completa                    ║
╚══════════════════════════════════════════════════════════════╝
`);

// Iniciar gerenciador
const manager = new SelfBotManager();

// Manipulação de encerramento gracioso
process.on('SIGINT', () => {
    console.log('\n🛑 Encerrando selfbot...');
    
    // Desconectar todas as contas secundárias
    CONFIG.secondaryTokens.forEach(account => {
        account.logout();
    });
    
    // Desconectar conta principal
    if (manager.mainClient) {
        manager.mainClient.destroy();
    }
    
    console.log('✅ Selfbot encerrado com sucesso.');
    process.exit(0);
});

// Prevenir crashes
process.on('uncaughtException', (error) => {
    console.error('Erro não capturado:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Promise rejeitada:', reason);
});