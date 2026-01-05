# Product Requirements Document (PRD): Optimization of Jobs Page Loading in i2v Bulk Image/Video Generator

## 1. Document Overview
### 1.1 Purpose
This PRD outlines the requirements for optimizing the loading performance of the Jobs page in the i2v project (https://github.com/YallaPapi/i2v), a full-stack application for bulk image and video generation using AI models. The focus is on addressing slow page loads (e.g., 20 seconds for 20 items), even after recent additions like pagination and collapsed outputs. Improvements will target backend API efficiency, database queries, asset handling (thumbnails), frontend lazy loading/caching, and overall caching layers.

The PRD is structured to be easily parsed into development tasks, with each major section corresponding to a phase of implementation. It builds on a sequenced set of optimizations to ensure incremental progress and minimal regressions.

### 1.2 Scope
- **In Scope**: Backend API refinements, database enhancements, thumbnail integration, frontend performance tweaks, and caching mechanisms.
- **Out of Scope**: Major architectural overhauls (e.g., switching frameworks), new features unrelated to performance (e.g., additional AI models), or non-Jobs page optimizations unless directly impacting it.
- **Assumptions**: The project uses FastAPI (backend), React/TypeScript (frontend), SQLAlchemy (ORM), and SQLite/PostgreSQL (DB). Recent commits (e.g., up to 6b98878) include basic pagination and thumbnails in related areas.
- **Dependencies**: Access to the repo for code changes; potential need for tools like Redis for caching.

### 1.3 Stakeholders
- **Product Owner**: User (YallaPapi) – Focus on usability and speed.
- **Developers**: Backend/Frontend engineers – Implement optimizations.
- **Testers**: Ensure no regressions in functionality (e.g., job listing, output viewing).

### 1.4 Version History
- Version 1.0: Initial draft based on performance analysis (January 05, 2026).

## 2. Goals and Objectives
### 2.1 Business Goals
- Reduce Jobs page load time to under 1 second for initial view (20 items) and under 2 seconds for expansions.
- Improve user experience for handling 100+ pipelines without slowdowns.
- Enhance scalability for growing datasets (e.g., thousands of outputs).

### 2.2 Success Metrics
- **Performance**: Initial API response <500ms; full page render <1s (measured via browser dev tools or Lighthouse).
- **Usability**: No visible delays in expanding pipelines or hovering previews.
- **Efficiency**: Reduce JSON payload size by 80%+; minimize DB query times.
- **Test Coverage**: 90%+ for new/updated endpoints and components.

## 3. Requirements
### 3.1 Functional Requirements
These are sequenced based on dependency order for implementation.

#### Phase 1: API Payload Optimization
- Create a lightweight schema for /api/pipelines list endpoint: Include only id, name, status, created_at, output_count, and thumbnail_url (for first output).
- Use SQLAlchemy's .with_entities() to fetch only necessary columns.
- Add a new endpoint /api/pipelines/{id} for full details (including steps and outputs) on-demand.
- Update frontend (Jobs.tsx) to fetch full details only when expanding a pipeline.
- **Acceptance Criteria**: List API returns <10KB JSON for 20 items; expansion loads details asynchronously without blocking UI.

#### Phase 2: Database Query Optimization
- Add indexes via Alembic migrations for columns: status, tags, is_favorite, is_hidden.
- Set lazy=True on ORM relationships (steps, outputs) in models.py to avoid eager loading in list views.
- Use subqueries for aggregating output_count (e.g., via func.count()) instead of full lists.
- Update list_pipelines function for efficient counting.
- **Acceptance Criteria**: Query time <100ms for 100+ pipelines (test with sample data); no N+1 query issues.

#### Phase 3: Thumbnail Integration
- Extend thumbnail.py service to generate thumbnails for all pipeline outputs (150px JPEG, 60% quality).
- Include thumbnail_urls in API responses (replace full URLs in list views).
- In Jobs.tsx, use thumbnails in grids with loading='lazy'; load full images only on hover/click via preview component.
- Add migration to backfill thumbnails for existing outputs.
- **Acceptance Criteria**: Grid loads thumbnails instantly; full images deferred; reduced bandwidth usage by 70%+.

#### Phase 4: Frontend Lazy Loading and Caching
- Implement on-demand output fetching: API call to /api/pipelines/{id}/outputs on expansion.
- Integrate React Query for caching pipeline lists and outputs (instant reloads).
- Add loading skeletons/suspense for async states.
- Apply infinite scroll or batching similar to ImageLibrary.tsx.
- Add new backend endpoint for outputs if not present.
- **Acceptance Criteria**: Expansions load in <500ms; cached data persists across navigations; no flicker during loads.

#### Phase 5: Overall Caching Layer
- Introduce Redis for API caching (/api/pipelines) with keys based on filters/limit/offset; TTL=5min.
- Use aioredis in FastAPI dependencies.
- Enhance React Query for paginated results; fallback to IndexedDB if Redis unavailable.
- Add docker-compose.yml setup for Redis.
- Add middleware/dependency in main.py for cache handling.
- **Acceptance Criteria**: Repeat API calls <10ms (cache hit); frontend caches survive refreshes; scalable to 10x data volume.

### 3.2 Non-Functional Requirements
- **Performance**: Target sub-second loads; profile with tools like cProfile (backend) and React Profiler (frontend).
- **Security**: No changes to auth; ensure cached data respects user scopes if added later.
- **Compatibility**: Works on modern browsers (Chrome, Firefox); no breaking changes to existing features.
- **Accessibility**: Maintain ARIA labels in UI; lazy-loaded images have alt text.
- **Error Handling**: Graceful fallbacks (e.g., no thumbnails → placeholders); logging for cache misses.

## 4. User Stories and Tasks
This section parses the requirements into actionable tasks, grouped by phase. Each phase can be a sprint or milestone.

### Phase 1 Tasks: API Payload Optimization
- Task 1.1: Analyze and refactor pipelines.py to use lightweight schema with .with_entities().
- Task 1.2: Define new Pydantic schema in models.py or schemas.py for summary responses.
- Task 1.3: Implement /api/pipelines/{id} endpoint for full details.
- Task 1.4: Update Jobs.tsx fetch logic to use summary API and on-demand details.
- Task 1.5: Write unit tests for new endpoints; integration tests for frontend.

### Phase 2 Tasks: Database Query Optimization
- Task 2.1: Generate Alembic migration for indexes on filter columns.
- Task 2.2: Update models.py relationships to lazy=True.
- Task 2.3: Refactor list_pipelines with subqueries for counts.
- Task 2.4: Add performance tests with 100+ sample pipelines.
- Task 2.5: Run migrations and verify query speeds.

### Phase 3 Tasks: Thumbnail Integration
- Task 3.1: Extend thumbnail.py to process pipeline outputs.
- Task 3.2: Update API responses to include thumbnail_urls.
- Task 3.3: Modify Jobs.tsx to use thumbnails in grids and full URLs in previews.
- Task 3.4: Create migration for backfilling thumbnails.
- Task 3.5: Test thumbnail generation and loading performance.

### Phase 4 Tasks: Frontend Lazy Loading and Caching
- Task 4.1: Add /api/pipelines/{id}/outputs endpoint in backend.
- Task 4.2: Integrate React Query in Jobs.tsx for caching.
- Task 4.3: Implement on-demand fetching and loading states.
- Task 4.4: Add batching/infinite scroll if applicable.
- Task 4.5: UI tests for expansions and caching behavior.

### Phase 5 Tasks: Overall Caching Layer
- Task 5.1: Set up Redis in docker-compose.yml.
- Task 5.2: Integrate aioredis in FastAPI (main.py/dependencies).
- Task 5.3: Add cache logic to /api/pipelines.
- Task 5.4: Enhance React Query for pagination; add IndexedDB fallback.
- Task 5.5: Load tests for cache hits/misses and scalability.

## 5. Design and Architecture
- **Backend**: Layered (routers, services, models); use async for I/O-bound ops.
- **Frontend**: Component-based; leverage existing hooks for state management.
- **Data Flow**: User → Frontend (paginated summaries) → Backend (light queries) → DB/Cache → Thumbnails on-demand.
- **Wireframes**: (Optional) Update Jobs page to show skeletons during loads; hover previews remain.

## 6. Risks and Mitigations
- **Risk**: Breaking existing functionality – Mitigation: Comprehensive tests; staged rollouts.
- **Risk**: Thumbnail generation overhead – Mitigation: Run asynchronously; use queues if needed.
- **Risk**: Redis dependency – Mitigation: Make optional with env flags.
- **Risk**: Data migration issues – Mitigation: Backup DB before migrations.

## 7. Timeline and Milestones
- Phase 1: 1-2 days (Quick wins on payloads).
- Phase 2: 1 day (DB tweaks).
- Phase 3: 2 days (Thumbnails).
- Phase 4: 2-3 days (Frontend).
- Phase 5: 2 days (Caching).
- Total: 1-2 weeks, assuming 1-2 developers.

## 8. Appendices
- **References**: GitHub repo (https://github.com/YallaPapi/i2v); recent logs and commits from conversation.
- **Approval**: Pending user review for task parsing.
