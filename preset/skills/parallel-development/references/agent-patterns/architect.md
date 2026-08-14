# Architect Agent Code Patterns

## ADR Template

```markdown
# ADR-XXX: [Decision Title]

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
[What is the issue that we're seeing that is motivating this decision or change?]

## Decision
[What is the change that we're proposing and/or doing?]

## Consequences
- [Positive consequence 1]
- [Positive consequence 2]
- [Negative consequence 1]

## Alternatives Considered
1. [Alternative 1]
   - Pros: [advantages]
   - Cons: [disadvantages]

## Related Decisions
- [ADR-XXX]: [Related decision]
```

## Example ADRs

### ADR-001: Use OpenResty as Core Platform

- Status: Accepted
- Context: Need high-performance request processing with dynamic configuration
- Decision: Use OpenResty (Nginx + LuaJIT) for core request processing
- Consequences: High performance, dynamic config, Lua ecosystem, Lua learning curve

### ADR-002: Dual Dashboard Architecture

- Status: Accepted
- Context: Need modern UI while maintaining backward compatibility
- Decision: Maintain both legacy (Vue/jQuery) and modern (React) dashboards
- Consequences: Gradual migration, no breaking changes, maintenance burden

## Architecture Documentation Format

```markdown
# Architecture Document: [Component/Feature]

## Overview
[High-level description]

## Goals
- [Goal 1]
- [Goal 2]

## Non-Functional Requirements
- Performance: [Specific metrics]
- Scalability: [Expected load, growth]
- Availability: [Uptime target]
- Security: [Security requirements]
- Maintainability: [Design considerations]

## Architecture

### System Diagram
[ASCII or mermaid diagram]

### Components
| Component | Responsibility | Technology | Interfaces |
| --- | --- | --- | --- |
| [Name] | [Description] | [Tech stack] | [APIs/protocols] |

### Data Flow
[Sequence diagram or description]

### Technology Choices
| Decision | Rationale | Alternatives |
| --- | --- | --- |
| [Tech] | [Why chosen] | [What else was considered] |

## Interfaces

### API Contracts
[Endpoint definitions, request/response formats]

### Data Models
[Schema definitions, relationships]

## Deployment
[Deployment architecture, infrastructure]

## Considerations
- Scalability: [How to scale]
- Reliability: [Failure modes, recovery]
- Security: [Security considerations]
- Monitoring: [What to monitor]

## Future Considerations
[Potential improvements, evolution paths]
```

## Design Patterns

### Request Processing Patterns

- **Chain of Responsibility** - Nginx phase handlers
- **Strategy Pattern** - Matcher types
- **Observer Pattern** - Config updates

### Dashboard Patterns

- **Container/Presenter Pattern** - React components
- **Repository Pattern** - Data access
- **Command Pattern** - API actions

### Configuration Patterns

- **Singleton Pattern** - Shared dictionaries
- **Factory Pattern** - Module creation
- **Builder Pattern** - Complex config

## VeryNginx/DianNginx Architecture Reference

### Overall Architecture: Module Monolith with Web Dashboard

- Core: OpenResty (Nginx + LuaJIT)
- Dashboard: React SPA (separate deployment)
- Storage: File-based JSON + Shared Memory

### Request Processing Pipeline

```text
Client Request
→ Nginx Rewrite Phase (Lua: Config, Redirects, URI Rewrite)
→ Nginx Access Phase (Lua: Stats, Browser Verify, Rate Limit, Routing)
→ Nginx Content Phase (Backend Proxy / Static / API)
→ Nginx Log Phase (Lua: Status Logging, Summary Collection)
```

### Component Architecture

```text
Web Dashboard (React)
    ↓
API Layer (/verynginx/config/*, /verynginx/status/*)
    ↓
Lua Core Modules (Security, Routing, Stats, Config)
    ↓
OpenResty (Nginx + LuaJIT)
    ↓
Backend Upstreams / Files
```
