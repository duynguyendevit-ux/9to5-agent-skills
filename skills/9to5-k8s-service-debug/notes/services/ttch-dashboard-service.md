# ttch-dashboard-service

- Namespaces: `dev-c7`, `dev-c7-ttdvkh`
- Repo: `~/Documents/C777777777777/services/ttch-dashboard-service` (duplicate checkout at `~/Documents/service/ttch-dashboard-service`)
- Type: `rest` + `grpc`, includes scheduled device-state processing
- Port: `8082`

## Trigger

REST and gRPC requests from other services and portals, plus internal scheduling. Both interfaces delegate to the same use-case layer.

## Modules

Loaded conditionally via `app.module.exts`; each module has a `*ModuleLoader` implementing `Condition` and registers `@ComponentScan` / `@EnableJpaRepositories` / `@EntityScan`. Registration list: `src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`.

`statistics`, `chart`, `report`, `commondashboard`, `handle`, `event`, `device`, `customer`, `facility`, `init`, `commoncore`, `syncc7rest`, `eventcustomer`, `installation`, `diary`, `devicestate`.

## Layering (per module)

```
controller/v1            REST controllers, implement *Api, return ValueResponse / ListResponse / PageImplResponse
controller/grpc          gRPC services via @GRpcService (lognet-spring-boot-grpc), return protobuf via StreamObserver
service/*UseCaseService  business logic, implements *UseCase
repository/database      Spring Data JPA
domain                   models, DTOs, enums
```

Most endpoints expose REST and gRPC over the same use case.

## Outputs

| Target | Detail |
|--------|--------|
| Oracle | Default schema `TTDVKH_ADMIN_GEIC`; separate writer/reader datasources; Hibernate + `Oracle12cDialect`; `show-sql` enabled (disable in prod) |
| Redis | Redis Cluster |
| File storage | MinIO, enabled via `EnableFileStorageStarter` |
| Reports | Aspose.Cells / Aspose.Words from `libs/`; templates in `src/main/resources/template/` |

## Build / debug

```bash
JAVA_HOME=/home/duynk/.jdks/corretto-17.0.19 ./gradlew check
./gradlew bootRun --args='--spring.profiles.active=dev'
```

Local dependency substitution via `DEBUG_*=true` in `gradle.properties` (`DEBUG_TTCH_SERVICE_COMMON`, `DEBUG_MICROSERVICE`, `DEBUG_KAFKA`, `DEBUG_ISC`, `DEBUG_COMMON_CORE`, `DEBUG_FILESTORAGE`).

## Failure modes

| Symptom | Log signature | Likely cause |
|---------|---------------|--------------|
| Module endpoints 404 | no `ModuleLoader` init log for that module | module missing from `app.module.exts` or `AutoConfiguration.imports` |
| Report generation fails | Aspose exception | missing/corrupt template in `src/main/resources/template/` |
| Query method writes | `@Transactional(readOnly = true)` missing | checkstyle/convention violation, and reader datasource misuse |
| SQL floods logs | `show-sql` output | enabled outside local; disable for the environment |

## Debug

```bash
kerror ttch-dashboard-service dev-c7
kfind  ttch-dashboard-service '<module or use case>' dev-c7
ksql   ttch-dashboard-service dev-c7
```

## Open questions

- `TODO(unverified)` which `devicestate` scheduling drives writes to `device_state_queues` here versus in `ttch-worker-service`.
- `TODO(unverified)` Kafka topics consumed overridden by `syncc7rest` / `eventcustomer` modules.
