# Installation

## Prerequisites

- Python 3.10+
- Node.js 18+
- Fal.ai API key
- (Optional) Cloudflare R2 account for CDN caching

## Backend Setup

```bash
# Clone repository
git clone https://github.com/your-repo/i2v.git
cd i2v

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

## Frontend Setup

```bash
cd frontend
npm install
```

## Environment Configuration

Create `.env` file in project root:

```bash
# Required
FAL_KEY=your_fal_api_key

# Optional - R2 CDN
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
R2_BUCKET_NAME=i2v
R2_PUBLIC_DOMAIN=your-r2-domain.r2.dev
```

## Database Initialization

The SQLite database is created automatically on first run.

```bash
# Start server to initialize DB
uvicorn app.main:app --port 8001
```
