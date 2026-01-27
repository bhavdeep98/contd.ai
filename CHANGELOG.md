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
- Comprehensive workflow examples (12 examples)
- Rate limiting and webhook support
- Health checks and structured logging
- SQLite and Redis storage adapters
- CLI tool for workflow management

### Changed
- Enhanced Python SDK with improved types and decorators
- Improved tracing with OpenTelemetry integration

### Fixed
- N/A

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
- API key authentication

### Security
- API key authentication
- Rate limiting
- Input validation

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
