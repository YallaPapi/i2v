# Configuration

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `FAL_KEY` | Fal.ai API key for video generation | `fal-xxx-xxx` |

### R2 CDN (Optional)

| Variable | Description | Example |
|----------|-------------|---------|
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key | `xxx` |
| `R2_SECRET_ACCESS_KEY` | R2 secret access key | `xxx` |
| `R2_ENDPOINT` | R2 S3-compatible endpoint | `https://xxx.r2.cloudflarestorage.com` |
| `R2_BUCKET_NAME` | R2 bucket name | `i2v` |
| `R2_PUBLIC_DOMAIN` | R2 public domain for URLs | `cdn.example.com` |

### Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | SQLite database path | `wan_jobs.db` |

## Model Configuration

Available models in `app/fal_client.py`:

| Model | ID | Description |
|-------|-----|-------------|
| WAN 2.1 | `wan-2.1` | High quality video generation |
| Hunyuan | `hunyuan` | Alternative model |
| Kling | `kling-1.6-pro` | Kling video model |

## Rate Limiting

Configure in `app/services/rate_limiter.py`:

- Default: 10 requests/minute per model
- Configurable per-model limits
