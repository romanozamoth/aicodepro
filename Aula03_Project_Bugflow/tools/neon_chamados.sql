
/* Tabela de bugs e incidentes */
CREATE TABLE bugs (
    id SERIAL PRIMARY KEY,
    descricao TEXT NOT NULL,
    equipe VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'Aberto',
    data_abertura TIMESTAMP DEFAULT NOW(),
    passos_reproducao TEXT,
    versao_sistema VARCHAR(100),
    ambiente VARCHAR(50) DEFAULT 'Produção'
);

/* Classificacao por componente (setor) */
CREATE TABLE classificacao_setor (
    id SERIAL PRIMARY KEY,
    chamado_id INT REFERENCES bugs(id),
    setor VARCHAR(50) NOT NULL CHECK (setor IN ('Frontend', 'Backend', 'Database', 'DevOps', 'Security', 'Integration', 'UI/UX', 'Infrastructure')),
    justificativa TEXT,
    data_classificacao TIMESTAMP DEFAULT NOW()
);

/* Classificacao por severidade (prioridade) */
CREATE TABLE classificacao_prioridade (
    id SERIAL PRIMARY KEY,
    chamado_id INT REFERENCES bugs(id),
    prioridade VARCHAR(20) NOT NULL CHECK (prioridade IN ('Critico', 'Grave', 'Menor')),
    impacto TEXT,
    data_classificacao TIMESTAMP DEFAULT NOW()
);

/* Analise tecnica do bug */
CREATE TABLE analise_tecnica (
    id SERIAL PRIMARY KEY,
    bug_id INT REFERENCES bugs(id),
    causa_raiz TEXT NOT NULL,
    impacto_tecnico TEXT,
    abordagem_debugging TEXT,
    solucoes_propostas TEXT,
    potenciais_efeitos_colaterais TEXT,
    arquivos_afetados TEXT,
    data_analise TIMESTAMP DEFAULT NOW()
);

/* Gerenciamento da resolucao (andamento_chamados) */
CREATE TABLE andamento_chamados (
    id SERIAL PRIMARY KEY,
    chamado_id INT REFERENCES bugs(id),
    responsavel VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('Atribuido', 'Em desenvolvimento', 'Em teste', 'Aguardando review', 'Resolvido', 'Fechado')),
    data_atualizacao TIMESTAMP DEFAULT NOW()
);

/* Documentacao do bug (relatorio_final) */
CREATE TABLE relatorio_final (
    id SERIAL PRIMARY KEY,
    chamado_id INT REFERENCES bugs(id),
    conclusao TEXT NOT NULL,
    resolvido BOOLEAN DEFAULT FALSE,
    data_conclusao TIMESTAMP DEFAULT NOW()
);
