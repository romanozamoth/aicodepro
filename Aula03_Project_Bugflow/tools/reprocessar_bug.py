# -*- coding: utf-8 -*-
import psycopg2
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Caminho absoluto para o .env na raiz do projeto
dotenv_path = Path(__file__).resolve().parents[1] / ".env"

# Carregar variaveis do arquivo .env
load_dotenv(dotenv_path=dotenv_path)
DB_URL = os.getenv("NEON_DB_URL")

def verificar_estrutura_tabela(tabela, conn):
    """Verifica a estrutura de uma tabela e retorna suas colunas."""
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = '{tabela}'
        """)
        colunas = [row[0] for row in cur.fetchall()]
        print(f"Colunas da tabela {tabela}: {colunas}")
        return colunas
    except Exception as e:
        print(f"Erro ao verificar estrutura da tabela {tabela}: {str(e)}")
        return []
    finally:
        cur.close()

def reabrir_bug(bug_id):
    """Reabre um bug específico para processamento."""
    try:
        # Conectar ao banco
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar se o bug existe
        cur.execute("SELECT id, descricao FROM bugs WHERE id = %s", (bug_id,))
        bug = cur.fetchone()
        
        if not bug:
            print(f"Bug com ID {bug_id} não encontrado.")
            return False
        
        # Verificar quais tabelas existem
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('relatorio_final', 'andamento_chamados', 'analise_tecnica', 'classificacao_prioridade', 'classificacao_setor')
        """)
        tabelas_existentes = [row[0] for row in cur.fetchall()]
        print(f"Tabelas encontradas: {tabelas_existentes}")
        
        # Verificar estrutura das tabelas e remover registros relacionados
        for tabela in tabelas_existentes:
            try:
                # Verificar estrutura da tabela para encontrar a coluna que referencia bugs
                colunas = verificar_estrutura_tabela(tabela, conn)
                
                # Procurar por colunas que podem referenciar a tabela bugs
                coluna_referencia = None
                for coluna in colunas:
                    if 'bug' in coluna.lower() or 'chamado' in coluna.lower() or 'id_' in coluna.lower():
                        coluna_referencia = coluna
                        break
                
                if coluna_referencia:
                    cur.execute(f"DELETE FROM {tabela} WHERE {coluna_referencia} = %s", (bug_id,))
                    print(f"Registros removidos da tabela {tabela} usando coluna {coluna_referencia}")
                else:
                    print(f"Não foi possível encontrar uma coluna de referência na tabela {tabela}")
            except Exception as e:
                print(f"Erro ao remover registros da tabela {tabela}: {str(e)}")
                conn.rollback()
        
        # Atualizar status do bug para "Aberto"
        cur.execute("UPDATE bugs SET status = 'Aberto' WHERE id = %s", (bug_id,))
        conn.commit()
        
        print(f"Bug #{bug_id} reaberto com sucesso: {bug[1]}")
        print("Execute 'python agents/crewai_agents.py' para processá-lo novamente.")
        return True
        
    except Exception as e:
        print(f"Erro ao reabrir bug: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return False
    
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python reprocessar_bug.py <bug_id>")
        sys.exit(1)
    
    try:
        bug_id = int(sys.argv[1])
        reabrir_bug(bug_id)
    except ValueError:
        print("O ID do bug deve ser um número inteiro.")
        sys.exit(1)
