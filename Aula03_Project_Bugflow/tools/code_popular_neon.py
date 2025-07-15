# -*- coding: utf-8 -*-
import psycopg2
import os
from dotenv import load_dotenv

# Caminho absoluto para o .env na raiz do projeto
from pathlib import Path
dotenv_path = Path(__file__).resolve().parents[1] / ".env"

# Carregar variaveis do arquivo .env
load_dotenv(dotenv_path=dotenv_path)
DB_URL = os.getenv("NEON_DB_URL")

def popular_banco():
    try:
        # Conecta ao banco
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Drop nas tabelas se existirem
        cur.execute("DROP TABLE IF EXISTS documentacao_bug CASCADE;")
        cur.execute("DROP TABLE IF EXISTS gerenciamento_resolucao CASCADE;")
        cur.execute("DROP TABLE IF EXISTS analise_tecnica CASCADE;")
        cur.execute("DROP TABLE IF EXISTS classificacao_severidade CASCADE;")
        cur.execute("DROP TABLE IF EXISTS classificacao_componente CASCADE;")
        cur.execute("DROP TABLE IF EXISTS bugs CASCADE;")
        print("Tabelas antigas removidas.")
        
        # Cria a tabela de bugs
        cur.execute("""
            CREATE TABLE bugs (
                id SERIAL PRIMARY KEY,
                descricao TEXT NOT NULL,
                equipe VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'Aberto',
                data_abertura TIMESTAMP DEFAULT NOW(),
                passos_reproducao TEXT,
                versao_sistema VARCHAR(100),
                ambiente VARCHAR(50) DEFAULT 'Producao'
            );
        """)
        print("Nova tabela de bugs criada.")
        
        # Insere os bugs um por um
        bugs = [
            ("Erro 500 na API de autenticacao apos atualizacao", "Frontend Team", "Ao fazer login, a API retorna erro 500. Ocorre apenas apos o ultimo deploy.", "v2.3.4", "Producao"),
            ("Memory leak detectado em producao no servico de processamento de imagens", "DevOps Team", "Servico consome cada vez mais memoria ao processar imagens em lote, nao liberando recursos.", "v1.8.2", "Producao"),
            ("Inconsistencia no banco de dados apos migracao", "Database Team", "Alguns registros de usuarios apresentam dados corrompidos apos a migracao da ultima sexta-feira.", "v3.0.1", "Producao"),
            ("Falha de seguranca: possivel injecao SQL na pagina de login", "Security Team", "Identificada vulnerabilidade onde input nao sanitizado pode permitir injecao SQL.", "v2.1.0", "Producao"),
            ("Tempo de resposta da API aumentou 300% apos deploy", "Backend Team", "Endpoints de listagem de produtos estao demorando em media 3s quando antes era 0.8s.", "v4.2.1", "Producao"),
            ("Erro de renderizacao em navegadores Safari na pagina de checkout", "Frontend Team", "Botao de finalizar compra nao aparece em Safari no iOS e macOS.", "v2.8.5", "Producao"),
            ("Conflito de dependencias apos atualizacao do Node.js", "DevOps Team", "Build falha com erro de conflito entre pacotes apos atualizacao para Node.js 18.", "v3.1.0", "Desenvolvimento"),
            ("Dados de usuario nao estao sendo mascarados no log", "Security Team", "Informacoes sensiveis como emails e telefones aparecem em texto plano nos logs.", "v2.4.3", "Producao"),
            ("Deadlock identificado no processamento assincrono de pagamentos", "Backend Team", "Sistema trava quando dois pagamentos sao processados simultaneamente para o mesmo usuario.", "v3.5.2", "Homologacao"),
            ("Testes de integracao falhando apos merge da feature de notificacoes", "QA Team", "70% dos testes de integracao falham apos o merge da nova feature.", "v4.0.0-rc1", "Testes"),
            ("Problemas de responsividade no dashboard em dispositivos moveis", "UI/UX Team", "Dashboard quebra layout em telas menores que 375px de largura.", "v2.9.1", "Producao"),
            ("Credenciais expostas no repositorio Git", "Security Team", "Chaves de API da AWS foram commitadas no repositorio publico.", "v3.2.0", "Desenvolvimento"),
            ("Race condition identificada no sistema de reservas", "Backend Team", "Possivel reservar o mesmo recurso duas vezes quando requisitado simultaneamente.", "v2.7.3", "Producao"),
            ("Falha na integracao com API de terceiros apos mudanca na documentacao", "Integration Team", "API de pagamentos mudou parametros obrigatorios sem aviso previo.", "v3.0.5", "Producao"),
            ("Erro na compilacao do projeto apos atualizacao do TypeScript", "Frontend Team", "Erros de tipagem apos atualizacao para TypeScript 5.0.", "v4.1.0", "Desenvolvimento"),
            ("Consumo excessivo de CPU no servico de cache", "Infrastructure Team", "Servico de cache consome 100% de CPU apos 24h de execucao.", "v2.5.1", "Producao"),
            ("Problemas de acessibilidade no formulario de cadastro", "UI/UX Team", "Formulario nao e compativel com leitores de tela e nao segue WCAG 2.1.", "v3.4.2", "Producao"),
            ("Falha no sistema de CI/CD impedindo deploys", "DevOps Team", "Pipeline falha na etapa de testes de seguranca sem mensagem de erro clara.", "v4.0.1", "Desenvolvimento"),
            ("Inconsistencia nos dados retornados pela API GraphQL", "Backend Team", "Consultas aninhadas retornam dados incompletos ou incorretos em alguns casos.", "v3.2.1", "Homologacao"),
            ("Vulnerabilidade de XSS identificada no editor de comentarios", "Security Team", "Possivel injetar codigo JavaScript malicioso via editor de comentarios.", "v2.8.0", "Producao")
        ]
        
        for descricao, equipe, passos, versao, ambiente in bugs:
            cur.execute(
                "INSERT INTO bugs (descricao, equipe, passos_reproducao, versao_sistema, ambiente) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                (descricao, equipe, passos, versao, ambiente)
            )
            id_inserido = cur.fetchone()[0]
            print(f"Bug inserido com ID: {id_inserido}")
        
        # Commit das alterações
        conn.commit()
        
        # Verifica os dados inseridos
        cur.execute("SELECT * FROM bugs ORDER BY id;")
        resultados = cur.fetchall()
        print("\nBugs inseridos:")
        for row in resultados:
            print(f"ID: {row[0]}, Equipe: {row[2]}, Descrição: {row[1]}, Versão: {row[6]}, Ambiente: {row[7]}")
        
        cur.close()
        conn.close()
        print("\nProcesso concluído com sucesso!")
        
    except Exception as e:
        print(f"Erro durante a operação: {str(e)}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🔍 Iniciando processo de população do banco de bugs...")
    popular_banco()
