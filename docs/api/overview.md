# API Overview

The i2v API is built with FastAPI and provides RESTful endpoints for video generation pipelines.

## Base URL

```
http://localhost:8001
```

## Authentication

Currently, the API does not require authentication. For production, implement API key authentication.

## Response Format

All responses are JSON:

```json
{
  "id": 1,
  "status": "completed",
  "data": {...}
}
```

## Error Handling

Errors return appropriate HTTP status codes:

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid data format |
| 500 | Internal Server Error |

Error response format:

```json
{
  "detail": "Error description"
}
```

## Rate Limiting

The API implements per-model rate limiting to prevent Fal.ai quota exhaustion.

## OpenAPI Documentation

Interactive API docs available at:

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`
