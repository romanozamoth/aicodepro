#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuração centralizada e robusta do Pinecone
Resolve problemas de compatibilidade entre versões
"""

import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def get_pinecone_client():
    """
    Retorna cliente Pinecone configurado corretamente
    Para Pinecone v7.3.0
    """
    try:
        from pinecone import Pinecone
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY não encontrada no .env")
        
        # Inicializar cliente Pinecone v7.x
        pc = Pinecone(api_key=api_key)
        return pc
        
    except Exception as e:
        raise Exception(f"Erro ao inicializar Pinecone: {str(e)}")

def get_pinecone_index(index_name="bugflow"):
    """
    Retorna índice Pinecone configurado
    """
    try:
        pc = get_pinecone_client()
        index = pc.Index(index_name)
        return index
        
    except Exception as e:
        raise Exception(f"Erro ao conectar ao índice {index_name}: {str(e)}")

def test_pinecone_connection():
    """
    Testa conexão com Pinecone
    """
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        print(f"✅ Pinecone conectado com sucesso!")
        print(f"   - Total de vetores: {stats.total_vector_count}")
        print(f"   - Dimensões: {stats.dimension}")
        return True
    except Exception as e:
        print(f"❌ Erro na conexão Pinecone: {str(e)}")
        return False

if __name__ == "__main__":
    test_pinecone_connection()
