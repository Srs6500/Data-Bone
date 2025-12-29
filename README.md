# Student Performance Enhancer

AI-powered tool that helps students identify knowledge gaps between what they've learned and what's required for assignments/exams. Specifically designed for Computer Science and Mathematics courses.

## Problem Statement

Students often find that even after paying attention in classes, their assignments are not solvable. They rely on AI to solve problems, then try to learn from solutions, which consumes time and resources. Additionally, exam questions differ from what they studied, causing poor performance.

## Solution

This tool:
- Analyzes professor notes, assignments, and course materials
- Automatically detects missing concepts and knowledge gaps
- Categorizes gaps as Critical (🔴) or Safe (🟢)
- Provides explanations and practice questions
- Acts as a "second brain" by proactively suggesting exam variations
- Offers context-aware chat for specific questions

## Tech Stack

### Backend
- **FastAPI** - Python web framework
- **Google Vertex AI (Gemini Pro)** - LLM for analysis and explanations
- **LangChain** - RAG framework
- **ChromaDB** - Vector database for embeddings
- **Sentence Transformers** - Embedding generation
- **PyPDF2/pdfplumber** - PDF processing

### Frontend
- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Axios** - API client

## Project Structure

```
.
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # API routes
│   │   ├── services/ # Business logic
│   │   ├── ai/       # AI/ML components
│   │   ├── models/   # Data models
│   │   └── utils/    # Utilities
│   └── requirements.txt
│
└── frontend/         # Next.js frontend
    ├── app/          # Next.js app directory
    ├── components/   # React components
    ├── lib/          # Utilities
    └── types/        # TypeScript types
```

## Getting Started

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
OPENAI_API_KEY=your_api_key_here
```

5. Run the server:
```bash
uvicorn app.main:app --reload
```

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000)

## Features (Planned)

- [x] Project structure and setup
- [ ] PDF upload and processing
- [ ] Document analysis and gap detection
- [ ] Gap categorization (Critical/Safe)
- [ ] Practice question generation
- [ ] Context-aware chat
- [ ] Second brain variations

## Development Status

Currently in active development. See individual README files in `backend/` and `frontend/` directories for more details.

## License

MIT

