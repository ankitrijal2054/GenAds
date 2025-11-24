# 🎬 AI Ad Video Generator

An intelligent system that transforms product briefs into professional, brand-consistent promotional videos using AI-powered scene planning, product extraction, and smart compositing.

## 🎯 Core Innovation

Rather than trusting AI to generate perfect products (which it can't), we:
1. **Extract** your product image (remove background)
2. **Generate** beautiful backgrounds without the product
3. **Composite** your product perfectly onto backgrounds
4. **Apply** consistent styling to all scenes

**Result:** Pixel-perfect product consistency across all scenes.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- FFmpeg

### Installation

1. **Clone and setup:**
   ```bash
   cd GenAds
   cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
   cd ../frontend && npm install
   ```

2. **Configure environment** (see `SETUP_GUIDE.md`):
   - Create `backend/.env` with Supabase, Railway, S3, and API keys
   - Create `frontend/.env` with Supabase credentials

3. **Start development servers:**
   ```bash
   # Terminal 1: Backend
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload --port 8000

   # Terminal 2: Frontend  
   cd frontend
   npm run dev
   ```

4. **Access:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## 📁 Project Structure

```
GenAds/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Configuration management
│   │   ├── database/            # Database layer
│   │   ├── models/              # Pydantic schemas
│   │   ├── services/            # Business logic services
│   │   ├── api/                 # API endpoints
│   │   └── jobs/                # Background job pipeline
│   ├── worker.py                # RQ worker process
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main component
│   │   ├── main.tsx             # React entry point
│   │   ├── pages/               # Page components
│   │   ├── components/          # Reusable components
│   │   └── hooks/               # Custom React hooks
│   ├── package.json
│   └── vite.config.ts
│
├── memory-bank/                 # Project documentation
├── AI_Docs/                     # Reference documents
└── SETUP_GUIDE.md              # Detailed setup instructions
```

## 🔧 Tech Stack

### Frontend
- React 18 + TypeScript + Vite
- Tailwind CSS + shadcn/ui
- Framer Motion (animations)
- Supabase JS Client
- React Router

### Backend
- FastAPI (Python)
- Supabase (Postgres + Auth)
- Redis + RQ (Job Queue)
- AWS S3 (Video Storage)

### AI Services
- Wān Model (Video Generation via Replicate)
- MusicGen (Audio Generation via Replicate)
- GPT-4o-mini (Scene Planning via OpenAI)
- rembg (Product Extraction)

### Processing
- OpenCV (Compositing)
- FFmpeg (Video Rendering)
- PIL/Pillow (Image Processing)

## 📋 MVP Features

- ✅ Scene planning with LLM
- ✅ Product extraction + compositing
- ✅ Multi-scene video generation
- ✅ Background music generation
- ✅ Text overlay rendering
- ✅ Real-time progress tracking
- ✅ Prompt based scene editing
- ✅ Manual video editing

## 🎬 How It Works

### User Journey

1. **Input:** User provides:
   - Product image
   - Brand brief (2-3 sentences)
   - Duration, mood, colors

2. **Planning:** AI breaks brief into scenes:
   - Hook (attention grabber)
   - Product showcase
   - Benefit demo
   - Lifestyle context
   - Call-to-action

3. **Generation:** Parallel processing:
   - Extract product (rembg)
   - Generate backgrounds (Wān model)
   - Generate music (MusicGen)
   - Composite product onto backgrounds
   - Add text overlays
   - Render final video

4. **Output:** Three formats ready to download:
   - 9:16 (Vertical - TikTok/Reels)
   - 1:1 (Square - Instagram)
   - 16:9 (Horizontal - YouTube)

## 🛠️ Development Commands

```bash
# Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload              # Dev server
python -m pytest app/services/             # Run tests
python worker.py                           # Start RQ worker

# Frontend
cd frontend
npm run dev                                # Dev server
npm run build                              # Production build
npm run lint                               # Linting
```

## 🚀 Deployment

- **Backend:** Railway (Web service + RQ worker)
- **Frontend:** Vercel
- **Database:** Supabase
- **Storage:** AWS S3
- **Auto-scaling:** Add more RQ workers as needed

## 📝 License

MIT

