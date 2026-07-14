# ADR 0001: Monorepo Foundation

## Status

Accepted

## Decision

Use a monorepo with `apps/api`, `apps/web`, shared package boundaries, infrastructure, docs, and CI in one repository.

## Consequences

The interview demo can be started and reviewed from a single workspace. Backend and frontend checks run independently while Docker Compose provides the integrated local environment.

