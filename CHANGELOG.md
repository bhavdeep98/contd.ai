# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Docker Compose setup with Postgres, Redis, MinIO, and observability stack
- Kubernetes Helm charts with environment-specific values
- Terraform modules for AWS, GCP, and Azure infrastructure
- GitHub Actions CI/CD workflows
- Performance benchmarking suite
- TypeScript, Go, and Java SDKs
- Comprehensive workflow examples (13 examples)
- Rate limiting and webhook support
- Health checks and structured logging
- SQLite and Redis storage adapters
- CLI tool for workflow management
- Context preservation module for AI agent reasoning continuity
- LLM-aware step decorator with token tracking and cost management
- Reasoning ledger for context rot prevention
- Distillation support for compressing accumulated reasoning

### Changed
- Enhanced Python SDK with improved types and decorators
- Improved tracing with OpenTelemetry integration
- Metrics labels optimized to prevent Prometheus cardinality explosion

### Fixed
- Go SDK: NewExecutionContext nil state initialization bug
- Python SDK: Engine method signature mismatches (restore, complete_workflow, maybe_snapshot)
- Python SDK: llm_step double-execution bug causing duplicate API calls
- Python API: Missing get_db function in webhook_routes
- Java SDK: Cached step returning null instead of actual result
- Java SDK: OkHttp response body leaks (now uses try-with-resources)
- Python: Stale checksums after state mutations (set_variable, update_tags)
- Go SDK: StartHeartbeat race condition with WaitGroup
- Go SDK: Jitter calculation that was a no-op (thundering herd not mitigated)
- TypeScript SDK: Double-increment of step counter breaking event replay
- TypeScript SDK: Lost 'this' binding in getSavepoints method
- Rate limiter: Memory leak from unbounded dictionary growth

### Security
- SQL injection vulnerability in workflow ID handling (journal and postgres adapter)
- Added regex validation for workflow IDs to prevent injection attacks

## [1.0.0] - 2026-01-27

### Added
- Initial release
- Core workflow engine with durable execution
- Step-level checkpointing and recovery
- Savepoint management
- PostgreSQL and S3 persistence adapters
- gRPC and REST API
- Python SDK with decorators
- Prometheus metrics integration
- OpenTelemetry tracing

### Security
- API key authentication (via hosted platform)

---

## Release Notes Format

### [Version] - YYYY-MM-DD

#### Added
- New features

#### Changed
- Changes in existing functionality

#### Deprecated
- Soon-to-be removed features

#### Removed
- Removed features

#### Fixed
- Bug fixes

#### Security
- Security fixes
