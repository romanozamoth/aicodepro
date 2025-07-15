#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interface Flask para o sistema RAG de bugs
"""

from flask import Flask, render_template, request, jsonify
import os
from rag_system import BugRAGSystem

app = Flask(__name__)

# Inicializar sistema RAG
try:
    rag_system = BugRAGSystem()
    print("✅ Sistema RAG inicializado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao inicializar sistema RAG: {str(e)}")
    rag_system = None

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint para chat"""
    if not rag_system:
        return jsonify({
            'success': False,
            'response': 'Sistema RAG não está disponível',
            'bugs_encontrados': []
        })
    
    data = request.json
    query = data.get('query', '')
    filters = data.get('filters', {})
    top_k = data.get('top_k', 5)
    
    if not query:
        return jsonify({
            'success': False,
            'response': 'Por favor, digite uma pergunta',
            'bugs_encontrados': []
        })
    
    # Processar query
    result = rag_system.chat(query, filters, top_k)
    
    return jsonify(result)

@app.route('/clear-history', methods=['POST'])
def clear_history():
    """Endpoint para limpar histórico conversacional"""
    if not rag_system:
        return jsonify({
            'success': False,
            'message': 'Sistema RAG não está disponível'
        })
    
    rag_system.clear_conversation_history()
    return jsonify({
        'success': True,
        'message': 'Histórico conversacional limpo com sucesso'
    })

@app.route('/stats')
def stats():
    """Endpoint para estatísticas"""
    if not rag_system:
        return jsonify({'error': 'Sistema RAG não disponível'})
    
    stats = rag_system.get_index_stats()
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
