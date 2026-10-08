# Scan semantics

## Evidence and names

- `variables`: literal uppercase placeholder keys (`${DB_HOST}`) and literal
  `System.getenv("DB_HOST")` names, plus uppercase keys from `.getProperty`-style
  lookups (heuristic receiver). Uppercase property/placeholder syntax is an env-shaped
  reference, not proof of which Spring PropertySource supplies it. JVM-only
  `System.getProperty` keys stay in `properties`, not the environment checklist.
- `properties`: YAML/properties declarations, dotted/lowercase placeholder refs,
  Java property lookups and config-class binding candidates. Consumers are linked
  through static aliases, including nested fallback placeholders. A source default
  is recorded only as present/absent; no default values are output.
  Property links are the union of source references across scanned modules/documents,
  not a precedence-resolved or module-isolated runtime graph. Narrow the root to a
  service/module for a service-specific inventory.
- `inferred_variables`: Spring Boot override candidates for known properties:
  replace dots with underscores, **remove hyphens**, uppercase. For example,
  `my.service.connect-timeout` → `MY_SERVICE_CONNECTTIMEOUT`, not
  `MY_SERVICE_CONNECT_TIMEOUT`. Underscore/uppercase references remain explicit;
  indexed/list/map keys are withheld from inference because their binding depends
  on collection structure. System JVM property lookups do not imply Spring binding.
- `no_default`: no colon fallback at that occurrence. A fallback can contain another
  placeholder, and the result can still require an external value. No runtime
  required/optional claim is made.

## Supported source

- `application*.yaml/yml/properties` and `bootstrap*.yaml/yml/properties`, across
  modules. YAML multi-document config, mappings, sequences, anchors/merge keys,
  quoted scalars and nested placeholder defaults. Java-properties continuations,
  escaped separators and Unicode escapes. Config profile conditions are not evaluated.
- Java comments are ignored; string tokens are decoded. `@Value`, literal
  `System.getenv/getProperty`, and receiver `.getProperty/getRequiredProperty/
  containsProperty` calls are scanned. The receiver's type is not resolved, so
  non-System lookup calls carry heuristic confidence. Dynamic lookup arguments
  produce warnings rather than invented names.
- Literal `@ConfigurationProperties` prefixes on classes/records and factory
  methods whose return class is available locally. Direct fields, Java record
  components and local nested/custom class fields produce heuristic binding keys.
  This is candidate discovery, not verification of setters, constructor selection,
  bean registration or actual getter calls. Private/final fields are candidates;
  static fields are excluded. Same-simple-name types are ambiguous and warned.
  Lists/maps, inherited fields, external classes, complex annotated fields and
  annotation aliases may need manual tracing. Collection entry expansion is not
  attempted. Method bodies and their local variables are not config fields.

## Coverage boundaries

No full Java/Spring semantic compiler or runtime PropertySource precedence.
No SpEL evaluation, computed variable names, dependency-JAR scanning, Kotlin,
setter-only bindings, Lombok-generated accessor analysis, imports from Vault/config
servers, active-profile selection or deployment comparison. Configuration imports
produce warnings; add local imported files with `--config` to inventory them without
claiming runtime resolution. Getter/accessor call sites are not traced.

Malformed YAML, dynamic placeholders/lookups, unsupported binding shapes and file
read failures yield structured warnings and partial-coverage exit status `1`.
Warnings contain a code/location, not source text or parser exception messages;
those can include secrets. Unsupported Java patterns may escape this lightweight
lexer, so even zero warnings means only completion within the documented scope.

All source values, snippets, annotation defaults and environment values are omitted
from every output format. Key names and paths themselves can be sensitive; keep
real-service reports private. Names-only `.env` output is a checklist, not a runnable
config: it prints comments plus names, never `KEY=` that could override defaults.
