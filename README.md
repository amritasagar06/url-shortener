Zenith Links: Decoupled URL Shortener with Deep Telemetry

Zenith Links is a production-grade, highly optimized, asynchronous URL shortener built with FastAPI, PostgreSQL, Redis and Nginx engineered for sub-millisecond redirection and high-scale traffic environments.

The project features a beautiful, dynamic Single-Page Application (SPA) dashboard, a custom Redis-backed sliding-window rate limiter, robust Server-Side Request Forgery (SSRF) filters and non-blocking click-stream telemetry analytics.

📖 Deep-Dive System Design Article

For a detailed mathematical and architectural dissection of this system—covering estimated 5-year storage footprints, PostgreSQL indexing strategies, the birthday paradox collision retry loop and cache eviction analysis—read the full technical write-up on Substack:

👉 Read the System Design Deep Dive on Substack

🏗️ System Architecture Overview

The system is deployed using a containerized 4-tier decoupled layout:

                 +----------------------------------------+
                 |            Client Browser              |
                 +----------------------------------------+
                                     |
                                     | Port 80 (HTTP)
                                     v
                 +----------------------------------------+
                 |          Nginx Gateway/Proxy           |
                 +----------------------------------------+
                    /                                  \
     (Static Files)/                                    \(API & Redirects)
                  v                                      v
+-----------------------------+               +-----------------------------+
|    Frontend SPA Assets      |               |     FastAPI Backend App     |
| (HTML5, Tailwind, Chart.js) |               |      (Python 3.11-slim)     |
+-----------------------------+               +-----------------------------+
                                                 /                       \
                                   (Cache & RL) /                         \ (Persistent DB)
                                               v                           v
                                     +-------------------+       +-------------------+
                                     |    Redis Cache    |       |   PostgreSQL DB   |
                                     |     (Port 6379)   |       |    (Port 5432)    |
                                     +-------------------+       +-------------------+


Technical Highlights

Nginx Reverse Proxy: Acts as the public-facing gateway (Port 80). Serves frontend assets directly and routes API/Redirection traffic to the backend and completely shielding internal databases.

FastAPI Backend (async/await): Highly performant asynchronous event loop with lightweight memory overhead.

Non-blocking Telemetry Pipeline: Redirections (302 Found) execute in < 5ms by immediately delegating click logging (UA parsing, IP-hashing, and GeoIP lookup) to non-blocking BackgroundTasks.

Redis Cache-Aside Pattern: Hot links are cached with a 1-hour TTL under a volatile-lru eviction policy, preventing database lookup degradation.

SSRF Shielding: Dynamic DNS resolution filtering stops Server-Side Request Forgery by parsing target hostnames to block private IP classes (RFC 1918) and local loopbacks before database insert.

🛠️ Tech Stack & Key Libraries

Backend Engine: Python 3.11, FastAPI, Uvicorn

Database & Migration: PostgreSQL 15, SQLAlchemy Async 2.0 (asyncpg), Alembic

Caching & Counters: Redis 7, redis-py (async pipeline)

Analytics & Telemetry: ua-parser (User-Agent detection), httpx (async GeoIP query client)

Testing: pytest, pytest-asyncio

🚀 Quickstart Guide

1. Prerequisites

Ensure you have Docker and Docker Compose installed on your machine.

2. Environment Setup

Clone the repository and set up your local environment file:

git clone [https://github.com/amritasagar06/url-shortener.git](https://github.com/amritasagar06/url-shortener.git)
cd url-shortener
cp .env.example .env


Update the variables inside .env to match your local production secrets.

3. Spin up the Containers

Run Docker Compose to pull, build and start the unified service layers in detached mode:

docker compose up --build -d


4. Run Database Schema Migrations

Bootstrap the database tables using Alembic:

docker compose exec api alembic upgrade head


The application is now live!

Dashboard: Navigate to http://localhost

API Documentation (Swagger UI): Navigate to http://localhost/docs

🧪 Automated Testing

I maintained a high-quality test suite using pytest-asyncio with isolated transactional rollbacks to test redirects, SSRF blocking, rate limits and analytics tracking.

To execute the test suite inside the active application container:

docker compose exec api python -m pytest tests/


🔒 Security Configuration

Sliding-Window Rate Limiter: Implemented atomically in Redis Sorted Sets (ZSET). Protects shortening writes and redirection reads from DDoS and brute force attacks.

Hash Validation Guards: Exposes security tokens using secure SHA-256 validation, ensuring raw keys are never written to disk.

SSRF Target Disallowment: Evaluates resolved DNS maps to block loopback interfaces, link-local addresses, and malicious local subnets.

📈 What I'd Do Differently at 10x Scale

Transition to Kafka: Move FastAPI's local BackgroundTasks click processor to an external distributed queue (like Apache Kafka) to guarantee delivery and decouple high-throughput writes.

CQRS Architecture (Go/Rust): Separate the read (redirects) API and write (URL creation) API into dedicated microservices. A thin Go/Rust microservice would handle cached redirection queries at massive scale.

Columnar Database Storage: Route analytics records directly to ClickHouse instead of PostgreSQL to keep high-volume logs compressed and enable sub-second aggregations on billions of rows.
