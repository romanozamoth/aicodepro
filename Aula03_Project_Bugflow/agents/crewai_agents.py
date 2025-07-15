# -*- coding: utf-8 -*-
import os
import logging
import json
import re
import psycopg2
import openai
import litellm
import html
import pinecone
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from openai import OpenAI

# Importacoes para LangChain
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.memory import ConversationBufferMemory
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.manager import CallbackManager
from langchain.schema import HumanMessage, AIMessage
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

# Configuracao de logs
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Carregar variaveis do .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
NEON_DB_URL = os.getenv("NEON_DB_URL")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

# Configuracao explicita do OpenAI
openai.api_key = OPENAI_API_KEY
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Configuracao explicita do LiteLLM
litellm.api_key = OPENAI_API_KEY
litellm.set_verbose = False  # Desativar logs verbosos que podem causar problemas

# Configurar o modelo LLM base para todos os agentes
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1,
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_API_BASE,
    max_tokens=1000,
    timeout=60
)

# Criar os agentes
AG1 = Agent(
    name="Classificador de Componente",
    role="Classificacao de bugs por componente afetado",
    goal="Classificar corretamente os bugs nos componentes adequados do sistema.",
    backstory="""Especialista em triagem de bugs e incidentes para diferentes componentes de software.
    Analiso o conteudo do bug report e classifico baseado nas seguintes regras:
    - Frontend: Problemas de UI, renderizacao, JavaScript, CSS, responsividade
    - Backend: Problemas em APIs, processamento de dados, logica de negocio
    - Database: Problemas com banco de dados, queries, inconsistencias, migracoes
    - DevOps: Problemas de infraestrutura, CI/CD, deploys, configuracao de servidores
    - Security: Vulnerabilidades, exposicao de dados, problemas de autenticacao
    - Integration: Problemas de integracao com servicos externos ou APIs de terceiros""",
    llm=llm
)

AG2 = Agent(
    name="Classificador de Severidade",
    role="Classificacao de bugs por severidade",
    goal="Definir a severidade dos bugs e incidentes.",
    backstory="""Avaliador da severidade de bugs como Critico, Grave ou Menor.
    Analiso o conteudo e classifico baseado nas seguintes regras:
    - Critico: Bugs que causam crash da aplicacao, perda de dados, exposicao de informacoes sensiveis, ou bloqueiam completamente funcionalidades essenciais
    - Grave: Bugs que afetam funcionalidades importantes mas possuem workarounds, causam comportamentos incorretos em features principais, ou degradam significativamente a performance
    - Menor: Problemas cosmeticos, pequenas inconsistencias de UI, bugs em funcionalidades secundarias, ou problemas que afetam poucos usuarios""",
    llm=llm
)

AG3 = Agent(
    name="Analista Técnico de Bugs",
    role="Analise tecnica de bugs e incidentes",
    goal="Fornecer uma analise tecnica detalhada com possiveis causas e solucoes.",
    backstory="""Engenheiro de software especializado em debugging e resolucao de problemas tecnicos.
    Para cada bug, devo:
    1. Identificar a possivel causa raiz do problema
    2. Avaliar o impacto tecnico e areas do codigo potencialmente afetadas
    3. Sugerir abordagens para reproducao e debugging
    4. Propor possiveis solucoes com consideracoes tecnicas
    5. Identificar potenciais efeitos colaterais da correcao""",
    llm=llm
)

AG4 = Agent(
    name="Gerenciador de Resolucao",
    role="Gerenciamento do fluxo de resolucao de bugs",
    goal="Coordenar a resolucao de bugs e atribuir a desenvolvedores apropriados.",
    backstory="""Tech Lead responsavel por garantir que bugs sejam resolvidos eficientemente.
    Minhas responsabilidades incluem:
    1. Verificar se o componente classificado esta correto
    2. Confirmar se a severidade esta adequada ao impacto real
    3. Avaliar a analise tecnica e sugerir abordagens adicionais se necessario
    4. Identificar o desenvolvedor ou equipe mais adequada para resolver o problema
    5. Definir prazos e prioridades no roadmap de desenvolvimento
    6. Coordenar testes e validacao da correcao""",
    llm=llm
)

AG5 = Agent(
    name="Documentador de Bugs",
    role="Documentacao completa de bugs e solucoes",
    goal="Criar documentacao detalhada para cada bug e sua resolucao em multiplos formatos.",
    backstory="""Especialista em documentacao tecnica e gestao de conhecimento.
    Minha documentacao deve incluir:
    1. Descricao clara do bug com passos para reproducao
    2. Componente afetado e justificativa da classificacao
    3. Nivel de severidade e impacto no sistema/usuarios
    4. Analise tecnica da causa raiz
    5. Solucao implementada com detalhes tecnicos
    6. Mudancas no codigo e arquivos afetados
    7. Testes realizados para validar a correcao
    8. Licoes aprendidas e recomendacoes para evitar problemas similares
    
    Devo gerar dois formatos de documentacao:
    
    1. Relatorio detalhado em formato Markdown (.md) para documentacao tecnica
    
    2. Visualizacao interativa em HTML com diagrama Mermaid mostrando:
       - Fluxo de resolucao do bug
       - Componentes afetados
       - Relacao entre causa e efeito
       - Processo de correcao
       - Interacoes entre diferentes sistemas
       
    O documento HTML deve ser visualmente atraente, com estilos CSS apropriados e um diagrama
    interativo usando a biblioteca Mermaid, similar ao formato do arquivo visualizar_diagrama.html.
    Devo garantir que o diagrama seja claro, informativo e ajude a visualizar o problema e sua solucao.""",
    llm=llm
)

# Criar as tasks com expected_output
Task_AG1 = Task(
    description="""Analise o bug e classifique em um dos componentes: Frontend, Backend, Database, DevOps, Security, Integration, UI/UX, Infrastructure.
    Use o formato exato:
    Thought: Analiso o conteudo do bug report...
    Final Answer: [COMPONENTE] - Justificativa da classificacao""",
    expected_output="COMPONENTE (em maiusculo) seguido de justificativa",
    agent=AG1
)

Task_AG2 = Task(
    description="""Defina a severidade do bug como Critico, Grave ou Menor.
    Use o formato exato:
    Thought: Considerando o impacto e urgencia...
    Final Answer: [SEVERIDADE] - Justificativa da classificacao""",
    expected_output="SEVERIDADE (em maiusculo) seguido de justificativa",
    agent=AG2
)

Task_AG3 = Task(
    description="""Faca uma analise tecnica detalhada do bug.
    Use o formato exato:
    Thought: Analisando tecnicamente o problema...
    Final Answer: 
    Causa Raiz: [possivel causa do bug]
    Impacto Tecnico: [areas do codigo afetadas]
    Debugging: [abordagem para reproducao]
    Solucao: [proposta de solucao]
    Efeitos Colaterais: [potenciais efeitos da correcao]""",
    expected_output="Analise tecnica estruturada com os campos acima",
    agent=AG3
)

Task_AG4 = Task(
    description="""Gerencie o fluxo de resolucao do bug verificando as classificacoes e definindo acoes.
    Use o formato exato:
    Thought: Avaliando o encaminhamento...
    Final Answer:
    Status: [status atual do bug]
    Desenvolvedor: [desenvolvedor mais adequado]
    Equipe: [equipe responsavel]
    Prazo: [prazo estimado]
    Prioridade: [prioridade no roadmap]
    Observacoes: [notas importantes]""",
    expected_output="Plano de resolucao estruturado",
    agent=AG4
)

Task_AG5 = Task(
    description="""Gere uma documentacao completa do bug e sua resolucao em dois formatos: Markdown e HTML.
    Use o formato exato:
    Thought: Consolidando informacoes para documentacao...
    Final Answer:
    === DOCUMENTACAO DO BUG ===
    ## Markdown:
    ```markdown
    # Bug #[ID] - [Titulo descritivo]
    
    ## Descricao
    [Descricao detalhada do bug]
    
    ## Componente Afetado
    [Componente] - [Justificativa]
    
    ## Severidade
    [Severidade] - [Justificativa]
    
    ## Analise Tecnica
    - Causa Raiz: [causa]
    - Impacto: [impacto]
    - Solucao: [solucao]
    
    ## Resolucao
    - Desenvolvedor: [nome]
    - Prazo: [data]
    - Status: [status atual]
    
    ## Licoes Aprendidas
    [Licoes e recomendacoes]
    ```
    
    ## HTML (com diagrama Mermaid):
    [Codigo HTML com diagrama Mermaid mostrando o fluxo de resolucao]
    """,
    expected_output="Documentacao completa em Markdown e HTML com diagrama Mermaid",
    agent=AG5
)

def processar_bugs():
    # Definir db_params no início da função para evitar erro de escopo
    db_params = None
    
    try:
        # Verificar se a variável de ambiente está configurada
        if not NEON_DB_URL:
            logger.error("Erro: NEON_DB_URL não está configurado no arquivo .env")
            return
            
        # Obter a URL do banco de dados e configurar db_params no início
        db_url = NEON_DB_URL
        url = urlparse(db_url)
        db_params = {
            'dbname': url.path[1:],
            'user': url.username,
            'password': url.password,
            'host': url.hostname,
            'port': url.port
        }
            
        logger.info(f"Tentando conectar ao banco de dados...")
        # Conectar ao NeonDB
        conn = psycopg2.connect(NEON_DB_URL)
        cur = conn.cursor()
        logger.info("Conexão com o banco de dados estabelecida com sucesso.")
        
        # Verificar se ha bugs abertos
        cur.execute("SELECT COUNT(*) FROM bugs WHERE status = 'Aberto';")
        total_abertos = cur.fetchone()[0]
        
        if total_abertos == 0:
            logger.info("Info: Nenhum bug aberto encontrado")
            return

        logger.info(f"Estatisticas: Total de bugs abertos: {total_abertos}")
        
        # Criar a equipe com configuracoes mais robustas
        crew = Crew(
            agents=[AG1, AG2, AG3, AG4, AG5],
            tasks=[Task_AG1, Task_AG2, Task_AG3, Task_AG4, Task_AG5],
            verbose=True,
            memory=False,  # Desabilitar memória para evitar o erro do ChromaDB
            process=Process.sequential,  # Processo sequencial para evitar conflitos
            max_iter=3,  # Limitar iterações para evitar loops infinitos
            max_execution_time=300  # Timeout de 5 minutos por bug
        )

        # Processar cada bug
        cur.execute("SELECT id, descricao, passos_reproducao, versao_sistema, ambiente FROM bugs WHERE status = 'Aberto';")
        bugs = cur.fetchall()
        
        for bug in bugs:
            bug_id = bug[0]
            bug_data = {
                "descricao": bug[1],
                "passos_reproducao": bug[2] if bug[2] else "",
                "versao": bug[3] if bug[3] else "",
                "ambiente": bug[4] if bug[4] else "",
                "ID": str(bug_id)
            }
            
            logger.info(f"\nINICIANDO BUG {bug_id}")
            logger.info(f"DESCRICAO: {bug_data['descricao']}")
            logger.info(f"PASSOS: {bug_data['passos_reproducao']}")
            logger.info(f"VERSAO: {bug_data['versao']}")
            logger.info(f"AMBIENTE: {bug_data['ambiente']}")
            
            try:
                # Executar com timeout de 3 minutos
                try:
                    logger.info("Iniciando processamento com CrewAI...")
                    resultado = crew.kickoff(
                        inputs=bug_data
                    )
                    logger.info("CrewAI concluiu o processamento com sucesso.")
                except Exception as e:
                    import traceback
                    logger.error(f"Erro no processamento do CrewAI: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
                logger.info(f"Processamento do bug {bug_id} concluido!")
                logger.info(f"Resultado final do bug: {resultado}")
                
                # Iniciar uma nova transação para cada bug
                conn.rollback()  # Garantir que não há transação pendente
                
                # Criar uma nova conexão para cada operação para evitar problemas de transação abortada
                
                # Obter a URL do banco de dados do ambiente
                db_url = os.environ.get('NEON_DB_URL')
                if not db_url:
                    logger.error("NEON_DB_URL não está definida no ambiente")
                    raise ValueError("NEON_DB_URL não está definida no ambiente")
                    
                # Analisar a URL do banco de dados
                url = urlparse(db_url)
                db_params = {
                    'dbname': url.path[1:],
                    'user': url.username,
                    'password': url.password,
                    'host': url.hostname,
                    'port': url.port
                }
                
                # Processar resultados dos agentes
                try:
                    # Resultado do AG1 (Classificador de Componente)
                    componente_match = None
                    for linha in str(resultado).split('\n'):
                        if '[COMPONENTE]' in linha or 'FRONTEND' in linha.upper() or 'BACKEND' in linha.upper() or 'DATABASE' in linha.upper() or 'DEVOPS' in linha.upper() or 'SECURITY' in linha.upper() or 'INTEGRATION' in linha.upper() or 'UI/UX' in linha.upper() or 'INFRASTRUCTURE' in linha.upper():
                            componente_match = linha
                            break
                    
                    if componente_match:
                        # Extrair componente e justificativa
                        componente_parts = componente_match.split('-', 1)
                        componente = componente_parts[0].replace('[COMPONENTE]', '').strip()
                        if not componente:
                            for comp in ['FRONTEND', 'BACKEND', 'DATABASE', 'DEVOPS', 'SECURITY', 'INTEGRATION', 'UI/UX', 'INFRASTRUCTURE']:
                                if comp in componente_match.upper():
                                    componente = comp
                                    break
                        justificativa = componente_parts[1].strip() if len(componente_parts) > 1 else ''
                        
                        # Usar a função de normalização profissional para componente
                        componente_normalizado = normalizar_componente(componente)
                        logger.info(f"Componente normalizado: '{componente_normalizado}'")
                        
                        # Inserir na tabela classificacao_setor
                        try:
                            # Criar uma nova conexão para esta operação
                            with psycopg2.connect(**db_params) as conn_setor, conn_setor.cursor() as cur_setor:
                                cur_setor.execute(
                                    "INSERT INTO classificacao_setor (chamado_id, setor) VALUES (%s, %s)",
                                    (bug_id, componente_normalizado)
                                )
                                conn_setor.commit()
                                logger.info(f"Classificacao de componente salva: {componente_normalizado}")
                        except Exception as e:
                            logger.error(f"Erro ao inserir na tabela classificacao_setor: {str(e)}")
                            # Continuar com as próximas operações
                        # Já logado dentro do bloco try
                    
                    # Resultado do AG2 (Classificador de Severidade)
                    severidade_match = None
                    for linha in str(resultado).split('\n'):
                        if '[SEVERIDADE]' in linha or 'CRITICO' in linha.upper() or 'GRAVE' in linha.upper() or 'MENOR' in linha.upper():
                            severidade_match = linha
                            break
                    
                    if severidade_match:
                        # Extrair severidade e impacto
                        severidade_parts = severidade_match.split('-', 1)
                        severidade = severidade_parts[0].replace('[SEVERIDADE]', '').strip()
                        if not severidade:
                            for sev in ['CRITICO', 'GRAVE', 'MENOR']:
                                if sev in severidade_match.upper():
                                    severidade = sev
                                    break
                        impacto = severidade_parts[1].strip() if len(severidade_parts) > 1 else ''
                        
                        # Usar a função de normalização profissional para prioridade
                        severidade_normalizada = normalizar_prioridade(severidade)
                        logger.info(f"Severidade normalizada: '{severidade_normalizada}'")
                                
                        # Inserir na tabela classificacao_prioridade
                        try:
                                # Usar a função de normalização profissional para garantir valor correto
                            prioridade_final = normalizar_prioridade(severidade_normalizada)
                            logger.info(f"Tentando inserir prioridade: '{prioridade_final}'")
                            
                            # Criar uma nova conexão para esta operação
                            with psycopg2.connect(**db_params) as conn_prioridade, conn_prioridade.cursor() as cur_prioridade:
                                cur_prioridade.execute(
                                    "INSERT INTO classificacao_prioridade (chamado_id, prioridade) VALUES (%s, %s)",
                                    (bug_id, prioridade_final)
                                )
                                conn_prioridade.commit()
                                logger.info(f"Classificacao de severidade salva: {prioridade_final}")
                        except Exception as e:
                            logger.error(f"Erro ao inserir na tabela classificacao_prioridade: {str(e)}")
                            # Tentar novamente com um valor fixo literal
                            try:
                                with psycopg2.connect(**db_params) as conn_retry, conn_retry.cursor() as cur_retry:
                                    # Usar o valor literal diretamente para evitar problemas
                                    cur_retry.execute(
                                        "INSERT INTO classificacao_prioridade (chamado_id, prioridade) VALUES (%s, 'Normal')",
                                        (bug_id,)
                                    )
                                    conn_retry.commit()
                                    logger.info("Classificacao de severidade salva com valor padrão 'Normal'")
                            except Exception as retry_error:
                                logger.error(f"Erro ao inserir na tabela classificacao_prioridade (retry): {str(retry_error)}")
                            # Continuar com as próximas operações
                        # Já logado dentro do bloco try
                    
                    # Resultado do AG3 (Analista Técnico)
                    causa_raiz = ''
                    impacto_tecnico = ''
                    abordagem_debugging = ''
                    solucoes_propostas = ''
                    potenciais_efeitos = ''
                    
                    linhas = str(resultado).split('\n')
                    for i, linha in enumerate(linhas):
                        if 'Causa Raiz:' in linha and i+1 < len(linhas):
                            causa_raiz = linhas[i].replace('Causa Raiz:', '').strip()
                        elif 'Impacto Tecnico:' in linha and i+1 < len(linhas):
                            impacto_tecnico = linhas[i].replace('Impacto Tecnico:', '').strip()
                        elif 'Debugging:' in linha and i+1 < len(linhas):
                            abordagem_debugging = linhas[i].replace('Debugging:', '').strip()
                        elif 'Solucao:' in linha and i+1 < len(linhas):
                            solucoes_propostas = linhas[i].replace('Solucao:', '').strip()
                        elif 'Efeitos Colaterais:' in linha and i+1 < len(linhas):
                            potenciais_efeitos = linhas[i].replace('Efeitos Colaterais:', '').strip()
                    
                    # Armazenar informações da análise técnica no relatório final
                    analise_tecnica_texto = f"""Análise Técnica:
- Causa Raiz: {causa_raiz or 'Não especificado'}
- Impacto Técnico: {impacto_tecnico}
- Abordagem de Debugging: {abordagem_debugging}
- Soluções Propostas: {solucoes_propostas}
- Potenciais Efeitos Colaterais: {potenciais_efeitos}
"""
                    
                    # Não inserimos na tabela analise_tecnica pois ela não existe
                    # Vamos incluir essas informações no relatório final
                    logger.info("Informações da análise técnica armazenadas para o relatório final")
                    
                    # Resultado do AG4 (Gerenciador de Resolução)
                    desenvolvedor = ''
                    equipe = ''
                    prazo = None
                    prioridade = 0
                    status = 'Atribuido'
                    
                    for linha in str(resultado).split('\n'):
                        if 'Desenvolvedor:' in linha:
                            desenvolvedor = linha.replace('Desenvolvedor:', '').strip()
                        elif 'Equipe:' in linha:
                            equipe = linha.replace('Equipe:', '').strip()
                        elif 'Prazo:' in linha:
                            prazo_str = linha.replace('Prazo:', '').strip()
                            # Tentar converter para data se possível
                            try:
                                from datetime import datetime, timedelta
                                if 'dia' in prazo_str.lower():
                                    dias = int(''.join(filter(str.isdigit, prazo_str)) or 7)
                                    prazo = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
                                else:
                                    prazo = datetime.now().strftime('%Y-%m-%d')
                            except:
                                prazo = None
                        elif 'Prioridade:' in linha:
                            prioridade_str = linha.replace('Prioridade:', '').strip()
                            try:
                                prioridade = int(''.join(filter(str.isdigit, prioridade_str)) or 3)
                            except:
                                prioridade = 3
                    
                    # Inserir na tabela andamento_chamados
                    if desenvolvedor:
                        # Usar a função de normalização profissional para status
                        status_normalizado = normalizar_status(status)
                        logger.info(f"Status normalizado: '{status_normalizado}'")
                        
                        # Limpar e limitar o tamanho do campo responsavel para evitar erros
                        responsavel_limpo = limpar_texto(desenvolvedor)
                        # Remover quaisquer marcadores de lista ou caracteres especiais no início
                        responsavel_limpo = re.sub(r'^[-\*\•\·\⁃\‣\⁌\⁍\⦾\⦿\⁃] *', '', responsavel_limpo)
                        # Remover quaisquer caracteres não alfanuméricos no início
                        responsavel_limpo = re.sub(r'^[^a-zA-Z0-9]+', '', responsavel_limpo)
                        responsavel_limitado = responsavel_limpo[:200] if responsavel_limpo else "Não atribuído"
                        
                        try:
                            # Usar valores literais diretamente na consulta SQL para evitar problemas de formatação
                            # Criar uma nova conexão para esta operação
                            with psycopg2.connect(**db_params) as conn_status, conn_status.cursor() as cur_status:
                                # Usar uma consulta SQL parametrizada, mas com o status como literal
                                # Usar sempre o valor normalizado que já está correto
                                cur_status.execute(
                                    "INSERT INTO andamento_chamados (chamado_id, responsavel, status) VALUES (%s, %s, %s)",
                                    (bug_id, responsavel_limitado, status_normalizado)
                                )
                                conn_status.commit()
                                logger.info(f"Gerenciamento de resolucao salvo: {responsavel_limitado}, status: {status_normalizado}")
                        except Exception as e:
                            logger.error(f"Erro ao inserir na tabela andamento_chamados: {str(e)}")
                            # Tentar novamente com um valor fixo literal
                            try:
                                with psycopg2.connect(**db_params) as conn_retry, conn_retry.cursor() as cur_retry:
                                    # Usar o valor literal diretamente na consulta SQL
                                    cur_retry.execute(
                                        "INSERT INTO andamento_chamados (chamado_id, responsavel, status) VALUES (%s, %s, 'Atribuido')",
                                        (bug_id, "Desenvolvedor Padrão")
                                    )
                                    conn_retry.commit()
                                    logger.info("Gerenciamento de resolucao salvo com valores padrão")
                            except Exception as retry_error:
                                logger.error(f"Erro ao inserir na tabela andamento_chamados (retry): {str(retry_error)}")
                            # Continuar com as próximas operações
                        # Já logado dentro do bloco try
                    
                    # Resultado do AG5 (Documentador)
                    # Extrair documentação Markdown e HTML
                    markdown_doc = ''
                    html_doc = ''
                    
                    markdown_start = str(resultado).find('```markdown')
                    markdown_end = str(resultado).find('```', markdown_start + 10) if markdown_start > -1 else -1
                    
                    if markdown_start > -1 and markdown_end > -1:
                        markdown_doc = str(resultado)[markdown_start + 10:markdown_end].strip()
                    
                    html_start = str(resultado).find('## HTML')
                    if html_start > -1:
                        html_doc = str(resultado)[html_start:].strip()
                    
                    # Salvar o relatório Markdown diretamente na raiz do projeto
                    if markdown_doc:
                        # Salvar o relatório Markdown na raiz
                        relatorio_file = f'bug_{bug_id}_relatorio.md'
                        with open(relatorio_file, 'w', encoding='utf-8') as f:
                            f.write(markdown_doc)
                        logger.info(f"Relatório Markdown salvo em: {relatorio_file}")
                        
                        # Atualizar Pinecone com o relatório processado
                        logger.info(f"🔄 Atualizando Pinecone para bug {bug_id}...")
                        if atualizar_pinecone_bug(bug_id, markdown_doc):
                            logger.info(f"✅ Pinecone atualizado com sucesso para bug {bug_id}")
                        else:
                            logger.warning(f"⚠️  Falha ao atualizar Pinecone para bug {bug_id}")
                        
                        # Salvar o HTML se existir
                        if html_doc:
                            html_file = f'bug_{bug_id}_relatorio.html'
                            # Extrair apenas o conteúdo HTML
                            html_content_start = html_doc.find('```html')
                            html_content_end = html_doc.find('```', html_content_start + 7) if html_content_start > -1 else -1
                            
                            if html_content_start > -1 and html_content_end > -1:
                                html_content = html_doc[html_content_start + 7:html_content_end].strip()
                                with open(html_file, 'w', encoding='utf-8') as f:
                                    f.write(html_content)
                                logger.info(f"Relatório HTML salvo em: {html_file}")
                    
                    # Inserir na tabela relatorio_final
                    if markdown_doc or html_doc:
                        # Combinar markdown_doc com analise_tecnica_texto
                        relatorio_completo = markdown_doc
                        if 'analise_tecnica_texto' in locals() and analise_tecnica_texto:
                            relatorio_completo += "\n\n" + analise_tecnica_texto
                            
                        # Limpar e limitar o tamanho do relatório para evitar erros
                        # Muitos bancos de dados têm um limite para campos TEXT
                        relatorio_limpo = relatorio_completo  # Não aplicamos limpar_texto() aqui para preservar a formatação Markdown/HTML
                        relatorio_limitado = relatorio_limpo[:65000] if relatorio_limpo else "Sem documentação"
                        
                        try:
                            # Criar uma nova conexão para esta operação
                            with psycopg2.connect(**db_params) as conn_relatorio, conn_relatorio.cursor() as cur_relatorio:
                                cur_relatorio.execute(
                                    "INSERT INTO relatorio_final (chamado_id, conclusao, resolvido) VALUES (%s, %s, %s)",
                                    (bug_id, relatorio_limitado, True)
                                )
                                conn_relatorio.commit()
                                logger.info("Documentacao do bug salva")
                        except Exception as e:
                            logger.error(f"Erro ao inserir na tabela relatorio_final: {str(e)}")
                            # Continuar com as próximas operações
                        # Já logado dentro do bloco try
                        
                        # 🔄 ATUALIZAR PINECONE COM O RELATÓRIO PROCESSADO
                        logger.info(f"Atualizando Pinecone para bug {bug_id}...")
                        try:
                            sucesso_pinecone = atualizar_pinecone_bug(bug_id, relatorio_limitado)
                            if sucesso_pinecone:
                                logger.info(f"✅ Pinecone atualizado com sucesso para bug {bug_id}")
                            else:
                                logger.warning(f"⚠️ Falha na atualização do Pinecone para bug {bug_id}")
                        except Exception as pinecone_error:
                            logger.error(f"❌ Erro ao atualizar Pinecone para bug {bug_id}: {str(pinecone_error)}")
                            # Não interromper o fluxo por erro no Pinecone
                
                except Exception as e:
                    logger.error(f"Erro ao salvar resultados no banco: {str(e)}")
                
                # Atualizar status do bug para 'Processado'
                try:
                    with psycopg2.connect(**db_params) as conn_update, conn_update.cursor() as cur_update:
                        cur_update.execute(
                            "UPDATE bugs SET status = 'Processado' WHERE id = %s",
                            (bug_id,)
                        )
                        conn_update.commit()
                        logger.info(f"Bug {bug_id} marcado como 'Processado'")
                except Exception as e:
                    logger.error(f"Erro ao atualizar status do bug: {str(e)}")
                
                # Commit da transação se tudo correu bem
                try:
                    conn.commit()
                    logger.info(f"Transação concluída com sucesso para o bug {bug_id}")
                except Exception as e:
                    logger.error(f"Erro ao fazer commit da transação: {str(e)}")
                    conn.rollback()
            except Exception as e:
                logger.error(f"Erro no processamento do bug {bug_id}: {str(e)}")
                logger.error("Marcando bug como 'Erro' para revisao manual")
                
                # Rollback da transação em caso de erro
                conn.rollback()
                
                # Marcar o bug como 'Erro' para revisao manual em uma nova transação
                try:
                    # Usar uma nova conexão para esta operação
                    with psycopg2.connect(**db_params) as conn_erro, conn_erro.cursor() as cur_erro:
                        cur_erro.execute(
                            "UPDATE bugs SET status = 'Erro' WHERE id = %s",
                            (bug_id,)
                        )
                        conn_erro.commit()
                        logger.info(f"Bug {bug_id} marcado como 'Erro' para revisao manual")
                except Exception as update_error:
                    logger.error(f"Erro ao marcar bug como 'Erro': {str(update_error)}")

    except Exception as e:
        import traceback
        logger.error(f"Erro na conexao com o banco de dados: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("Verifique as configuracoes de conexao no arquivo .env")
    
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        logger.info("Processamento finalizado")

def limpar_texto(texto):
    """Remove tags HTML, espaços extras e caracteres especiais de um texto."""
    if not texto:
        return ""
    
    # Remover tags HTML
    texto_sem_html = re.sub(r'<[^>]+>', '', texto)
    
    # Remover espaços extras
    texto_limpo = re.sub(r'\s+', ' ', texto_sem_html).strip()
    
    # Decodificar entidades HTML
    texto_final = html.unescape(texto_limpo)
    
    # Remover caracteres especiais e marcadores de lista
    texto_final = re.sub(r'^[-\*\•\·\⁃\‣\⁌\⁍\⦾\⦿\⁃] *', '', texto_final)
    
    return texto_final

def normalizar_prioridade(prioridade):
    """Normaliza o valor de prioridade para um dos valores permitidos na tabela."""
    # Valores permitidos conforme constraint REAL: Urgente, Intermediário, Normal
    valores_permitidos = ['Urgente', 'Intermediário', 'Normal']
    
    # Limpar o texto primeiro
    prioridade_limpa = limpar_texto(prioridade).strip()
    
    # Verificar correspondência exata
    if prioridade_limpa in valores_permitidos:
        return prioridade_limpa
    
    # Normalizar baseado em substrings
    prioridade_lower = prioridade_limpa.lower()
    if 'crític' in prioridade_lower or 'urgent' in prioridade_lower or 'grave' in prioridade_lower or 'alto' in prioridade_lower:
        return 'Urgente'
    elif 'médio' in prioridade_lower or 'medio' in prioridade_lower or 'intermedi' in prioridade_lower:
        return 'Intermediário'
    elif 'menor' in prioridade_lower or 'baixo' in prioridade_lower or 'normal' in prioridade_lower or 'low' in prioridade_lower:
        return 'Normal'
    else:
        return 'Normal'

def normalizar_status(status):
    """Normaliza o valor de status para um dos valores permitidos na tabela."""
    # Valores permitidos conforme constraint REAL: Em andamento, Aguardando resposta, Concluído
    valores_permitidos = ['Em andamento', 'Aguardando resposta', 'Concluído']
    
    # Limpar o texto primeiro
    status_limpo = limpar_texto(status).strip()
    
    # Verificar correspondência exata
    if status_limpo in valores_permitidos:
        return status_limpo
    
    # Normalizar baseado em substrings
    status_lower = status_limpo.lower()
    if 'atri' in status_lower or 'aberto' in status_lower or 'desen' in status_lower or 'progr' in status_lower or 'andament' in status_lower:
        return 'Em andamento'
    elif 'aguard' in status_lower or 'review' in status_lower or 'revis' in status_lower or 'resposta' in status_lower:
        return 'Aguardando resposta'
    elif 'conclu' in status_lower or 'resolv' in status_lower or 'finaliz' in status_lower or 'fecha' in status_lower:
        return 'Concluído'
    else:
        return 'Em andamento'

def normalizar_componente(componente):
    """Normaliza o valor de componente/setor para um dos valores permitidos na tabela."""
    # Valores permitidos exatos conforme a restrição CHECK na tabela
    valores_permitidos = ['Frontend', 'Backend', 'Database', 'DevOps', 'Security', 'Integration', 'UI/UX', 'Infrastructure']
    
    # Limpar o texto primeiro
    componente_limpo = limpar_texto(componente).strip()
    
    # Verificar correspondência exata
    if componente_limpo in valores_permitidos:
        return componente_limpo
    
    # Normalizar baseado em substrings
    componente_lower = componente_limpo.lower()
    for valor in valores_permitidos:
        if valor.lower() in componente_lower:
            return valor
    
    # Se não encontrar correspondência, usar um valor padrão seguro
    return 'Backend'

def atualizar_pinecone_bug(bug_id, relatorio_markdown):
    """Atualiza o Pinecone com o relatório processado de um bug específico"""
    try:
        # Inicializar conexões
        pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index("bugflow")
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Criar embedding do relatório completo (mesmo modelo do RAG)
        response = client.embeddings.create(
            input=relatorio_markdown,
            model="text-embedding-3-small",
            dimensions=1536  # Mesma dimensão do índice
        )
        embedding = response.data[0].embedding
        
        # Extrair metadados do relatório
        metadados = extrair_metadados_relatorio(relatorio_markdown)
        
        # Buscar informações adicionais do banco para enriquecer metadados
        try:
            conn = psycopg2.connect(NEON_DB_URL)
            cur = conn.cursor()
            
            # Buscar dados do bug
            cur.execute("""
                SELECT b.descricao, b.equipe, b.ambiente, b.versao_sistema,
                       cs.setor, cp.prioridade, ac.responsavel
                FROM bugs b
                LEFT JOIN classificacao_setor cs ON b.id = cs.chamado_id
                LEFT JOIN classificacao_prioridade cp ON b.id = cp.chamado_id
                LEFT JOIN andamento_chamados ac ON b.id = ac.chamado_id
                WHERE b.id = %s
            """, (bug_id,))
            
            bug_info = cur.fetchone()
            if bug_info:
                metadados.update({
                    'descricao_original': bug_info[0][:200] if bug_info[0] else '',
                    'equipe': bug_info[1] or '',
                    'ambiente': bug_info[2] or '',
                    'versao_sistema': bug_info[3] or '',
                    'componente': bug_info[4] or '',
                    'severidade': bug_info[5] or '',
                    'desenvolvedor': bug_info[6] or ''
                })
            
            cur.close()
            conn.close()
            
        except Exception as db_error:
            logger.warning(f"Erro ao buscar metadados do banco para bug {bug_id}: {str(db_error)}")
        
        # Metadados finais
        metadados.update({
            'bug_id': str(bug_id),
            'tipo': 'relatorio_processado',
            'conteudo_completo': relatorio_markdown[:1000],  # Primeiros 1000 chars
            'processado_em': datetime.now().isoformat(),
            'status': 'processado'
        })
        
        # Atualizar vetor no Pinecone
        vector_id = f"bug_{bug_id}_processado"
        index.upsert(vectors=[(vector_id, embedding, metadados)])
        logger.info(f"✅ Bug {bug_id} atualizado no Pinecone com sucesso (ID: {vector_id})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar Pinecone para bug {bug_id}: {str(e)}")
        return False

def extrair_metadados_relatorio(conteudo_relatorio):
    """Extrai metadados estruturados do relatório"""
    metadados = {}
    
    linhas = conteudo_relatorio.split('\n')
    
    for i, linha in enumerate(linhas):
        # Extrair componente afetado
        if "## Componente Afetado" in linha and i+1 < len(linhas):
            componente_linha = linhas[i+1].strip()
            if ' - ' in componente_linha:
                metadados['componente'] = componente_linha.split(' - ')[0].strip()
        
        # Extrair severidade
        elif "## Severidade" in linha and i+1 < len(linhas):
            severidade_linha = linhas[i+1].strip()
            if ' - ' in severidade_linha:
                metadados['severidade'] = severidade_linha.split(' - ')[0].strip()
        
        # Extrair desenvolvedor
        elif "- Desenvolvedor:" in linha:
            metadados['desenvolvedor'] = linha.replace('- Desenvolvedor:', '').strip()
        
        # Extrair status
        elif "- Status:" in linha:
            metadados['status_resolucao'] = linha.replace('- Status:', '').strip()
    
    return metadados

def verificar_tabelas():
    """Verifica se as tabelas necessárias existem no banco de dados."""
    try:
        conn = psycopg2.connect(NEON_DB_URL)
        cur = conn.cursor()
        
        # Verificar quais tabelas existem
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('bugs', 'relatorio_final', 'andamento_chamados', 'classificacao_prioridade', 'classificacao_setor')
        """)
        tabelas_existentes = [row[0] for row in cur.fetchall()]
        logger.info(f"Tabelas encontradas no banco de dados: {tabelas_existentes}")
        
        # Verificar se todas as tabelas necessárias existem
        tabelas_necessarias = ['bugs', 'relatorio_final', 'andamento_chamados', 'classificacao_prioridade', 'classificacao_setor']
        tabelas_faltando = [t for t in tabelas_necessarias if t not in tabelas_existentes]
        
        if tabelas_faltando:
            logger.error(f"As seguintes tabelas estão faltando no banco de dados: {tabelas_faltando}")
            logger.error("Execute o arquivo SQL neon_chamados.sql no editor SQL do Neon para criar as tabelas necessárias.")
            return False
        
        return True
        
    except Exception as e:
        import traceback
        logger.error(f"Erro ao verificar tabelas: {str(e)}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Verificar se as tabelas necessárias existem
    if verificar_tabelas():
        processar_bugs()
    else:
        logger.error("Não foi possível continuar devido a problemas com as tabelas do banco de dados.")
