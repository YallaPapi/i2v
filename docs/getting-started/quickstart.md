# Quick Start

## Start the Servers

### Backend

```bash
cd i2v
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd i2v/frontend
npm run dev
```

Access the app at `http://localhost:5173`

## Create Your First Pipeline

1. Open the frontend at `http://localhost:5173`
2. Click "New Pipeline"
3. Upload an image or provide an image URL
4. Select a model (e.g., WAN 2.1)
5. Add a motion prompt describing the video
6. Click "Generate"

## Using the API

### Create a Pipeline

```bash
curl -X POST http://localhost:8001/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Pipeline",
    "model": "wan-2.1",
    "motion_prompt": "A gentle breeze moves through the scene"
  }'
```

### Run a Pipeline

```bash
curl -X POST http://localhost:8001/pipelines/1/run \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg"
  }'
```

### Check Job Status

```bash
curl http://localhost:8001/jobs/1
```
