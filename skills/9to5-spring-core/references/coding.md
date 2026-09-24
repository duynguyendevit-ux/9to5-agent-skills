# Cách code với core

## Layers và package

```text
tech.app
├── Application
├── controller.v2     # HTTP adapters; V2API marker
├── usecase           # @Service *UseCaseService, transaction boundary
├── model             # request/response records; no JPA entity in API response
├── repository.database
│   ├── entity        # scanned JPA entities
│   └── repository    # scanned Spring Data interfaces
└── configuration     # only application-owned configuration
```

`tech.app` is a template convention chosen to fit the starter's scan paths, not the
only permitted package. Broad `@ComponentScan("tech")` is unnecessary. Importing
AppConfiguration explicitly is normally unnecessary because the starter registers it.
Custom feature roots need explicit component, entity and repository scanning with no
duplicate registration.

## Controller → use-case → repository

Pattern for an existing table/entity named ExampleEntity (adapt types to actual schema):

```java
package tech.app.repository.database.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import tech.app.repository.database.entity.ExampleEntity;

public interface ExampleRepository extends JpaRepository<ExampleEntity, Long> {
}
```

```java
package tech.app.usecase;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.app.repository.database.entity.ExampleEntity;
import tech.app.repository.database.repository.ExampleRepository;
import tech.outsource.core.configurations.controller.exceptions.ResourceNotFoundException;

@Service
public class ExampleUseCaseService {
    private final ExampleRepository repository;

    public ExampleUseCaseService(ExampleRepository repository) {
        this.repository = repository;
    }

    @Transactional(readOnly = true)
    public ExampleEntity find(long id) {
        return repository.findById(id).orElseThrow(ResourceNotFoundException::new);
    }

    @Transactional
    public ExampleEntity save(ExampleEntity entity) {
        return repository.save(entity);
    }
}
```

This is an integration fragment, not generated runnable CRUD: it assumes a real entity
and schema already exist. Map to a response DTO inside the transaction if lazy fields
are needed; do not serialize ExampleEntity directly from the controller. The delivered
init template uses a schema-independent core-info endpoint instead.

## Entity/audit choice

- Choose `extends Auditable` only if audit user columns are numeric and principal names
  fit Integer; the listener calls Integer.parseInt. UUID/username subjects require
  StringAuditable or an application-specific mapping consistent with the DB schema.
- Both base classes add created_program, created_by, created_at, updated_by, updated_at.
  Verify column existence/types before extending them. Do not auto-generate schema with ddl-auto=update.
- Existing DDL uses quoted identifiers in many services; globally_quoted_identifiers
  changes case behavior. Match @Table/@Column to actual migration names.
- Select PK strategy via `9to5-id-design`. Do not infer IDENTITY from a NUMBER column.
- Constructor injection in services; Lombok is optional and requires the application's
  own annotation processor. MapStruct also needs its processor in the consuming build.

## V2 response and error contracts

```java
import tech.outsource.core.model.v2.ValueResponse;
// In the V2API controller:
// return ValueResponse.of(responseDto);
```

ValueResponse.of(dto) -> status/message/value. ListResponse.of(list) -> status/message/data.
PageImplResponse.of(page,current) also emits meta and legacy pagination fields. Do not
switch wrapper families in a stable API without reviewing the response contract.

ApplicationException takes `(ErrorCodes, String message, HttpStatus)`; ErrorCodes
requires getCode()/getMessage(). ResourceNotFoundException has a no-argument constructor.
V2 advice reports its application status in JSON while returning HTTP 200 for the main
error handlers. Verify HTTP and JSON separately; security filter errors do not necessarily
use the MVC advice contract. ValueResponse.ofEmpty() alone does not set HTTP 404.

## Paging

```java
import org.springframework.data.domain.Sort;
import tech.outsource.core.model.common.PageRequestCustom;
// Validate requestedPage >= 1 and requestedSize > 0 first.
// var request = PageRequestCustom.of(requestedPage, requestedSize, Sort.by("id"));
// var page = repository.findAll(request.pageRequest());
// return tech.outsource.core.model.v2.PageImplResponse.of(page.map(mapper::toDto), request.current());
```

Cap/whitelist sort fields; entity attribute names differ from DB column names. Binding
validation, transaction routing and response packaging are different responsibilities.

## Async and context

UseCaseServiceAspect sets createdProgram but does not clear the holder. TraceFilter
sets request context but also has no clearContext in the examined source. The template
adds an outer servlet filter that clears before/after request processing. It does not
propagate identity to @Async, schedulers or Kafka.

```java
import tech.outsource.core.process.local.LocalProcessContextHolder;
// In an application-owned worker boundary, populate an independent context as needed.
// try {
//     LocalProcessContextHolder.setContext(LocalProcessContextHolder.createEmptyContext());
//     performWork();
// } finally {
//     LocalProcessContextHolder.clearContext();
// }
```

Do not capture HttpServletRequest for later worker use, reuse another request's mutable
context, or assume @Async self-invocation creates a proxy boundary. Configure execution
capacity and rejected-task behavior for the actual workload.
