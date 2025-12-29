# Gemini/Vertex AI Setup Guide

## Getting Your Credentials

### Option 1: Using Service Account (Recommended)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **IAM & Admin** > **Service Accounts**
3. Create a new service account or use existing one
4. Grant these roles:
   - **Vertex AI User**
   - **Storage Object Viewer** (if using Cloud Storage)
5. Create a JSON key:
   - Click on the service account
   - Go to **Keys** tab
   - Click **Add Key** > **Create new key** > **JSON**
   - Download the JSON file

### Option 2: Using Application Default Credentials

If you're running locally and have `gcloud` CLI installed:

```bash
gcloud auth application-default login
```

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Gemini/Vertex AI Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json

# LLM Provider
LLM_PROVIDER=gemini

# Optional: OpenAI (if you want to switch later)
# OPENAI_API_KEY=your_openai_key_here
```

## Important Notes

- **Project ID**: Found in Google Cloud Console dashboard
- **Location**: Usually `us-central1`, `us-east1`, or `us-west1`
- **Service Account Key**: Full path to the downloaded JSON file
- **Free Tier**: Vertex AI has a generous free tier for development

## Testing Your Setup

Once configured, you can test by running:

```python
from app.config import settings
print(f"Project: {settings.google_cloud_project}")
print(f"Location: {settings.google_cloud_location}")
```


