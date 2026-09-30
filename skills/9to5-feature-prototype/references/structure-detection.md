# Grounding a feature in the checkout

The detector reports directory names and known project metadata only; it does not interpret Spring annotations, dependency wiring, actual consumers or production settings. Use its `evidence` paths to navigate. Never infer ownership from a shared base package alone.

1. Confirm the selected root with `git rev-parse --show-toplevel`. In multi-repository workspaces, run once per likely checkout and compare ownership; never treat the workspace parent as a single repository.
2. Read `settings.gradle[.kts]` or the root `pom.xml` to establish declared modules. The detector also lists the root build and any discovered modules but does not claim that all modules are deployable services.
3. Follow a domain keyword through an existing controller/consumer/scheduler, its use-case/service, its repository and migration/event definitions. Inspect imports, method signatures, surrounding conventions and at least one existing test if present. Quote source paths (and line ranges where helpful) for existing claims.
4. For Spring projects, establish actual component/JPA scanning and shared starter version before proposing a new package. `tech.app` from `9to5-spring-core` is a template convention, not a universal property of the current service.
5. For data changes, check `admin/sql/oracle/` or the service migration directory actually used; never infer table columns or migration naming from the directory alone. For Kafka, look up producers, binding properties, topic placeholders and actual config separately.
6. If the feature crosses repositories, diagram the boundary, but only name contract owners confirmed in source; avoid claiming another service consumes an event solely because a matching topic name exists.

Run:

```bash
python3 ~/.config/opencode/skills/9to5-feature-prototype/scripts/detect_structure.py --root "$(git rev-parse --show-toplevel)"
```

The script follows no symlinked directories, reads only `settings.gradle`, `settings.gradle.kts`, and `pom.xml`, and lists bounded source paths. Avoid saving the inventory as a product artifact: the explanation should cite the actual source files you inspected, not merely generated JSON.
