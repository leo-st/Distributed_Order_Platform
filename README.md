# 🎯 Project Philosophy

One repository.
One domain.
Iterative evolution.

### Instead of building many small unrelated projects, this project expands in phases:

- Start simple.
- Introduce failure.
- Introduce distribution.
- Introduce observability.
- Introduce chaos.
- Introduce infrastructure complexity.
- The system evolves with your engineering maturity.

# Domain

## A simplified food ordering platform.

### Why this domain?

Because it naturally contains:
- Stateful workflows
- Side effects (payments, notifications)
- External calls
- Event-driven flows
- Concurrency
- Failure scenarios
- Idempotency problems
- Race conditions

# System Evolution Roadmap

The final system will eventually include:
- API Service (FastAPI)
- Order Service
- Payment Service
- Notification Service
- PostgreSQL
- Redis
- Message Broker (Kafka or NATS)
- Observability stack (Prometheus, Grafana, OpenTelemetry)
- Kubernetes deployment

# Phase 1 — Resilient Monolith
### Architecture
Single FastAPI service.

### Endpoints:
- POST /orders
- GET /orders/{id}

### Order flow:
1. Create order
2. Simulate payment call (random latency + random failure)
3. Persist order to database

### Engineering Focus
- Timeouts
- Retry with exponential backoff
- Circuit breaker pattern
- Structured JSON logging
- Request ID correlation
### Intentional Failure Design
- 30% random payment failure rate
- Random 2–5 second latency
- Parallel request testing

### What This Phase Teaches
- Retries can create duplicate side effects
- Timeouts without idempotency are dangerous
- Logs without correlation IDs are nearly useless
- Crashes during transactions create edge cases

# Phase 2 — Event-Driven Architecture
The monolith is split into services.

### Services
- API Service
- Order Service
- Payment Service
- Notification Service
#### Message Broker
- Apache Kafka (preferred) 
- or NATS (simpler alternative)

### Event Flow
- API emits OrderPlaced
- Payment Service consumes event
- Emits PaymentCompleted
- Notification Service consumes event

### Engineering Focus
- At-least-once delivery
- Idempotent consumers
- Dead Letter Queue
- Retry with delay
- Consumer group behavior

### Intentional Chaos
- Kill consumers mid-processing
- Duplicate events
- Restart broker
- Introduce network latency

### What This Phase Teaches
- Exactly-once delivery is mostly an illusion
- Event ordering is not guaranteed
- Consumer rebalance affects real systems
- Data loss can occur in subtle ways

# Phase 3 — Observability

The system is now complex enough to require visibility.

### Add
- Prometheus
- Grafana
- OpenTelemetry distributed tracing

### Key Metrics
- Orders per second
- Payment latency (p95, p99)
- Failed events
- Queue lag
- Consumer processing time

### Planned Incidents
- Payment service slowdown
- Notification backlog growth
- Memory leak in one service

### What This Phase Teaches
- How to interpret p99 latency
- CPU-bound vs IO-bound analysis
- Backpressure detection
- Identifying bottlenecks
- Root cause isolation

# Phase 4 — Load & Chaos Testing

Now the system is stress-tested.

### Add
- Load testing (k6 or Locust)
- Rate limiting
- Backpressure strategies
- Inter-service circuit breakers

### Stress Scenarios
- 500–1000 RPS
- Kill node during load
- Network partition simulation
- Artificial latency injection

### Success Criteria
- No data loss
- Automatic recovery
- No cascading system collapse

# Phase 5 — Kubernetes Deployment

Move to real distributed infrastructure.

### Deploy Using

Kubernetes (minikube or kind locally)

### Engineering Focus
- Deployment vs StatefulSet
- Horizontal Pod Autoscaler (HPA)
- Resource limits
- Liveness vs Readiness probes
- Rolling updates

### Intentional Misconfiguration
- Insufficient CPU limits
- Pod termination during traffic
- Memory restrictions
- Autoscaling simulation

### What This Phase Teaches
- Infrastructure is part of the system
- Resource limits change runtime behavior
- Scaling is not magic
- Distributed systems fail at infrastructure boundaries