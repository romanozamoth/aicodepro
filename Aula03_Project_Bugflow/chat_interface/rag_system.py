#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sistema RAG para consulta de bugs usando Pinecone
Permite busca semântica e geração de respostas contextualizadas
"""

import os
import logging
import sys
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# Adicionar diretório pai ao path para importar pinecone_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pinecone_config import get_pinecone_index
    PINECONE_AVAILABLE = True
except ImportError as e:
    print(f"Erro ao importar pinecone_config: {e}")
    PINECONE_AVAILABLE = False
    get_pinecone_index = None

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BugRAGSystem:
    def __init__(self):
        """Inicializa o sistema RAG"""
        load_dotenv()
        
        # Configurações
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.index_name = "bugflow"
        
        # Inicializar clientes
        self.index = None
        self.openai_client = None
        
        # Memória conversacional
        self.conversation_history = []
        self.max_history_length = 10  # Manter últimas 10 interações
        
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Inicializa os clientes Pinecone e OpenAI"""
        if not PINECONE_AVAILABLE:
            raise Exception("Pinecone não está disponível")
            
        try:
            # Inicializar Pinecone usando função centralizada
            self.index = get_pinecone_index()
            
            # OpenAI
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            
            logger.info("✅ Clientes inicializados com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar clientes: {str(e)}")
            raise
    
    def create_query_embedding(self, query: str) -> List[float]:
        """Cria embedding da query do usuário usando o mesmo modelo do índice"""
        try:
            response = self.openai_client.embeddings.create(
                input=query,
                model="text-embedding-3-small",  # Mesmo modelo do índice Pinecone
                dimensions=1536  # Mesma dimensão do índice
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"❌ Erro ao criar embedding: {str(e)}")
            return []
    
    def _enrich_query_with_context(self, query: str) -> str:
        """Enriquece a query com contexto conversacional"""
        if not self.conversation_history:
            return query
            
        # Pegar últimas interações relevantes
        recent_context = self.conversation_history[-3:]  # Últimas 3 interações
        context_text = " ".join(recent_context)
        
        # Enriquecer query com contexto
        enriched = f"{query} {context_text}"
        logger.info(f"Query enriquecida: {enriched[:100]}...")
        return enriched
    
    def _update_conversation_history(self, query: str, response: str, bugs_found: List[Dict]):
        """Atualiza o histórico conversacional"""
        # Extrair informações relevantes dos bugs encontrados
        bug_context = ""
        if bugs_found:
            bug_ids = [bug['id'] for bug in bugs_found[:3]]  # Top 3 bugs
            bug_context = f" (bugs relevantes: {', '.join(bug_ids)})"
        
        # Adicionar ao histórico
        interaction = f"Q: {query} A: {response[:100]}...{bug_context}"
        self.conversation_history.append(interaction)
        
        # Manter apenas as últimas interações
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
        
        logger.info(f"Histórico atualizado. Total de interações: {len(self.conversation_history)}")
    
    def clear_conversation_history(self):
        """Limpa o histórico conversacional"""
        self.conversation_history = []
        logger.info("Histórico conversacional limpo")
    
    def get_conversation_summary(self) -> str:
        """Retorna resumo do histórico conversacional"""
        if not self.conversation_history:
            return "Nenhuma conversa anterior"
        
        return f"Histórico: {len(self.conversation_history)} interações. Últimas: {self.conversation_history[-2:]}"
    
    def search_similar_bugs(self, query: str, top_k: int = 5, filters: Optional[Dict] = None) -> List[Dict]:
        """Busca bugs similares usando embedding semântico com contexto conversacional"""
        try:
            # Enriquecer query com contexto conversacional
            enriched_query = self._enrich_query_with_context(query)
            
            # Criar embedding da query enriquecida
            query_embedding = self.create_query_embedding(enriched_query)
            if not query_embedding:
                return []
            
            # Preparar filtros
            filter_dict = {}
            if filters:
                if filters.get('componente'):
                    filter_dict['componente'] = filters['componente']
                if filters.get('severidade'):
                    filter_dict['severidade'] = filters['severidade']
                if filters.get('desenvolvedor'):
                    filter_dict['desenvolvedor'] = filters['desenvolvedor']
            
            # Buscar no Pinecone
            search_params = {
                'vector': query_embedding,
                'top_k': top_k,
                'include_metadata': True
            }
            
            if filter_dict:
                search_params['filter'] = filter_dict
            
            results = self.index.query(**search_params)
            
            # Processar resultados
            bugs_encontrados = []
            for match in results.matches:
                bug_info = {
                    'id': match.id,
                    'score': match.score,
                    'metadata': match.metadata or {}
                }
                bugs_encontrados.append(bug_info)
            
            logger.info(f"✅ Encontrados {len(bugs_encontrados)} bugs similares")
            return bugs_encontrados
            
        except Exception as e:
            logger.error(f"❌ Erro na busca: {str(e)}")
            return []
    
    def build_context(self, bugs: List[Dict], max_tokens: int = 3000) -> str:
        """Constrói contexto para o LLM baseado nos bugs encontrados"""
        if not bugs:
            return "Nenhum bug relevante encontrado na base de dados."
        
        context_parts = ["=== BUGS RELEVANTES ENCONTRADOS ===\n"]
        current_tokens = 0
        
        for i, bug in enumerate(bugs, 1):
            metadata = bug.get('metadata', {})
            score = bug.get('score', 0)
            
            bug_context = f"""
Bug #{bug['id']} (Relevância: {score:.2f})
- Componente: {metadata.get('componente', 'N/A')}
- Severidade: {metadata.get('severidade', 'N/A')}
- Desenvolvedor: {metadata.get('desenvolvedor', 'N/A')}
- Status: {metadata.get('status_resolucao', 'N/A')}
- Conteúdo: {metadata.get('conteudo_completo', 'N/A')[:500]}...

"""
            
            # Estimativa simples de tokens (4 chars ≈ 1 token)
            estimated_tokens = len(bug_context) // 4
            
            if current_tokens + estimated_tokens > max_tokens:
                break
                
            context_parts.append(bug_context)
            current_tokens += estimated_tokens
        
        return "\n".join(context_parts)
    
    def generate_response(self, query: str, context: str) -> str:
        """Gera resposta usando OpenAI com o contexto dos bugs"""
        try:
            system_prompt = """Você é um assistente especializado em análise de bugs e desenvolvimento de software. 
            
Sua função é ajudar desenvolvedores e gestores a entender e resolver problemas baseado no histórico de bugs da empresa.

INSTRUÇÕES:
1. Use APENAS as informações fornecidas no contexto dos bugs
2. Seja preciso e técnico nas suas respostas
3. Cite sempre os IDs dos bugs relevantes (ex: "Bug #123")
4. Se não houver informação suficiente, diga claramente
5. Forneça insights práticos e acionáveis
6. Mantenha um tom profissional mas acessível
7. IMPORTANTE: Quando o usuário usar referências como "esse bug", "o case", "esse problema", conecte com os bugs mencionados anteriormente
8. Se a pergunta for sobre "quem", "qual dev", "responsável", foque nas informações de desenvolvedor dos bugs

REFERÊNCIAS CONTEXTUAIS:
- "esse bug" = bug mencionado anteriormente
- "o case" = caso/bug em discussão
- "quem está com" = desenvolvedor responsável
- "esse problema" = problema técnico em questão

FORMATO DE RESPOSTA:
- Resposta direta à pergunta
- Bugs relevantes citados
- Insights ou recomendações (se aplicável)"""

            user_prompt = f"""
PERGUNTA DO USUÁRIO: {query}

CONTEXTO DOS BUGS:
{context}

Por favor, responda à pergunta baseado exclusivamente nas informações dos bugs fornecidos acima.
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar resposta: {str(e)}")
            return f"Desculpe, ocorreu um erro ao processar sua pergunta: {str(e)}"
    
    def chat(self, query: str, filters: Optional[Dict] = None, top_k: int = 5) -> Dict[str, Any]:
        """Função principal do chat RAG com memória conversacional"""
        try:
            # 1. Buscar bugs similares (já usa contexto conversacional)
            bugs_similares = self.search_similar_bugs(query, top_k, filters)
            
            # 2. Construir contexto
            context = self.build_context(bugs_similares)
            
            # 3. Gerar resposta
            response = self.generate_response(query, context)
            
            # 4. Atualizar histórico conversacional
            self._update_conversation_history(query, response, bugs_similares)
            
            return {
                'response': response,
                'bugs_encontrados': bugs_similares,
                'context_used': context,
                'conversation_history_size': len(self.conversation_history),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no chat: {str(e)}")
            return {
                'response': f"Desculpe, ocorreu um erro: {str(e)}",
                'bugs_encontrados': [],
                'context_used': "",
                'success': False
            }
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do índice Pinecone"""
        try:
            stats = self.index.describe_index_stats()
            return {
                'total_vectors': stats.total_vector_count,
                'dimension': stats.dimension,
                'index_fullness': stats.index_fullness
            }
        except Exception as e:
            logger.error(f"❌ Erro ao obter estatísticas: {str(e)}")
            return {}

# Função para criar instância do sistema RAG
def get_rag_system():
    """Cria e retorna instância do sistema RAG"""
    return BugRAGSystem()
