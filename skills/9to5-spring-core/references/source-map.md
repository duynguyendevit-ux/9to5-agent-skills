# Source map — snapshot 2026-09-24

Repo: `~/workspace/microservice-spring-boot-starter`; clean checkout at
`bfa01dd7623dc48c2dabbe400a591036929ec44e` (commit dated 2025-06-16).
186 Java files found under src at inspection time. Facts below come from source,
not a running deployment. Paths are relative to the repo; Java paths below abbreviate
`src/main/java/tech/outsource/core/` as `core/`.

| Area | Source | Observed contract |
|---|---|---|
| Build | build.gradle | java-library; Boot 3.1.3; Java 17; Spring Cloud 2022.0.4; bootJar disabled; group tech.outsource, artifact microservice-spring-boot-starter |
| Registration | src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports | Registers tech.outsource.core.AppConfiguration |
| Core bootstrap | core/AppConfiguration.java | ComponentScan tech.outsource.core; PropertySource classpath:spring-init.properties |
| Defaults | src/main/resources/spring-init.properties | Oracle dialect, globally quoted identifiers, SQL logging, Hikari properties, Feign settings; application config must override inappropriate defaults |
| JPA | core/starter/database/JpaConfiguration.java | Entity/repository scan tech.outsource.repository.database and tech.app.repository.database; auditorAware bean |
| Data REST | core/starter/database/rest/configuration/JpaBaseRestConfiguration.java, SpringDataRestConfig.java | Additional base.rest scan; only annotated repositories exposed, base URL /v1/base |
| DB routing | core/starter/database/DataSourceConfig.java, RoutingDataSource.java, RoutingDataSourceInterceptor.java | Two pools from database.writer/reader, shared spring.datasource.hikari config; fallback route reader; transaction readOnly controls route |
| Use cases | core/process/local/UseCaseServiceAspect.java | @Service classes named *UseCaseService record Class.method(..) in LocalProcessContext |
| Context | core/configurations/controller/filter/TraceFilter.java | Populates property/auth/request fields for nonignored requests; no clearContext call in this filter |
| Context holder | core/process/local/LocalProcessContextHolder.java | Plain ThreadLocal, get/set/createEmptyContext/clearContext |
| Responses | core/model/ and core/model/v2/ | Separate incompatible wrapper families; inspect imports explicitly |
| V2 errors | core/configurations/controller/v2/HttpV2ExceptionHandler.java | Applies to listed v2 controller packages or V2API type; ApplicationException/general errors return HTTP 200 with status in body |
| V1 errors | core/configurations/controller/advice/HttpExceptionHandler.java | ApplicationException HTTP response uses exception.httpStatus |
| Paging | core/model/common/PageRequestCustom.java | of(page,size[,sort]); converts 1-based page to Spring 0-based; cap 500; no lower-bound normalization |
| Auditing | core/starter/database/Auditable.java, BaseEntityListener.java | Integer createdBy/updatedBy; parses principal name; anonymous becomes 0 |
| String auditing | core/starter/database/StringAuditable.java | String createdBy/updatedBy plus StringBaseEntityListener; verify inherited columns |
| Mapping | core/model/mapper/EntityMapper.java, ModelMapper.java | EntityMapper<D,E>, ModelMapper<M,D>; no ready-made application mapper bean |
| JWT | core/starter/security/JWTTokenService.java, JwtProperties.java | Decoder uses jwt.jwk-set-uri when supplied, otherwise public key; encoder still instantiates from both RSA keys |
| Security | core/starter/security/SecurityConfiguration.java | Authenticated by default; permit-all plus built-in swagger/actuator/demo/error exclusions; no blanket disable flag |
| Redis | core/starter/autoconfigure/redis/RedisConfiguration.java | Unconditional config; standalone host/port factory; supplied code does not apply password/database/SSL to the factory |
| Async | core/starter/autoconfigure/async/AsyncModuleConfiguration.java | Unconditional @EnableAsync; app.async pool-size/max-pool-size/queue-capacity/thread-name-prefix; no context TaskDecorator |

## Optional extension points

| Switch/bean | Source | Required action |
|---|---|---|
| app.module.mqtt.enabled=true | starter/integration/mqtt/MqttConfig.java | Supply broker settings; QoS default is 1 despite a nearby Exactly Once comment |
| app.module.email.enabled=true | starter/autoconfigure/email/* | Supply app.module.email.config values; do not reuse embedded credentials |
| app.grpc.client.enabled=true | starter/autoconfigure/grpc/client/GlobalClientInterceptorConfiguration.java | Enable only when client integration and headers are needed |
| app.mock.enabled=true | configurations/mock/* | Mock endpoint filter; keep false in the init template |
| bean named apiAccessEvents | configurations/web/interceptor/* | Enables API access interceptor configuration; it captures headers/payload; redact before enabling |
| LogActionService bean | request/log/action/LogActionAspect.java | Supply afterReturning and exact capitalized AfterThrowing methods; @LogAction alone is insufficient |
| RequestRateLimiterService bean | request/limiter/RateLimiterAspect.java | Enables method limiter aspect; verify service implementation and SpEL parameter names |

## Important limitations, not patterns to copy

- Source contains hardcoded artifact repository credentials, RSA keys and integration
  defaults. The skill deliberately stores only property names and environment placeholders.
- Most core configurations are component-scanned and unconditional. There is no observed
  `app.core.enabled`, `app.database.enabled` or universal switch to strip infrastructure.
  Excluding stock Boot datasource auto-config does not remove core/DataSourceConfig.
- Redis center TTL uses Duration.ofHours even though its startup log calls it minutes.
  CompositeCacheManager tries managers in order; this is not automatic L1/L2 write-through.
- Routing aspect clears rather than restores the previous nested route; transaction
  propagation and when a connection is acquired matter. Do not promise nested annotation
  changes will safely switch an active transaction to another datasource.
- JWT encoder is unconditional even with remote JWK decoding. A verification-only service
  still needs compatible key configuration at this revision, or an explicit starter change.
- `StarterConfiguration` is an interface only in this snapshot; no usage was found that
  requires every consumer to implement it. The init template does not invent that requirement.
- Build properties contain `PCI_COMMIT_SHORT_SHA`, while build.gradle reads
  `CI_COMMIT_SHORT_SHA` for a nonblank branch. Do not copy the typo into service CI.
