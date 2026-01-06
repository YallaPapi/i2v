# Pipelines API

## List Pipelines

```http
GET /pipelines
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `skip` | int | Number of records to skip (default: 0) |
| `limit` | int | Max records to return (default: 100) |

**Response:**

```json
[
  {
    "id": 1,
    "name": "My Pipeline",
    "model": "wan-2.1",
    "status": "completed",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

## Get Pipeline

```http
GET /pipelines/{pipeline_id}
```

## Create Pipeline

```http
POST /pipelines
```

**Request Body:**

```json
{
  "name": "Pipeline Name",
  "model": "wan-2.1",
  "motion_prompt": "Description of motion",
  "image_url": "https://example.com/image.jpg"
}
```

## Run Pipeline

```http
POST /pipelines/{pipeline_id}/run
```

Starts video generation for the pipeline.

## Download Output

```http
GET /pipelines/download?url={url}
```

Proxy endpoint for downloading videos/images from CDN.
