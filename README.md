# PayFlow

PayFlow is a FastAPI-based backend service for wallet and payment operations, extended with airtime and data purchase functionality. It provides user authentication, wallet funding & withdrawal (via Flutterwave), airtime purchases (via VTPASS), transaction lifecycle handling, realtime WebSocket notifications, asynchronous webhook processing through RabbitMQ workers, and Redis-backed pub/sub broadcasting.

This README documents the PayFlow project, architecture, deployment, environment variables, airtime integration, API endpoints, and testing guidance.

---

## Table of Contents

1. Overview  
2. Features  
3. Architecture  
4. Technology Stack  
5. Airtime Integration (VTPASS)  
6. Request Flows (End-to-End)  
7. Directory Structure  
8. Environment Variables  
9. API Endpoints  
10. Authentication & Security  
11. Running Locally  
12. Running with Docker / Docker Compose  
13. Templates & Webhooks  
14. Wallet & Transaction Lifecycle  
15. Asynchronous Processing (RabbitMQ Worker)  
16. Realtime Notifications (Redis + WebSockets)  
17. Logging & Monitoring  
18. Error Handling Strategy  
19. Data Models (MongoDB)  
20. Testing Strategy  
21. Performance & Scalability Notes  
22. Troubleshooting  
23. Roadmap / Future Improvements  
24. License  
25. Contributing  
26. Quick Start (TL;DR)  

---

## 1. Overview

PayFlow manages user wallets, payment integrations, and realtime transaction updates for client applications. It emphasizes:

- **Correctness**: atomic updates with MongoDB transactions  
- **Idempotency**: webhook events processed once only  
- **Concurrency safety**: wallet lock flags during balance changes  

With airtime functionality, PayFlow can perform airtime/data purchases via the VTPASS API while reconciling wallet balances.

---

## 2. Features

- User registration & authentication (JWT-based)  
- Wallet creation and balance management  
- Wallet funding via Flutterwave hosted checkout  
- Wallet withdrawal via Flutterwave transfers  
- Airtime/data purchases via VTPASS  
- Transaction lifecycle tracking (`PENDING → SUCCESS/FAILED`)  
- Asynchronous webhook ingestion through RabbitMQ  
- Realtime WebSocket notifications (room per transaction reference)  
- Redis pub/sub for distributed WebSocket broadcasting  
- Config-driven settings via Pydantic Settings  
- Graceful startup/shutdown with background tasks  

---

## 3. Architecture

```bash
Client (Browser / Mobile)
 | (HTTP / WebSocket)
FastAPI API (app.main)
 |-- Auth Routes (/auth/*)
 |-- Wallet Routes (/wallet/*)
 |-- Airtime Routes (/airtime/*)
 |-- WebSocket (/ws/wallet)
 |-- Health / Root
 |
 |---> MongoDB (users, wallets, transactions)
 |---> Flutterwave API (payments, transfers, bank verification)
 |---> VTPASS API (airtime/data purchases)
 |---> Publish webhook payloads -> RabbitMQ queue (wallet.events)
 |---> Redis (publish websocket event envelopes)
 |
RabbitMQ Worker (app.rabbitmq.worker)
 |-- Consumes wallet.events
 |-- Verifies & processes webhooks
 |-- Updates MongoDB state atomically
 |-- Publishes Redis websocket messages
 |
Redis Listener Task (startup lifespan)
 |-- Subscribes channel -> broadcasts over in-process websocket manager
 |
WebSocket Connection Manager
 |-- Maps tx_ref (room) -> set[WebSocket]

Patterns:
	•	Clear split between sync initiation and async completion
	•	Airtime purchases executed inside MongoDB transactions for balance safety
	•	Wallet lock flags prevent race conditions

⸻

4. Technology Stack
	•	Language: Python 3.11
	•	Framework: FastAPI / Starlette
	•	Database: MongoDB (async via pymongo.AsyncMongoClient)
	•	Broker: RabbitMQ (aio-pika)
	•	Cache / PubSub: Redis (redis.asyncio)
	•	Payments: Flutterwave
	•	Airtime/Data: VTPASS
	•	Auth: JWT (PyJWT), OAuth2 password flow
	•	Validation: Pydantic v2 / pydantic-settings
	•	HTTP Client: HTTPX with retry wrapper
	•	Deployment: Docker + docker-compose

⸻

5. Airtime Integration (VTPASS)
	•	Vendor: VTPASS
	•	Wrapper: app.services.vtpass.VTPassClient
	•	get_services() – fetch airtime/data options
	•	buy_airtime(...) – initiate purchase
	•	process_response(...) – normalize responses

Flow (POST /airtime/purchase)
	1.	Validate request and service ID
	2.	Lock wallet (wallet.is_locked = True)
	3.	Create PENDING transaction with vendor reference
	4.	Call buy_airtime(...)
	5.	On success → deduct balance, mark transaction SUCCESS
	6.	On failure → mark transaction FAILED
	7.	On pending → keep PENDING, wait for requery/callback
	8.	Unlock wallet

Error Handling & Idempotency
	•	All vendor errors normalized as AirtimePurchaseError
	•	Vendor request_id used for deduplication & requery
	•	Wallet balance always updated inside a MongoDB transaction

⸻

6. Request Flows (End-to-End)

Funding (Flutterwave)
	1.	POST /wallet/fund
	2.	API: create PENDING transaction, lock wallet, request Flutterwave link
	3.	User completes checkout on Flutterwave site
	4.	Webhook → RabbitMQ queue
	5.	Worker verifies payment, updates DB, notifies via Redis

Withdrawal
	1.	POST /wallet/withdraw with bank info
	2.	API: verify account, create PENDING transaction, lock wallet
	3.	API: initiate Flutterwave transfer
	4.	Webhook processed by worker → finalizes DB state

Airtime (VTPASS)
	1.	POST /airtime/purchase
	2.	API: validate input, lock wallet, create PENDING transaction
	3.	Call VTPASS
	4.	Success/fail/pending handled → update wallet & transaction

⸻

7. Directory Structure

app/
  api/v1/
    auth.py
    wallet.py
    airtime.py
    websocket.py
  core/
    config.py
    logger.py
    security.py
  db/
    config.py
    init_db.py
    sessions.py
    crud/
      transactions.py
      wallet.py
      user.py
    models/
      user.py
      wallet.py
  exceptions/
  rabbitmq/
  services/
    vtpass.py
    async_client.py
    payment_gateway.py
  templates/
  logs/

README.md
compose.yaml
Dockerfile
requirements.txt


⸻

8. Environment Variables

Variable	Description	Required	Default
MONGO_URI	MongoDB connection URI	Yes	-
MONGO_DB_NAME	Mongo database name	Yes	-
JWT_SECRET_KEY	JWT signing secret	Yes	-
JWT_ALGORITHM	Signing algorithm	No	HS256
ACCESS_TOKEN_EXPIRE_MINUTES	Token TTL	No	30
FLUTTERWAVE_SECRET_KEY	Flutterwave API secret	Yes	-
FLUTTERWAVE_WEBHOOK_HASH	Flutterwave webhook secret	Yes	-
FLUTTERWAVE_LINK_EXPIRY_MINUTES	Hosted checkout TTL	No	30
FLUTTERWAVE_REDIRECT_URL	Redirect after payment	No	/wallet/flutterwave/callback
RABBITMQ_URL	RabbitMQ connection URI	No	amqp://guest:guest@rabbitmq:5672/
REDIS_URL	Redis connection URI	No	redis://redis:6379
REDIS_CHANNEL	Pub/sub channel for WS	Yes	payflow:ws
APP_ADDRESS	Base app URL	No	http://localhost:8000/api/v1
APP_NAME	Application name	No	PayFlow
VTPASS_API_KEY	VTPASS public key	Required if airtime enabled	-
VTPASS_SECRET_KEY	VTPASS secret key	Required if airtime enabled	-
VTPASS_SANDBOX_MODE	Use sandbox mode	No	True
LOG_LEVEL	Logging level	No	INFO

Notes:
	•	VTPASS keys required only if airtime/data endpoints enabled.
	•	Never commit secrets to version control.

⸻

9. API Endpoints

Base: /api/v1

Auth
	•	POST /auth/register – Register user + wallet
	•	POST /auth/login – Get JWT token
	•	GET /auth/me – Current user profile

Wallet
	•	GET /wallet/ – Current wallet
	•	POST /wallet/toggle-activity – Enable/disable wallet
	•	POST /wallet/fund – Start funding flow
	•	GET /wallet/flutterwave/callback – Payment landing page
	•	GET /wallet/flutterwave/get-banks – List banks
	•	GET /wallet/flutterwave/verify-bank – Verify account
	•	POST /wallet/withdraw – Request withdrawal
	•	GET /wallet/withdraw/success/{tx_ref} – Success page
	•	POST /wallet/flutterwave/webhook – Webhook ingestion

Airtime
	•	GET /airtime/services – List airtime/data services
	•	POST /airtime/purchase – Purchase airtime

WebSocket
	•	WS /ws/wallet – Join with { "tx_ref": "<ref>" }

Health
	•	GET /health – Service check
	•	GET /ping-rabbitmq – Broker connectivity

⸻

10. Authentication & Security
	•	Password hashing: bcrypt (passlib)
	•	JWT with sub = user_id, signed by JWT_SECRET_KEY
	•	OAuth2 bearer dependency for protected endpoints
	•	Configurable token expiry
	•	Always run under HTTPS in production
	•	Validate all vendor responses before trust

⸻

11. Running Locally

Requirements: Python 3.11+, MongoDB, RabbitMQ, Redis

python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# Run API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run worker
python -m app.rabbitmq.worker

Docs: http://127.0.0.1:8000/api/v1/docs

⸻

12. Running with Docker / Docker Compose

docker compose up --build
docker compose logs -f api
docker compose logs -f worker
docker compose down


⸻

13. Templates & Webhooks
	•	Jinja templates for redirect pages: app/templates/wallet/
	•	Flutterwave webhooks arrive at /wallet/flutterwave/webhook → published to RabbitMQ

⸻

14. Wallet & Transaction Lifecycle

States:
	•	PENDING – Created at initiation
	•	SUCCESS – Set after worker verification
	•	FAILED – Error, mismatch, or cancellation

Concurrency:
	•	wallet.is_locked prevents parallel balance changes
	•	Updated inside MongoDB transactions

Balance changes:
	•	Funding: add after Flutterwave verification
	•	Withdrawal: subtract after confirmed transfer

⸻

15. Asynchronous Processing (RabbitMQ Worker)
	•	Consumes queue wallet.events
	•	Verifies Flutterwave webhook payloads
	•	Updates MongoDB state transactionally
	•	Publishes Redis notifications for WebSockets

Run:

python -m app.rabbitmq.worker


⸻

16. Realtime Notifications (Redis + WebSockets)

Flow:
	1.	Client connects → /ws/wallet
	2.	Sends { "tx_ref": "<ref>" }
	3.	Server maps connection to room
	4.	Worker publishes event → Redis
	5.	Listener forwards to clients in room

Use cases:
	•	Payment confirmation
	•	Withdrawal updates

⸻

17. Logging & Monitoring

Loggers in app/core/config.py:
	•	app_logger → app/logs/app.log
	•	request_logger → app/logs/request.log
	•	websocket_logger → app/logs/websocket.log
	•	rabbitmq_logger → app/logs/rabbitmq.log

Production: forward logs to aggregation system (ELK, Loki, CloudWatch).

⸻

18. Error Handling Strategy
	•	Exceptions in app/exceptions/types.py
	•	Registered handlers return structured JSON
	•	Examples: BankVerificationError, WalletError, PaymentFailedError
	•	Prevent raw stack traces from leaking

⸻

19. Data Models (MongoDB)

Collections
	•	users – unique index on email
	•	wallets – unique index on user_id
	•	transactions – reference user_id + wallet_id

Core Models
	•	UserModel: email, hashed_password, flags
	•	WalletModel: balance, currency, active/locked flags
	•	TransactionModel: type, status, reference

⸻

20. Testing Strategy

Currently no suite. Suggested:
	•	Unit: CRUD, payment handlers (mock HTTPX)
	•	Integration: funding & withdrawal with test DB
	•	WebSocket: connect + simulate Redis events
	•	Load: concurrency on wallet locks

Tools: pytest, pytest-asyncio, httpx.AsyncClient, testcontainers

⸻

21. Performance & Scalability Notes
	•	API nodes are stateless → horizontal scaling possible
	•	Redis handles WebSocket fanout
	•	MongoDB indexed queries (email, user_id)
	•	RabbitMQ buffers webhook bursts; worker pool can scale separately
	•	Async I/O prevents event loop blocking
	•	Rate limiting & circuit breakers recommended

⸻

22. Troubleshooting

Symptom	Possible Cause	Resolution
No WebSocket updates	Missing {tx_ref} join message	Ensure client sends payload after connect
Wallet stuck locked	Crash before unlock	Inspect logs; fallback unlock required
Payment stuck	Worker not running or webhook missing	Check RabbitMQ, worker logs, Flutterwave dashboard
Signature mismatch	Wrong FLUTTERWAVE_WEBHOOK_HASH	Sync env var with Flutterwave settings
401 errors	Token expired	Re-login
Duplicate transactions	Replay or race	Ensure idempotency checks
Redis broadcast fails	Wrong REDIS_CHANNEL	Match across publisher and listener


⸻

23. Roadmap / Future Improvements
	•	Retry/dead-letter queue for failed webhooks
	•	Structured JSON logs + correlation IDs
	•	Prometheus metrics (latency, queue depth)
	•	API rate limiting & abuse protection
	•	OpenAPI-generated client SDK
	•	Comprehensive tests & CI/CD pipeline
	•	Pagination & filtering on transaction history

⸻

24. License

Internal / Proprietary. Add explicit license if releasing publicly.

⸻

25. Contributing
	1.	Fork & create feature branch (feat/<name>)
	2.	Add/update tests
	3.	Ensure lint & formatting
	4.	Open PR with clear description

⸻

26. Quick Start (TL;DR)

cp .env.example .env   # Create and edit env file
docker compose up --build
start http://localhost:8000/api/v1/docs


⸻

Feel free to open issues or proposals for improvements.