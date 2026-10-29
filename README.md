# F1 Performance Analytics — Historical Race Intelligence (2021–2025)

A full-stack web application for exploring Formula 1 data from the 2021–2025 seasons, with AI-powered question answering using semantic retrieval and the Gemini LLM.

## Architecture

```text
F1-Race-Intelligence/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI app with lifespan, CORS, routing
│   │   ├── api/               # Route endpoints
│   │   │   ├── dashboard.py   # Dashboard statistics
│   │   │   ├── drivers.py     # Driver listings and details
│   │   │   ├── constructors.py# Constructor listings and details
│   │   │   ├── chat.py        # RAG chat endpoint (Gemini + Pinecone)
│   │   │   └── races.py       # Race listings and details
│   │   ├── services/          # Business logic services
│   │   │   ├── rag_service.py # Full RAG pipeline (embedding → Pinecone → Gemini)
│   │   │   ├── gemini_service.py # Gemini API wrapper
│   │   │   ├── retrieval_service.py # Query embedding + Pinecone search
│   │   │   └── analytics_service.py # Dashboard data from CSVs
│   │   ├── schemas/           # Pydantic models (planned)
│   │   └── core/
│   │       └── config.py      # Environment configuration
│   ├── requirements.txt       # Python dependencies
│   └── .env.example           # Placeholder environment variables
│
├── frontend/                  # React + Vite + Tailwind frontend
│   ├── src/
│   │   ├── pages/             # Page components
│   │   │   ├── DashboardPage.jsx
│   │   │   ├── AIRaceChat.jsx
│   │   │   ├── RaceExplorer.jsx
│   │   │   ├── DriverComparison.jsx
│   │   │   └── AboutPage.jsx
│   │   ├── components/        # Reusable UI components
│   │   │   ├── ui/            # Button, Input, Card, Typography, MessageBubble
│   │   │   └── chat.jsx       # MessageBubble for chat interface
│   │   ├── App.jsx            # Main router with BrowserRouter + Routes
│   │   ├── main.jsx           # React root render
│   │   ├── vite.config.ts     # Vite configuration
│   │   └── tailwind.config.js # Tailwind CSS configuration
│   ├── package.json           # npm dependencies (React, Recharts, Lucide)
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env.example           # Frontend environment variables
│
├── data/                      # CSV datasets (2021–2025 F1)
│   ├── circuits.csv
│   ├── constructors.csv
│   ├── driver_standings.csv
│   ├── drivers.csv
│   ├── lap_times.csv
│   ├── pit_stops.csv
│   ├── qualifying.csv
│   ├── race_results.csv
│   ├── races.csv
│   ├── results.csv
│   ├── constructor_standings.csv
│   ├── seasons.csv
│   └── ...
│
├── existing ingestion modules # Original Python pipeline (unchanged)
│   ├── ingest.py
│   ├── pinecone_store.py
│   ├── embedding_service.py
│   ├── data_loader.py
│   ├── preprocessor.py
│   ├── config.py
│   └── utils.py
│
├── .gitignore                # Rules for excluding sensitive/local files
├── README.md                 # This comprehensive guide
└── requirements.txt          # Original pipeline dependencies
```

## Prerequisites

### Python (Backend)

- Python 3.10+
- pip (Python package manager)

### Node.js & npm (Frontend)

- Node.js 20+ LTS
- npm 10+ (comes with Node.js)

### External Services

- **Pinecone account** with index `f1-racing` (namespace: `f1-2021-2025`) already created
  - Index must use dense vectors with dimension **384**
  - The index must already contain the uploaded vectors from the ingestion pipeline
- **Google Gemini API key** with access to a supported model (e.g., `gemini-1.5-flash`)
- **F1 dataset** CSV files (included in the `data/` directory)

## Setup Instructions

### 1. Python Backend Setup

```powershell
# 1.1 Create and activate virtual environment
cd F1-Race-Intelligence\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 1.2 Install Python dependencies
pip install -r requirements.txt

# 1.3 Configure environment variables
# Copy the example .env and fill in your values
copy .env.example .env
# Edit backend/.env:
#   - GEMINI_API_KEY=your_google_gemini_api_key
#   - PINECONE_API_KEY=your_pinecone_api_key
#   - PINECONE_INDEX_NAME=f1-racing  (must match your index)
#   - PINECONE_NAMESPACE=f1-2021-2025

# 1.3 Verify the existing pipeline data is available
# The backend reads the CSV data from ../data/ relative to the project root
# Ensure the data/ directory contains the F1 CSV datasets

# 1.4 Start the backend server
uvicorn app.main:app --reload
# Server will be available at http://localhost:8000
```

### 2. Node.js Frontend Setup

```powershell
# 2.1 Install Node.js dependencies
cd F1-Race-Intelligence\frontend
npm install

# 2.2 Start the development server
npm run dev
# Frontend will be available at http://localhost:5173
```

### 3. Verify the Full Stack

```powershell
# In first terminal (backend):
cd F1-Race-Intelligence\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload

# In second terminal (frontend):
cd F1-Race-Intelligence\frontend
npm run dev

# Open http://localhost:5173 in your browser
# The dashboard should load with F1 season 2021 data
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET /` | `/` | Root endpoint — basic app info |
| `GET /api/health` | Health check |
| `GET /api/v1/health` | Health check (v1) |
| `GET /api/seasons` | `[\$2021,\$2022,\$2023,\$2024,\$2025]` | Available F1 seasons |
| `GET /api/dashboard?season=\$YEAR` | Dashboard statistics for a season |
| `GET /api/races?season=\$YEAR` | List of races for a season |
| `GET /api/races/\$RACE_ID` | Race details and results |
| `GET /api/drivers` | List of all drivers |
| `GET /api/drivers/\$ID` | Driver detailed statistics |
| `GET /api/constructors` | List of all constructors |
| `GET /api/constructors/\$ID` | Constructor detailed statistics |
| `POST /api/chat` | Send a question through the RAG pipeline |
| `GET /api/chat/sources/\$request_id` *(planned)* | Retrieve source records for a chat request |

### Chat Endpoint Details

```json
POST /api/chat
{
  "question": "How did Lewis Hamilton perform in the 2021 Bahrain Grand Prix?",
  "top_k": 5,
  "season_filter": 2021,
  "driver_filter": "Lewis Hamilton",
  "constructor_filter": "Mercedes"
}
```

**Successful Response:**
```json
{
  "answer": "Lewis Hamilton finished first in the 2021 Bahrain Grand Prix for Mercedes, scoring 25 championship points...",
  "sources": [
    {
      "season": "2021",
      "grand_prix": "Bahrain Grand Prix",
      "driver": "Lewis Hamilton",
      "constructor": "Mercedes",
      "document_type": "race_result",
      "similarity_score": "0.9421"
    }
  ],
  "context_used": "Race: Bahrain Grand Prix ...",
  "retrieval_stats": {
    "total_retrieved": 3,
    "filtered_out_empty_text": 0,
    "query": "How did Lewis Hamilton perform in the 2021 Bahrain Grand Prix?"
  },
  "model_used": "gemini-1.5-flash",
  "success": true
}
```

**Error Response:**
```json
{
  "answer": "",
  "sources": [],
  "context_used": "",
  "retrieval_stats": {},
  "model_used": "gemini-1.5-flash",
  "success": false,
  "error": "Insufficient data: No relevant records found in the F1 dataset for this query."
}
```

## Obtaining API Keys

### Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API key" → "Create API key"
4. Choose a supported model: `gemini-1.5-flash` (recommended), `gemini-1.5-pro`, or `gemini-1.0-pro`
5. Copy the key and add it to `backend/.env` as `GEMINI_API_KEY`

### Pinecone Index

1. Go to [Pinecone Console](https://www.pinecone.io/)
2. Create a new index if you haven't already:
   - **Name:** `f1-racing`
   - **Dimension:** `384` (must match `all-MiniLM-L6-v2`)
   - **Metric:** `cosine`
   - **Environment:** Choose appropriate (on-serverless pods default)
3. The index must already contain vectors from the F1 ingestion pipeline
   - Run `python ingest.py test_batch` to upload a test batch
   - Or `python ingest.py full` to upload all 27,038 documents

## Development Workflow

### Starting the Application

```powershell
# Terminal 1 - Backend
cd F1-Race-Intelligence\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
# → http://localhost:8000

# Terminal 2 - Frontend  
cd F1-Race-Intelligence\frontend
npm run dev
# → http://localhost:5173
```

### Adding New API Endpoints

1. Create a new file in `backend/app/api/` (e.g., `new_feature.py`)
2. Define FastAPI route functions with Pydantic schemas
3. Register the router in `backend/app/main.py`:
   ```python
   from ...app.api import new_feature
   app.include_router(new_feature.router)
   ```
4. Add TypeScript types in the frontend if needed
5. Test with `curl` or the frontend UI

### Running Tests

```powershell
# Backend tests
cd F1-Race-Intelligence\backend
.\.venv\Scripts\Activate.ps1
pytest tests/ -v

# Frontend tests (if configured)
cd F1-Race-Intelligence\frontend
npm test
```

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| `GEMINI_API_KEY not found` | Set `GEMINI_API_KEY` in `backend/.env` |
| `PINECONE_API_KEY not found` | Set `PINECONE_API_KEY` in `backend/.env` |
| `Index 'f1-racing' not found` | Create the Pinecone index with dimension 384 and upload data |
| `Rate limit exceeded` | Wait before retrying; check Gemini quota |
| `CORS error` | Configure `allow_origins` in `main.py` for production |
| `No relevant records found` | The query may be outside the 2021–2025 dataset coverage |
| Frontend won't compile | Run `npm install` and ensure Node.js 20+ is available |

### Development Tips

- The backend never re-ingests data on startup — it reads CSVs directly and queries Pinecone
- All API keys stay on the backend; the frontend never sees Gemini or Pinecone keys
- Use `python ingest.py dry_run` to verify document generation without Pinecone upload
- Use `python ingest.py validate` to check document quality and Pinecone metadata
- Chat questions about 2021–2025 seasons will have the best retrieval results

## What Works (Verified)

✅ Dashboard data from actual CSV dataset (seasons, races, drivers, constructors)  
✅ CLI pipeline modes: `dry_run`, `test_batch`, `full`, `validate`  
✅ Pinecone vector upload via `test_batch` mode (13,519 vectors uploaded)  
✅ Retrieval with meaningful text metadata (no empty "text" fields)  
✅ Gemini answer generation with grounded evidence  
✅ Source citation in chat responses  
✅ Idempotent reruns (no duplicate vectors)  
✅ Empty-state handling when data is insufficient  

## Known Limitations

⚠️ Chat questions about events outside 2021–2025 will have limited/no retrieval  
⚠️ Some driver/constructor statistics may have incomplete data (lap times, practice results)  
⚠️ AI answers rely on retrieved evidence — if retrieval returns empty context, the model states this  
⚠️ Frontend requires Node.js 20+ and npm 10+  
⚠️ Pinecone index must be pre-created with dimension 384 and populated with data  

## Deployment

### Production Checklist

- [ ] Set `GEMINI_API_KEY` and `PINECONE_API_KEY` in production `.env`
- [ ] Restrict `allow_origins` in CORS to your domain
- [ ] Pin the Gemini model version in `backend/.env`
- [ ] Backup Pinecone index state
- [ ] Enable backend logging to file (currently console-only)
- [ ] Run `python ingest.py validate` to verify data quality before going live
- [ ] Test all API endpoints with edge cases (missing seasons, empty queries, etc.)

### Cloud Deployment (examples)

- **Backend:** Deploy FastAPI to Cloud Run, Cloud Functions, or any Python-capable hosting
- **Frontend:** Deploy Vite build to Netlify, Vercel, or GitHub Pages
- **Pinecone:** Keep the index always-on; no additional setup needed

## License

This project is for educational and research purposes. F1 data is sourced from open-championship records.
No official Formula 1 branding or copyrighted assets are used.