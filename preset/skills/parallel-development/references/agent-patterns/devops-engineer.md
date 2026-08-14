# DevOps Code Patterns

CI/CD pipeline and infrastructure patterns.

## Dockerfiles

### Multi-stage Build

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Runtime
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./
RUN npm ci --production
EXPOSE 3000
CMD ["node", "dist/index.js"]
```

### Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/health || exit 1
```

## Kubernetes

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: myapp:latest
        ports:
        - containerPort: 8080
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: app
spec:
  selector:
    app: myapp
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

## GitHub Actions

### Node.js CI/CD

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm test
      - run: npm run build

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: myapp:${{ github.sha }}
```

## Terraform

### Provider

```hcl
provider "aws" {
  region = "us-east-1"
}

resource "aws_ecr_repository" "myapp" {
  name                 = "myapp"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}
```

## Monitoring

### Prometheus Metrics

```yaml
scrape_configs:
  - job_name: 'myapp'
    metrics_path: /metrics
    static_configs:
      - targets: ['localhost:8080']
```

### Log Format

```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "info",
  "method": "GET",
  "path": "/api/status",
  "status": 200,
  "duration_ms": 45
}
```

## Deployment Checklist

**Pre-Deployment:**

- [ ] All tests passing
- [ ] Code reviewed
- [ ] Migration scripts prepared
- [ ] Rollback plan documented

**Deployment:**

- [ ] Backup current version
- [ ] Deploy (blue-green)
- [ ] Health checks passing

**Post-Deployment:**

- [ ] Verify functionality
- [ ] Check error logs
- [ ] Monitor performance

## See Also

- [memory-protocol.md](../skills/parallel-dev/references/memory-protocol.md)
