# Airtime Backend API

FastAPI-based backend service providing user authentication, wallet funding & withdrawal (via Flutterwave), transaction lifecycle handling, realtime WebSocket notifications, asynchronous payment/transfer webhook processing through RabbitMQ workers, and Redis-backed pub/sub broadcasting.

---

## Table of Contents

1. Overview
2. Features
3. Architecture
4. Technology Stack
5. Request Flow (End-to-End)
6. Directory Structure
7. Environment Variables
8. Local Development (Non-Docker)
9. Running with Docker / Docker Compose
10. API Endpoints Summary
11. Authentication & Security
12. Wallet & Transaction Lifecycle
13. Webhooks (Flutterwave)
14. Asynchronous Processing (RabbitMQ Worker)
15. Realtime Notifications (Redis + WebSockets)
16. Logging
17. Error Handling Strategy
18. Data Models (MongoDB Collections)
19. Testing Strategy (Planned)
20. Performance & Scalability Notes
21. Troubleshooting
22. Roadmap / Future Improvements

---

## 1. Overview

The Airtime Backend API is a modular service designed for financial wallet operations: user registration/login, wallet management (funding, locking, withdrawals), and payment/transfer handling via Flutterwave. It integrates:

- FastAPI for the HTTP layer
- MongoDB for persistence
- RabbitMQ for decoupled webhook processing
- Redis for realtime pub/sub broadcasting to WebSocket clients
- HTTPX for external API calls (Flutterwave, potential VTPASS integration)

The system emphasizes transactional integrity (MongoDB multi-document transactions with `majority` write concern), idempotent webhook handling, and explicit concurrency control using wallet locking.

---

## 2. Features

- User registration & authentication (JWT-based)
- Secure password hashing (bcrypt via `passlib`)
- Wallet creation on user signup
- Wallet balance funding (Flutterwave hosted payment)
- Wallet withdrawal (bank transfer via Flutterwave)
- Bank account verification
- Transaction recording (pending → success/failed)
- Webhook ingestion (payments & transfers) via RabbitMQ queue worker
- Realtime client updates using WebSockets keyed by transaction reference (`tx_ref`)
- Redis pub/sub broadcast for horizontally scalable websocket delivery
- Centralized structured logging (request, app, websocket, rabbitmq)
- Graceful startup/shutdown with async lifespan
- Config-driven settings via Pydantic Settings

---

## 3. Architecture

```bash
Client (Browser / Mobile)
 | (HTTP / WebSocket)
FastAPI API (app.main)
 |-- Auth Routes (/auth/*)
 |-- Wallet Routes (/wallet/*)
 |-- WebSocket (/ws/wallet)
 |-- Health / Root
 |
 |---> MongoDB (users, wallets, transactions)
 |---> Flutterwave API (payments, transfers, bank verification)
 |---> Publish webhook payloads -> RabbitMQ queue (wallet.events)
 |---> Redis (publish websocket event envelopes)
 |
RabbitMQ Worker (app.rabbitmq.worker)
 |-- Consumes wallet.events
 |-- Processes payment/transfer webhook logic
 |-- Updates MongoDB state atomically
 |-- Publishes Redis websocket messages
 |
Redis Listener Task (startup lifespan)
 |-- Subscribes channel -> broadcasts over in-process websocket manager
 |
WebSocket Connection Manager
 |-- Maps tx_ref (room) -> set[WebSocket]
```

Key patterns:

- CQRS-like separation between synchronous initiation (fund/withdraw) and asynchronous completion (webhook/worker)
- Idempotent webhook handlers guard against duplicates
- Wallet lock flag prevents race conditions during balance-affecting operations
- Redis decouples process-specific WebSocket broadcasting (scales to multiple API instances)

---

## 4. Technology Stack

- Language: Python 3.11
- Framework: FastAPI / Starlette
- DB: MongoDB (async motor client via `pymongo.AsyncMongoClient`)
- Message Broker: RabbitMQ (`aio-pika`)
- Cache / PubSub: Redis (`redis.asyncio`)
- External Payments: Flutterwave
- Potential Airtime/Data Integration: VTPASS (credentials present; implementation TBD)
- Auth: JWT (PyJWT), OAuth2 password flow bearer tokens
- Schemas/Validation: Pydantic v2 / pydantic-settings
- HTTP Client: HTTPX (with retry wrapper)
- Deployment: Docker (python:3.11-slim) + docker-compose

---

## 5. Request Flow (End-to-End)

### Funding Flow

1. Client calls `POST /wallet/fund` with amount & currency
2. API locks wallet, creates PENDING transaction, requests Flutterwave payment link
3. Client is redirected to Flutterwave hosted checkout
4. Flutterwave sends webhook → published to RabbitMQ (`wallet.events`)
5. Worker consumes message → verifies transaction → updates transaction to SUCCESS/FAILED → updates balance → publishes Redis notification `{room: tx_ref, payload: {...}}`
6. Redis listener broadcasts to any WebSocket clients joined with that `tx_ref`

### Withdrawal Flow

1. Client calls `POST /wallet/withdraw` with bank details
2. Bank details verified (Flutterwave resolve endpoint)
3. API locks wallet, creates PENDING transaction, initiates transfer
4. Client redirected to success template (pending finalization)
5. Flutterwave transfer webhook processed similarly via worker
6. Balance deducted on SUCCESS else unlocked on failure

---

## 6. Directory Structure

```bash
app/
  api/v1/          # Route handlers (auth, wallet, websocket)
  core/            # Config, constants, logging, security
  db/              # DB config, sessions, CRUD abstractions, models, init indexes
  exceptions/      # Custom exception types & handlers
  services/        # External integrations (payment gateway, async http client, websocket manager)
 redis/         # Redis publisher/listener for websocket events
  rabbitmq/        # Publisher & consumer worker
  schemas/         # Pydantic request/response schemas
  templates/       # Jinja2 HTML templates for redirects / success pages
  logs/            # Runtime log files (ignored in prod via log aggregation ideally)
```

---

## 7. Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MONGO_URI` | Mongo connection string | Yes | - |
| `MONGO_DB_NAME` | Mongo database name | Yes | - |
| `JWT_SECRET_KEY` | Secret for signing JWT | Yes | - |
| `JWT_ALGORITHM` | JWT signing algorithm | No | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | No | 30 |
| `FLUTTERWAVE_SECRET_KEY` | Flutterwave API secret | Yes | - |
| `FLUTTERWAVE_WEBHOOK_HASH` | Shared secret used to validate webhook | Yes | - |
| `FLUTTERWAVE_LINK_EXPIRY_MINUTES` | Hosted payment link expiry | No | 30 |
| `FLUTTERWAVE_SESSION_DURATION_MINUTES` | Payment session duration | No | 30 |
| `FLUTTERWAVE_REDIRECT_URL` | Redirect path after payment | No | /wallet/flutterwave/callback |
| `RABBITMQ_URL` | Broker URL | No | amqp://guest:guest@rabbitmq:5672// |
| `REDIS_URL` | Redis instance URL | No | redis://redis:6379 |
| `REDIS_CHANNEL` | Redis pub/sub channel name | Yes | - |
| `APP_ADDRESS` | External base URL (used in redirects) | No | <http://127.0.0.1:8000/api/v1> |
| `APP_NAME` | Application name | No | Airtime Backend API |
| `VTPASS_API_KEY` | VTPASS integration key | Conditional | - |
| `VTPASS_PUBLIC_KEY` | VTPASS public key | Conditional | - |
| `VTPASS_SECRET_KEY` | VTPASS secret key | Conditional | - |
| `VTPASS_SANDBOX_MODE` | Use sandbox environment | No | True |

Create a `.env` file in the project root when running locally.

---

## 8. Local Development (Non-Docker)

Prerequisites: Python 3.11+, MongoDB, RabbitMQ, Redis services running.

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# Run API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# (Optional) Run worker for webhook processing
python -m app.rabbitmq.worker
```

Open: <http://127.0.0.1:8000/api/v1/docs>

---

## 9. Running with Docker / Docker Compose

```powershell
# Build and start all services
docker compose up --build

# Tail logs
docker compose logs -f api
docker compose logs -f worker

# Stop
docker compose down
```

Services:

- `api`: FastAPI application with live reload mounted source
- `worker`: RabbitMQ consumer processing webhooks
- `rabbitmq`: Message broker + management UI (<http://localhost:15672>)
- `redis`: Pub/Sub for websocket event fanout

---

## 10. API Endpoints Summary

Base Path: `/api/v1`

Auth:

- `POST /auth/register` – Create user & wallet (form)
- `POST /auth/login` – Obtain JWT (form)
- `GET /auth/me` – Current user profile

Wallet:

- `GET /wallet/` – Get current wallet
- `POST /wallet/toggle-activity` – Toggle `is_active`
- `POST /wallet/fund` – Initiate funding (form → returns payment link)
- `GET /wallet/flutterwave/callback` – Payment redirect landing (HTML)
- `GET /wallet/flutterwave/get-banks` – List supported banks
- `GET /wallet/flutterwave/verify-bank` – Verify account (form)
- `POST /wallet/withdraw` – Initiate withdrawal (redirect on success start)
- `GET /wallet/withdraw/success/{tx_ref}` – Static success page (HTML)
- `POST /wallet/flutterwave/webhook` – Webhook ingestion (publishes to RabbitMQ)

WebSocket:

- `WS /ws/wallet` – Client connects, sends `{ "tx_ref": "..." }` once, then awaits status updates

Health:

- `GET /health`
- `GET /ping-rabbitmq` (placeholder)

---

## 11. Authentication & Security

- OAuth2 password bearer implemented via FastAPI dependency for protected endpoints
- Passwords hashed (bcrypt)
- JWT includes `sub` = user id, signed with symmetric key
- Access token expiry configurable
- Sensitive secrets loaded from environment; never hardcode in code

---

## 12. Wallet & Transaction Lifecycle

States:

- `PENDING` → Created at initiation (fund / withdraw)
- `SUCCESS` → Set only inside worker after validation / verification
- `FAILED` → Set on error, mismatch, or cancellation

Concurrency Controls:

- `wallet.is_locked` toggled during operations to prevent race writes
- Updated inside MongoDB transactions to ensure atomic modifications

Balance Changes:

- Funding: Add amount after verifying Flutterwave pay event
- Withdrawal: Subtract amount on successful transfer completion

---

## 13. Webhooks (Flutterwave)

Ingress Flow:

1. Flutterwave posts to `/wallet/flutterwave/webhook`
2. Signature verified (`verif-hash` header matched against `FLUTTERWAVE_WEBHOOK_HASH`)
3. Payload published to RabbitMQ queue `wallet.events`
4. Worker processes and updates DB state transactionally

Idempotency:

- Duplicate events are ignored if transaction status already terminal (SUCCESS/FAILED)

---

## 14. Asynchronous Processing (RabbitMQ Worker)

File: `app/rabbitmq/worker.py`

- Consumes queue `wallet.events`
- Delegates to `FlutterWaveClient.process_webhook`
- Applies DB updates within snapshot + majority transaction
- Publishes websocket notifications via Redis

Run manually:

```powershell
python -m app.rabbitmq.worker
```

---

## 15. Realtime Notifications (Redis + WebSockets)

Pattern:

1. Client opens websocket `/ws/wallet`
2. Immediately sends: `{ "tx_ref": "<transaction_reference>" }`
3. Server registers connection in room keyed by `tx_ref`
4. Worker publishes `{room: tx_ref, payload: {...}}` to Redis
5. Background Redis listener broadcasts payload JSON to all sockets in that room

Use Cases:

- Payment status update
- Withdrawal finalization

---

## 16. Logging

Loggers configured in `app/core/config.py`:

- `app_logger` → `app/logs/app.log`
- `request_logger` → `app/logs/request.log`
- `websocket_logger` → `app/logs/websocket.log`
- `rabbitmq_logger` → `app/logs/rabbitmq.log`

Recommend: In production, forward these to a central aggregation system (e.g., ELK, Loki, CloudWatch) instead of filesystem.

---

## 17. Error Handling Strategy

Custom exception classes in `app/exceptions/types.py` with corresponding handlers registered in `app/main.py`.

- Uniform JSON structure for errors
- Domain-specific clarity (e.g., `BankVerificationError`, `WalletError`, `PaymentFailedError`)
- Prevents stack traces leaking to clients

---

## 18. Data Models (MongoDB Collections)

Collections:

- `users` → unique index on `email`
- `wallets` → unique index on `user_id`
- `transactions` → references `user_id`, `wallet_id`, includes `reference`, `status`, `type`

Core Models:

- `UserModel`: email, hashed_password, flags
- `WalletModel`: balance, currency, locked/active flags
- `TransactionModel`: status workflow & reference key for websocket room

---

## 19. Testing Strategy (Planned)

Currently no test suite is included. Recommended additions:

- Unit: CRUD layers, payment gateway handlers (mock HTTPX)
- Integration: Fund & Withdraw flows with in-memory Mongo / test containers
- Websocket: Connect & receive simulated Redis events
- Load: Concurrency around lock/unlock to validate race safety

Suggested tools: `pytest`, `pytest-asyncio`, `httpx.AsyncClient` test client, `mongomock` or ephemeral container.

---

## 20. Performance & Scalability Notes

- Stateless API nodes can horizontally scale; WebSocket sessions coordinated via Redis pub/sub
- MongoDB indexes keep lookup O(log n) for user/email & wallet by user
- RabbitMQ buffers bursty webhook traffic; worker pool can scale independently
- Async HTTP & DB calls avoid blocking event loop
- Consider rate limiting & circuit breakers for external APIs in future

---

## 21. Troubleshooting

| Symptom | Possible Cause | Resolution |
|---------|----------------|-----------|
| Websocket not receiving updates | Missing initial `{tx_ref}` message | Ensure client sends JSON payload immediately after connect |
| Wallet remains locked | Exception during funding/withdraw before unlock | Check transaction/logs; implement unlock fallback / manual toggle |
| Payment never finalizes | Webhook not received or worker down | Verify RabbitMQ queue, worker logs, webhook delivery in Flutterwave dashboard |
| Signature errors | Incorrect `FLUTTERWAVE_WEBHOOK_HASH` | Sync env var with Flutterwave settings |
| 401 on protected endpoints | Missing/expired JWT | Re-login to acquire new token |
| Duplicate transaction effects | Race or replay webhook | Handlers should guard; inspect logs for status transitions |
| Redis broadcast not working | Wrong `REDIS_CHANNEL` | Match env variable in both publisher & listener |

---

## 22. Roadmap / Future Improvements

- Add VTPASS airtime/data purchase integration
- Implement retry / dead-letter queue for failed webhooks
- Introduce structured log JSON + correlation IDs
- Add Prometheus metrics (request latency, queue depth)
- Implement API rate limiting & abuse protection
- Add OpenAPI-generated client SDK
- Add comprehensive test suite & CI pipeline
- Support pagination & filtering on transaction history endpoint (to be added)
- Add idempotency keys for client-initiated operations

---

## License

Internal / Proprietary (add explicit license if distributing publicly).

## Contributing

1. Fork & branch (`feat/<name>`)
2. Add/Update tests
3. Ensure lint & formatting (configure tools as needed)
4. Open PR with clear description

---

## Quick Start (TL;DR)

```powershell
cp .env.example .env   # (Create and edit env file)
docker compose up --build
# Open docs
start http://localhost:8000/api/v1/docs
```

---

Feel free to open issues or proposals for improvements.
