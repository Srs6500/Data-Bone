# Student Performance Enhancer - Backend

AI-powered backend for analyzing student documents and detecting knowledge gaps.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```bash
# Add your Google Cloud credentials (see SETUP_GEMINI.md)
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

3. Run the server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check

More endpoints will be added as we build the application.

