# Knowledge Platform

MVP de plataforma RAG com foco em documentos (PDF, TXT e MD), usando FastAPI + PostgreSQL/pgvector.

https://github.com/user-attachments/assets/9f5dcbb6-637a-4890-9d17-75c75965336f

## Status atual

Este repositório ja possui uma primeira versao funcional com:

- Ingestao de documentos (PDF, TXT, MD)
- Geracao de embeddings com Sentence Transformers
- Indexacao vetorial em pgvector
- Busca semantica
- Endpoint de chat com citacoes

## Stack atual

- Python 3.12+
- FastAPI
- PostgreSQL 16 + pgvector
- Sentence Transformers (`all-MiniLM-L6-v2`)
- OpenAI (opcional, para resposta gerativa mais completa)
- Docker Compose (para banco, API e UI)

## Arquitetura

```mermaid
flowchart LR
		A[PDF TXT MD] --> B[Ingestion]
		B --> C[Markdown-like text]
		C --> D[Chunking]
		D --> E[Embedding]
		E --> F[PostgreSQL pgvector]
		G[Question] --> H[Semantic Search]
		H --> I[Top K chunks]
		I --> J[Answer generation]
		J --> K[Answer plus citations]
```

## Estrutura

```text
knowledge-platform/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── document_ingestion.py
│   ├── embeddings.py
│   ├── generation.py
│   ├── ingestion.py
│   ├── main.py
│   ├── retrieval.py
│   ├── schemas.py
│   └── vectorstore.py
├── input/                    # Pasta para documentos a ingerir
├── ui_gradio.py             # Interface Gradio
├── docker-compose.yml       # Orquestração de serviços
├── Dockerfile               # Build da API
├── requirements.txt         # Dependências Python
├── .env.example             # Exemplo de variáveis de ambiente
├── .env                     # Variáveis locais (não versionado)
├── .gitignore
└── README.md
```

## Variáveis de Ambiente

Crie um arquivo `.env` baseado em `.env.example`:

```bash
# Banco de dados
DATABASE_URL=postgresql://user:password@localhost:5432/knowledge_db

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2

# OpenAI (opcional, para geração mais completa)
OPENAI_API_KEY=sk-...
```

## Como rodar

### Com Docker (recomendado)

```bash
# Subir stack completa: PostgreSQL + API + UI
docker compose up -d
```

Serviços publicados:
- **API**: http://127.0.0.1:8000
- **Docs Swagger**: http://127.0.0.1:8000/docs
- **UI Gradio**: http://127.0.0.1:7860

### Local (sem Docker)

1. Criar ambiente virtual:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

2. Instalar dependências:

```bash
pip install -r requirements.txt
```

3. Configurar variáveis de ambiente:

```bash
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

4. Subir a API:

```bash
uvicorn app.main:app --reload
```

5. Em outro terminal, subir UI Gradio:

```bash
python ui_gradio.py
```

## Exemplos de Uso

### Ingesta de Documento (POST /ingest)

```powershell
# Windows PowerShell
$body = @{
    document_path = "./input/meu_documento.pdf"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:8000/ingest" `
  -ContentType "application/json" `
  -Body $body
```

### Chat com Busca Semântica (POST /chat)

```powershell
# Fazer pergunta com recuperação de contexto
$body = @{
    question = "Quais padrões aparecem entre cargo e tempo de experiência?"
    top_k = 3
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:8000/chat" `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 6
```

### Busca Semântica (GET /search)

```powershell
$params = "query=experiencia&top_k=5"
Invoke-RestMethod -Method GET `
  -Uri "http://127.0.0.1:8000/search?$params"
```

A interface ficara em `http://127.0.0.1:7860`.

## Endpoints

- `GET /health`
- `POST /ingest/csv`
- `POST /ingest/documents`
- `POST /search`
- `POST /chat`

## UI para demo

- Arquivo: `ui_gradio.py`
- A UI de demo exibe apenas os resultados principais (sem painel de resposta JSON).
- Fluxo recomendado:
	1. Ingerir documentos na aba **Ingest Documents**
  1. Validar resultados na aba **Search**
	1. Fazer perguntas na aba **Chat** (resposta com rolagem + tabela de citacoes)

## Exemplos de uso

### 1) Ingerir documentos da pasta input

```bash
curl -X POST "http://127.0.0.1:8000/ingest/documents" ^
	-H "Content-Type: application/json" ^
	-d "{\"input_path\":\"input\",\"prefer_docling\":true,\"chunk_size\":1200,\"chunk_overlap\":150}"
```

### 2) Buscar contexto

```bash
curl -X POST "http://127.0.0.1:8000/search" ^
	-H "Content-Type: application/json" ^
	-d "{\"query\":\"quais clausulas do contrato tratam de rescisao\",\"top_k\":5}"
```

### 3) Perguntar no chat

```bash
curl -X POST "http://127.0.0.1:8000/chat" ^
	-H "Content-Type: application/json" ^
	-d "{\"question\":\"quais pontos principais aparecem nos documentos sobre contrato e desligamento\",\"top_k\":5}"
```

## Observacoes

- Sem `OPENAI_API_KEY`, o endpoint `/chat` responde em modo fallback usando os chunks recuperados.
- Com `OPENAI_API_KEY`, a resposta gerativa usa o modelo definido em `OPENAI_MODEL`.
- Proximo passo natural: adicionar chunking por schema semantico + reranker para aumentar a precisao.

## Operacao e limpeza de ambiente (Docker)

### Parar e subir servicos

```bash
docker compose down
docker compose up -d --build api ui
```

### Limpar dados antigos indexados no banco

Mesmo removendo arquivos de `input`, os chunks antigos continuam no PostgreSQL (volume persistente). Para resetar apenas os dados indexados:

```bash
docker compose up -d postgres
docker compose exec postgres psql -U postgres -d knowledge_platform -c "TRUNCATE TABLE rag_chunks RESTART IDENTITY;"
```

Depois, suba API/UI novamente:

```bash
docker compose up -d --build api ui
```

### Reset total (incluindo volume do Postgres)

```bash
docker compose down -v --remove-orphans
docker compose up -d --build
```

## Troubleshooting da UI

### Chat travado em fila

Se a UI mostrar requisicao pendente por muito tempo, reinicie os servicos:

```bash
docker compose restart api ui
```

Se necessario, acompanhe logs:

```bash
docker compose logs -f api ui
```

### Sobre o indicador de queue no Gradio

- O chat atualiza 2 componentes na mesma acao (resposta e citacoes), por isso pode parecer que existem varias filas.
- Nesta demo, as acoes de botoes foram configuradas com `queue=False` para evitar esse comportamento visual de fila.

## Install

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python main.py
```

---

# Environment Variables

```env
LLM_PROVIDER=openai

OPENAI_API_KEY=

EMBEDDING_PROVIDER=openai

DATABASE_URL=

REDIS_URL=

PGVECTOR_COLLECTION=documents

RERANKER_MODEL=BAAI/bge-reranker-large

TOP_K=20

FINAL_K=5
```

---

# Example Flow

```mermaid
sequenceDiagram

User->>API: Upload PDF

API->>Ingestion: Read document

Ingestion->>Chunker: Split

Chunker->>Embeddings: Generate vectors

Embeddings->>Postgres: Store

User->>API: Ask question

API->>Retriever: Search

Retriever->>Reranker: Reorder

Reranker->>LLM: Build prompt

LLM-->>API: Answer

API-->>User: Response with citations
```

---

# Future Improvements

- Hybrid Search (BM25 + Vector)
- Multi-tenant support
- Incremental indexing
- Streaming responses
- Langfuse integration
- OpenTelemetry
- Redis semantic cache
- MCP document connector
- OCR support
- Image embeddings
- Multi-modal RAG

---

# License

MIT
