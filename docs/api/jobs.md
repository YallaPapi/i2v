# Jobs API

## List Jobs

```http
GET /jobs
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `skip` | int | Number to skip |
| `limit` | int | Max to return |
| `status` | string | Filter by status |

## Get Job

```http
GET /jobs/{job_id}
```

**Response:**

```json
{
  "id": 1,
  "pipeline_id": 1,
  "status": "completed",
  "model": "wan-2.1",
  "request_id": "fal-xxx",
  "video_url": "https://cdn.example.com/videos/xxx.mp4",
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:05:00Z"
}
```

## Job Statuses

| Status | Description |
|--------|-------------|
| `pending` | Job created, not started |
| `running` | Processing on Fal.ai |
| `completed` | Video ready |
| `failed` | Generation failed |
