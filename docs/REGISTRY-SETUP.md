# Private Container Registry Setup Guide

## Overview

This guide covers setting up a self-hosted Harbor registry as a proxy cache for hardened container images from multiple sources (dhi.io, cgr.dev, gcr.io).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Harbor Registry                          │
│                  (registry.yourdomain.com)                  │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Proxy: DHI  │  │Proxy: Chain- │  │Proxy: GCR    │      │
│  │  dhi.io     │  │guard cgr.dev │  │Distroless    │      │
│  └─────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
         ▲                 ▲                      ▲
         │                 │                      │
    ┌────┴────┐       ┌────┴────┐          ┌─────┴─────┐
    │ GitHub  │       │Portainer│          │   Local   │
    │ Actions │       │         │          │   Docker  │
    └─────────┘       └─────────┘          └───────────┘
```

## Benefits

- **Single authentication point**: Portainer and GitHub Actions authenticate only to your Harbor instance
- **Automatic caching**: First pull fetches from upstream, subsequent pulls use cache
- **Bandwidth savings**: Reduce external registry pulls
- **Offline capability**: Cached images available even if upstream is down
- **Registry v2 API**: Full Portainer compatibility
- **Multi-registry support**: Pull from dhi.io, cgr.dev, gcr.io through single endpoint

## Prerequisites

- Docker and Docker Compose installed
- Domain name with SSL certificate (Let's Encrypt recommended)
- Minimum 4GB RAM, 20GB disk space
- Ports 80/443 available

## Installation

### 1. Install Harbor

```bash
# Download Harbor installer
cd /opt
wget https://github.com/goharbor/harbor/releases/download/v2.11.0/harbor-offline-installer-v2.11.0.tgz
tar xzvf harbor-offline-installer-v2.11.0.tgz
cd harbor

# Configure Harbor
cp harbor.yml.tmpl harbor.yml
```

### 2. Configure harbor.yml

```yaml
# Edit harbor.yml
hostname: registry.yourdomain.com

# HTTPS configuration
https:
  port: 443
  certificate: /path/to/cert.crt
  private_key: /path/to/cert.key

# Admin password
harbor_admin_password: YourSecurePassword

# Database password
database:
  password: YourDatabasePassword

# Storage location
data_volume: /data/harbor
```

### 3. Install and Start Harbor

```bash
# Install Harbor
sudo ./install.sh --with-trivy

# Harbor will be available at https://registry.yourdomain.com
# Default login: admin / YourSecurePassword
```

## Configure Proxy Cache Projects

### 1. Add Registry Endpoints

**For Docker Hardened Images (dhi.io):**

1. Go to: **Administration → Registries → New Endpoint**
2. Configure:
   - **Provider**: Docker Registry
   - **Name**: dhi-registry
   - **Endpoint URL**: https://dhi.io
   - **Access ID**: Your Docker Hub username
   - **Access Secret**: Your Docker Hub password or PAT

**For Chainguard (cgr.dev):**

1. Go to: **Administration → Registries → New Endpoint**
2. Configure:
   - **Provider**: Docker Registry
   - **Name**: chainguard-registry
   - **Endpoint URL**: https://cgr.dev
   - **Access ID**: Your Chainguard username (from `chainctl auth`)
   - **Access Secret**: Your Chainguard password

**For Google Distroless (gcr.io):**

1. Go to: **Administration → Registries → New Endpoint**
2. Configure:
   - **Provider**: Google GCR
   - **Name**: gcr-registry
   - **Endpoint URL**: https://gcr.io
   - **Access ID**: (optional, public images)
   - **Access Secret**: (optional)

### 2. Create Proxy Cache Projects

**DHI Proxy:**

1. Go to: **Projects → New Project**
2. Configure:
   - **Project Name**: dhi
   - **Access Level**: Public or Private
   - **Proxy Cache**: ✅ Enable
   - **Registry**: dhi-registry

**Chainguard Proxy:**

1. Go to: **Projects → New Project**
2. Configure:
   - **Project Name**: chainguard
   - **Access Level**: Public or Private
   - **Proxy Cache**: ✅ Enable
   - **Registry**: chainguard-registry

**Distroless Proxy:**

1. Go to: **Projects → New Project**
2. Configure:
   - **Project Name**: distroless
   - **Access Level**: Public or Private
   - **Proxy Cache**: ✅ Enable
   - **Registry**: gcr-registry

## Usage

### Dockerfile Examples

```dockerfile
# Using DHI images via Harbor proxy
FROM registry.yourdomain.com/dhi/python:3.12-debian13

# Using Chainguard images via Harbor proxy
FROM registry.yourdomain.com/chainguard/python:latest

# Using Google Distroless images via Harbor proxy
FROM registry.yourdomain.com/distroless/python3-debian12
```

### Docker Pull

```bash
# Login to your Harbor registry
docker login registry.yourdomain.com

# Pull images (Harbor will fetch from upstream if not cached)
docker pull registry.yourdomain.com/dhi/python:3.12-debian13
docker pull registry.yourdomain.com/chainguard/node:latest
docker pull registry.yourdomain.com/distroless/static:latest
```

### Portainer Configuration

1. Go to: **Registries → Add Registry**
2. Configure:
   - **Registry**: Custom Registry
   - **Name**: Harbor Internal Registry
   - **Registry URL**: https://registry.yourdomain.com
   - **Username**: admin (or create dedicated user)
   - **Password**: Your Harbor password

## GitHub Actions Integration

### Create Harbor Robot Account

1. Go to: **Projects → dhi → Robot Accounts → New Robot Account**
2. Configure:
   - **Name**: github-actions
   - **Expiration**: Never
   - **Permissions**: Pull, Push (if needed)
3. Copy the **Name** and **Token**

### Add GitHub Secrets

```bash
# Add to your GitHub repository or organization secrets
HARBOR_REGISTRY: registry.yourdomain.com
HARBOR_USERNAME: robot$github-actions
HARBOR_PASSWORD: <token from above>
```

### Update Workflows

Instead of the current DHI-specific approach, use generic Harbor registry:

```yaml
# .github/workflows/python-docker.yml
- name: Login to Harbor Registry
  uses: docker/login-action@v3
  with:
    registry: ${{ secrets.HARBOR_REGISTRY }}
    username: ${{ secrets.HARBOR_USERNAME }}
    password: ${{ secrets.HARBOR_PASSWORD }}
```

## Monitoring

### Check Cache Status

1. Go to: **Projects → dhi** (or chainguard/distroless)
2. View **Repositories** to see cached images
3. Check **Logs** for pull-through activity

### Disk Usage

```bash
# Monitor Harbor storage
df -h /data/harbor

# Clean up old images (optional)
# Go to: Administration → Garbage Collection → Run Now
```

## Backup and Maintenance

### Backup Harbor

```bash
# Backup Harbor configuration and data
cd /opt/harbor
docker-compose stop
tar czf harbor-backup-$(date +%Y%m%d).tar.gz /data/harbor
docker-compose start
```

### Update Harbor

```bash
# Download new version
cd /opt
wget https://github.com/goharbor/harbor/releases/download/v2.12.0/harbor-offline-installer-v2.12.0.tgz
tar xzvf harbor-offline-installer-v2.12.0.tgz

# Backup and upgrade
cd harbor
docker-compose down
./install.sh --with-trivy
```

## Troubleshooting

### Image Pull Fails

1. Check endpoint connectivity:
   ```bash
   # Test from Harbor server
   curl -I https://dhi.io/v2/
   ```

2. Verify credentials:
   - Go to: **Administration → Registries**
   - Click **Test Connection** on each endpoint

3. Check Harbor logs:
   ```bash
   cd /opt/harbor
   docker-compose logs -f core
   ```

### Portainer Connection Issues

1. Ensure Harbor is accessible from Portainer host:
   ```bash
   curl -k https://registry.yourdomain.com/v2/
   ```

2. Verify SSL certificate is valid

3. Check Portainer logs for authentication errors

## Security Considerations

- **Use HTTPS**: Always use SSL/TLS certificates
- **RBAC**: Create separate robot accounts for different services
- **Network**: Restrict Harbor access to known IPs if possible
- **Scanning**: Enable Trivy vulnerability scanning in Harbor
- **Secrets**: Rotate robot account tokens regularly

## References

- [Harbor Documentation](https://goharbor.io/docs/)
- [Harbor Proxy Cache Guide](https://goharbor.io/docs/2.1.0/administration/configure-proxy-cache/)
- [Chainguard + Harbor Integration](https://edu.chainguard.dev/chainguard/chainguard-images/chainguard-registry/pull-through-guides/harbor/)
- [Docker Registry v2 API](https://docs.docker.com/registry/spec/api/)
