# TOJI Platform Deployment Guide

This document describes how to deploy the TOJI platform and its dashboard observability API using Docker Compose.

## Prerequisites
- **Docker** and **Docker Compose** installed on the deployment machine/VPS.

## Quickstart Service Control

1. **Start all services**:
   ```bash
   docker-compose up -d --build
   ```

2. **Verify services running**:
   ```bash
   docker-compose ps
   ```

3. **Monitor real-time logs**:
   ```bash
   docker-compose logs -f
   ```

4. **Shutdown all services gracefully**:
   ```bash
   docker-compose down
   ```

## Production Configurations
- Edit the database passwords and host settings directly inside `.env` or `docker-compose.yml`.
- The dashboard REST and WebSocket APIs run on port `8000`.
