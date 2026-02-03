# 🏗️ Architecture Overview

This project follows **Clean Architecture** principles, ensuring separation of concerns, testability, and maintainability. The architecture is organized into concentric layers, where dependencies point inward toward the domain.

## Core Principles

### 1. **Dependency Rule**
Dependencies point inward. Inner layers don't know about outer layers.

```
Infrastructure → Application → Domain
     ↓              ↓            ↓
 (adapters)     (use cases)  (entities)
```

### 2. **Independence**
- **Framework Independent**: Not tied to any specific framework
- **Testable**: Business rules can be tested without UI, database, or external services
- **UI Independent**: The UI can change without changing business rules
- **Database Independent**: Business rules aren't bound to a database
- **External Agency Independent**: Business rules don't know about external services

## Architecture Layers

### 📦 Domain Layer
**Location**: `app/domain/`

The **innermost layer** containing pure business logic.

**Characteristics**:
- No external dependencies
- Pure Python objects
- Business rules and entities
- Value objects and domain services

**Contents**:
- `helpdesk_request.py` - Core helpdesk request entity
- `service_catalog.py` - Service catalog domain models
- `classification.py` - Classification result value objects

**Principles**:
- Contains **zero** infrastructure code
- No imports from outer layers
- Framework-agnostic
- Highly reusable across projects

---

### ⚙️ Application Layer
**Location**: `app/application/`

The **use cases layer** - orchestrates the flow of data to/from domain entities.

**Characteristics**:
- Defines interfaces (ports) for infrastructure
- Contains use case implementations
- Orchestrates domain objects
- Defines DTOs for data transfer

**Contents**:
- `ports/` - Abstract interfaces for infrastructure adapters
- `dto/` - Data Transfer Objects
- Use case services (classification, enrichment, reporting)

**Principles**:
- No implementation details
- Depends only on domain layer
- Defines contracts for infrastructure
- Contains business logic coordination

---

### 🔌 Infrastructure Layer
**Location**: `app/infrastructure/`

The **outermost layer** - implements interfaces defined in application layer.

**Characteristics**:
- Concrete implementations of ports
- External service integrations
- Database adapters
- HTTP clients
- File system operations

**Contents**:
- `helpdesk_client.py` - Helpdesk API adapter
- `llm_classifier.py` - LLM integration adapter
- `service_catalog_client.py` - Service catalog fetcher
- `smtp_sender.py` - Email sending adapter
- `excel_reporter.py` - Excel report generator
- `report_log_repository.py` - SQLite database adapter

**Principles**:
- Implements application ports
- Can be swapped without affecting business logic
- Contains all I/O operations
- Framework-specific code lives here

---

### 🚀 Entrypoint Layer
**Location**: `app/cmd/`

The **composition root** - wires everything together.

**Characteristics**:
- Dependency injection
- Configuration loading
- CLI interface
- Pipeline orchestration

**Contents**:
- `main.py` - CLI entrypoint
- `pipeline.py` - Dependency wiring
- `pipeline_service.py` - Pipeline orchestration

**Principles**:
- Only layer that knows about all implementations
- Creates concrete instances
- Injects dependencies
- No business logic

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Entrypoint (CLI)                                           │
│  • Loads configuration                                      │
│  • Wires dependencies                                       │
│  • Starts pipeline                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure (Adapters)                                  │
│  • Fetch helpdesk requests (HTTP)                          │
│  • Fetch service catalog (HTTP)                            │
│  • Classify via LLM (API)                                  │
│  • Generate Excel report                                    │
│  • Send email (SMTP)                                        │
│  • Log to database (SQLite)                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Application (Use Cases)                                    │
│  • Orchestrate classification                              │
│  • Enrich with SLA                                         │
│  • Generate report data                                     │
│  • Coordinate email sending                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Domain (Business Logic)                                    │
│  • HelpdeskRequest entity                                  │
│  • ServiceCatalog models                                   │
│  • Classification results                                   │
│  • Business rules                                           │
└─────────────────────────────────────────────────────────────┘
```