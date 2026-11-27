# DEPLOYMENT

## Public URL

- Nền tảng chính: **Railway** (service agent + Redis trong cùng project)
- URL: https://k5-l3a-day14-nguyenthidung-2a202603508-deploymen-production.up.railway.app
- Code deploy: thư mục `06-lab-complete/` (Root Directory đặt trên Railway), build bằng `Dockerfile`.

## Lệnh kiểm tra

Thay `<YOUR_KEY>` bằng `AGENT_API_KEY` đã đặt trên Railway (không ghi key thật vào repo).

```bash
URL=https://k5-l3a-day14-nguyenthidung-2a202603508-deploymen-production.up.railway.app

# Health / readiness -> 200
curl -i $URL/health
curl -i $URL/ready

# Không có API key -> 401
curl -i -X POST $URL/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'

# Có API key -> 200
curl -i -X POST $URL/ask -H "X-API-Key: <YOUR_KEY>" -H "Content-Type: application/json" -d '{"question":"Hello"}'
```

Kết quả đã chạy:

| Lệnh | Kết quả |
|---|---|
| `GET /health` | 200 `{"status":"ok"}` |
| `GET /ready` | 200 |
| `POST /ask` không key | 401 `{"detail":"Invalid or missing API key"}` |
| `POST /ask` có `X-API-Key` | 200, trả về `question` và `answer` |

## Biến môi trường đặt trên Railway

Giá trị bí mật không được ghi ở đây.

| Biến | Giá trị / nguồn |
|---|---|
| `REDIS_URL` | Tham chiếu `${{Redis.REDIS_URL}}` tới service Redis của Railway |
| `AGENT_API_KEY` | Chuỗi ngẫu nhiên tạo bằng `openssl rand -hex 16` (bí mật) |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `MONTHLY_BUDGET_USD` | `30.0` |

`PORT` do Railway tự cấp; app đọc `${PORT}` trong `Dockerfile`.

## Screenshots

- `screenshots/dashboard.png`: Railway dashboard, service agent và Redis đang Online
- `screenshots/running.png`: `/health` và `/ready` trả 200
- `screenshots/test.png`: `/ask` trả 401 khi không có key và 200 khi có key

## So sánh `railway.toml` và `render.yaml`

| Tiêu chí | `railway.toml` | `render.yaml` |
|---|---|---|
| Phạm vi | Chỉ cấu hình build và deploy cho một service | Khai báo toàn bộ hạ tầng: web service và Redis (`keyvalue`) |
| Build | `builder = "DOCKERFILE"` | `runtime: docker`, `dockerfilePath: ./Dockerfile` |
| Health check | `healthcheckPath = "/health"`, timeout 30s | `healthCheckPath: /health` |
| Restart | `restartPolicyType = "ON_FAILURE"`, tối đa 3 lần | Không khai báo, dùng mặc định của Render |
| Biến môi trường | Đặt trong dashboard Railway, file không chứa giá trị | Khai báo ngay trong file; `AGENT_API_KEY` dùng `generateValue: true` |
| Redis | Thêm bằng tay trên dashboard, nối bằng `${{Redis.REDIS_URL}}` | Khai báo `keyvalue` trong file, nối bằng `fromService` |
| Gói | Trial của Railway | `plan: free` |

Nhận xét: `render.yaml` mô tả cả Redis nên triển khai lặp lại được từ file (infrastructure as code). Với Railway, phần Redis và biến môi trường phải thao tác trên dashboard.

## Cloud Run (chỉ đọc, không deploy)

`03-cloud-deployment/production-cloud-run/cloudbuild.yaml` là pipeline CI/CD của Google Cloud Build, chạy khi push lên `main`:

1. **test**: cài `requirements.txt` và chạy `pytest tests/`.
2. **build**: build image Docker, gắn tag theo `$COMMIT_SHA` và `latest`, dùng `--cache-from` để tận dụng cache layer.
3. **push**: đẩy image lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **deploy**: `gcloud run deploy` lên vùng `asia-southeast1`, `min-instances=1` để tránh cold start, `max-instances=10`, bí mật lấy từ Secret Manager qua `--set-secrets`.
