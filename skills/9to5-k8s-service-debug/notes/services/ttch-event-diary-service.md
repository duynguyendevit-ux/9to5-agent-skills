# ttch-event-diary-service

- Namespaces: `dev-c7`
- Repo: `~/Documents/C777777777777/services/ttch-event-diary-service` (registry `repo_confidence: remote`; duplicate checkout `~/Documents/ttdvkh-event-diary-service` exists and is a separate repo with a misleading `rootProject.name`)
- Type: `rest` + `grpc` + persistence
- Port: `TODO(unverified)`

## Trigger

Inbound gRPC from sibling services plus REST APIs. gRPC entry point is `EventDiaryServiceImpl` under `controller/grpc`; REST under `controller/v1` (`EventDiaryApi`, `ContentTemplateApi`).

## Inputs

| Source | Detail |
|--------|--------|
| gRPC | `EventDiaryService` — includes `saveList` |
| REST | `EventDiaryApi`, `ContentTemplateApi` |
| Cache | `CacheContentTemplate` (repository/cache) |
| Shared enum | `EnumEventDiarySource` lives in `internal-service-communication-spring-boot-starter` — changing it affects other services |

## Outputs

| Target | Detail |
|--------|--------|
| Oracle tables | `event_diaries`; `config_diary_content_templates` (diary content templates, seeded with explicit IDs) |
| Redis | `TODO(unverified)` — cache layer present |
| Kafka | `TODO(unverified)` — uses the outbox pattern; confirm the producer/topic |

## Layering

`controller/grpc` -> `service/*UseCaseService` -> `service/*CommandService` -> `repository/database` (MyBatis mapper) + `repository/cache`.

- `EventDiaryUseCaseService`, `EventDiaryCommandService`, `EventDiaryServiceImpl` are the classes normally touched together.
- A repo checkstyle rule requires every public method on `*UseCaseService` / `*UseCaseServiceImpl` to be `@Transactional`. A missing annotation fails `./gradlew checkstyleMain` with `[UseCaseService]`.
- gRPC DTO mapping sits in `controller/grpc/model/EventDiaryModelMapper`.
- Diary content templates are configured in `config_diary_content_templates`; `ContentTemplate` / `DiaryContentTemplateConfigQueryService` hold template constants.

## Debug

```bash
kerror ttch-event-diary-service dev-c7
kfind  ttch-event-diary-service '<method or event id>' dev-c7
ksql   ttch-event-diary-service dev-c7
```

## Failure modes

| Symptom | Log signature | Likely cause |
|---------|---------------|--------------|
| gRPC call fails | exception in `EventDiaryServiceImpl` | contract drift with the caller, or a mapper mismatch |
| Diary saved but not visible | insert logged, no follow-up row created | outbox not flushed, or template rows missing in `config_diary_content_templates` |
| `saveList` partially applies | one insert fails mid-batch | missing `@Transactional`, prior writes committed |

## Open questions

- `TODO(unverified)` Kafka topic(s) and outbox table name.
- `TODO(unverified)` Redis key patterns.
- `TODO(unverified)` service port.
