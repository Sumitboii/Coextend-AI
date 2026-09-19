# Docker Deployment Guide — Coextend Prospect Intelligence MVP

## Files Created

1. **Dockerfile** — Development multi-stage build (optimized for iteration)
2. **Dockerfile.prod** — Production multi-stage build (optimized for performance)
3. **.dockerignore** — Excludes unnecessary files from Docker context
4. **docker-compose.yml** — Local development orchestration

---

## Quick Start: Local Development

### Prerequisites
- Docker Desktop installed (Windows/Mac) or Docker Engine (Linux)
- .env file configured with API keys

### Option 1: Docker Compose (Recommended)

\\\ash
# Build and start the application
docker-compose up --build

# Application will be available at http://localhost:8000
\\\

**Features:**
- Automatic port mapping (8000)
- Volume mounts for data persistence
- Built-in health checks
- Network isolation
- Easy env variable management

### Option 2: Manual Docker Build

\\\ash
# Build the image
docker build -t coextend-prospect-intelligence:latest .

# Run container
docker run -d \
  --name coextend-app \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  coextend-prospect-intelligence:latest

# Access at http://localhost:8000
\\\

---

## Development Workflow

### Rebuild after code changes
\\\ash
docker-compose up --build
\\\

### View logs
\\\ash
docker-compose logs -f app
\\\

### Run tests inside container
\\\ash
docker-compose exec app pytest
\\\

### Access container shell
\\\ash
docker-compose exec app bash
\\\

### Ingest knowledge base (inside container)
\\\ash
docker-compose exec app curl -X POST http://localhost:8000/api/v1/knowledge/ingest
\\\

### Clean up
\\\ash
docker-compose down        # Stop and remove containers
docker-compose down -v     # Also remove volumes (careful: deletes data!)
\\\

---

## Production Deployment

### Build for Production
\\\ash
docker build -f Dockerfile.prod -t coextend-prospect-intelligence:prod .
\\\

### Push to Registry (Docker Hub)
\\\ash
# Tag the image
docker tag coextend-prospect-intelligence:prod username/coextend-prospect-intelligence:latest

# Push to Docker Hub
docker push username/coextend-prospect-intelligence:latest
\\\

### Environment Variables

Create a .env.prod file:
\\\
OPENAI_API_KEY=sk-...
SEARCH_API_KEY=...
DATABASE_URL=sqlite:///./data/prospect_intelligence.db
CHROMA_DB_PATH=./data/chroma_db
\\\

### Deploy to Cloud Platforms

#### Railway.app
1. Connect GitHub repo
2. Create new service → Docker image
3. Add environment variables in dashboard
4. Deploy (auto-deploys from git commits)

\\\ash
# Or deploy from CLI:
railway login
railway link
railway up
\\\

#### Render.com
1. Create new Web Service
2. Connect GitHub repo
3. Select Docker environment
4. Set environment variables
5. Deploy

#### AWS Lightsail (with Docker)
\\\ash
# SSH into instance
ssh -i key.pem ubuntu@instance-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Pull and run image
docker pull username/coextend-prospect-intelligence:latest
docker run -d \
  -p 80:8000 \
  --env-file /path/to/.env.prod \
  -v /var/data/coextend:/app/data \
  username/coextend-prospect-intelligence:latest
\\\

#### Docker Swarm (Multi-container Orchestration)
\\\ash
docker service create \
  --name coextend \
  --publish 8000:8000 \
  --replicas 2 \
  --env-file .env.prod \
  --mount type=bind,source=/var/data/coextend,destination=/app/data \
  username/coextend-prospect-intelligence:latest
\\\

---

## Health Checks

### Docker built-in health check
\\\ash
# Check container health status
docker ps

# Output shows STATUS like: Up 2 minutes (healthy)
\\\

### Manual health check
\\\ash
curl http://localhost:8000/api/v1/health
# Expected response: {"status": "ok"}
\\\

### Monitor with docker stats
\\\ash
docker stats coextend-app
\\\

---

## Image Optimization

### Size Comparison
- **Development (Dockerfile)**: ~850 MB
- **Production (Dockerfile.prod)**: ~750 MB (with venv optimization)

### What's included
- Python 3.11 slim base image
- FastAPI + Uvicorn
- SQLAlchemy + aiosqlite
- ChromaDB
- PDF extraction (pypdf)
- LLM clients (Google GenAI)
- Web search client (Tavily)
- HTTP client + retry logic (httpx + tenacity)

### Reduced in build
- Excluded: .git, __pycache__, .pytest_cache, build artifacts
- Uses multi-stage build to minimize final image size
- Strips development dependencies in production build

---

## Volume Management

### Data Persistence
\\\ash
# Data lives in ./data/ directory:
./data/prospect_intelligence.db       # SQLite database
./data/knowledge_base/                # PDF knowledge base
./data/exports/                       # CRM exports (JSON/CSV)
./data/chroma_db/                     # ChromaDB vector store
\\\

### Backup data
\\\ash
# Create backup tarball
tar -czf coextend-data-backup.tar.gz data/

# Restore from backup
tar -xzf coextend-data-backup.tar.gz
\\\

### Persistent volumes (production)
\\\ash
# Create named volume
docker volume create coextend-data

# Use in docker run
docker run -d \
  -v coextend-data:/app/data \
  coextend-prospect-intelligence:prod
\\\

---

## Logging

### View container logs
\\\ash
docker-compose logs app                 # Last 100 lines
docker-compose logs -f app              # Follow (tail -f)
docker-compose logs app --tail 50       # Last 50 lines
\\\

### Log rotation (production)
\\\ash
# Edit /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "10"
  }
}

# Restart Docker daemon
sudo systemctl restart docker
\\\

---

## Troubleshooting

### Container exits immediately
\\\ash
docker logs <container_id>
# Check for startup errors, missing env vars
\\\

### Health check failing
\\\ash
# Test endpoint manually
docker exec <container_id> curl http://localhost:8000/api/v1/health

# Check if API is responding
\\\

### High memory usage
\\\ash
# Monitor memory in real-time
docker stats <container_id>

# Limit memory in docker-compose.yml:
services:
  app:
    mem_limit: 1g
    memswap_limit: 2g
\\\

### Database locked errors
\\\ash
# SQLite can have concurrency issues; for production:
# 1. Switch to Postgres (see requirements in README.md)
# 2. Or use single worker process
\\\

---

## CI/CD Integration

### GitHub Actions Example
\\\yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build image
        run: docker build -f Dockerfile.prod -t coextend:latest .
      
      - name: Run tests
        run: docker run coextend:latest pytest
      
      - name: Push to Docker Hub
        run: |
          docker login -u ${{ secrets.DOCKER_USERNAME }} -p ${{ secrets.DOCKER_PASSWORD }}
          docker push coextend:latest
\\\

---

## Performance Tips

1. **Use production Dockerfile**: Multi-worker Uvicorn, better caching
2. **Enable resource limits**: Prevent runaway memory/CPU
3. **Use named volumes**: Faster I/O than bind mounts
4. **Monitor metrics**: Use docker stats, Prometheus, or cloud provider dashboard
5. **Load balancing**: Put Nginx in front for multiple containers
6. **Scale horizontally**: Run multiple container replicas with Docker Swarm or Kubernetes

---

## Next Steps

1. ✅ Docker images ready
2. Choose cloud platform (Railway / Render / AWS / Azure)
3. Set up CI/CD pipeline (GitHub Actions)
4. Configure monitoring & alerting
5. Set up backups for SQLite database → Postgres
6. Enable API authentication before production

