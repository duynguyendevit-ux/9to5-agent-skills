---
name: 9to5-container-build
description: Build and review service container images and CI release wiring for OTS services — the two-stage Dockerfile convention, internal registry base images, shared GitLab CI templates for dev-c7, CI_TAG to APP_VERSION wiring, JVM flags, and OOM dump paths inside containers. Use when adding a Dockerfile, changing builder or runtime images, adjusting JVM flags or heap in the image, or wiring a new service into the C7 CI/CD templates.
license: MIT
compatibility: Review is file-based and needs the service checkout; local image builds additionally need the internal registry credentials and a container engine. Runtime image verification happens on the cluster through 9to5-k8s-service-debug. Never hardcode registry hostnames in skills or notes.
metadata:
  version: "1.0.0"
---

# Container build — images and CI release wiring

## Example output

Illustrative review; versions and flags come from the actual Dockerfile and pipelines.

```text
Service: example-service, port 8082, group ots/apps/c7/<group>
Dockerfile: two-stage — builder <registry>/ots/infras/build/gradle:8.3.0-jdk17-alpine,
  runtime <registry>/ots/infras/images/jdk-eclipse-temurin:17.0.12_7-jre-alpine;
  CI_TAG arg wired to APP_VERSION; user ots; TZ UTC.
CI: includes shared templates java-ci.yaml + c7-cd.yaml from the env-config repo;
  CI_REGISTRY_IMAGE and CI_REGISTRY_PATH set per service.
Findings: -XX:+HeapDumpOnOutOfMemoryError is set but no HeapDumpPath — dumps land in the
  container filesystem and vanish with the pod. Either mount a dump path or accept loss;
  see 9to5-heap-triage.
Unverified: local image build not run (no container engine / registry credentials here).
```

## Scope and boundaries

- Owns the image build and the CI wiring around it: base images, stages, JVM flags baked
  into the image, tags, and the shared template includes.
- Runtime configuration values (env vars, heap sizing, feature flags) belong to
  `9to5-env-config-sync`. Do not fork flags per environment by editing the Dockerfile.
- Release records (which tag/image is released) belong to
  `9to5-release-confluence-sync`; the image tag cell there is driven by git tags, not by
  this skill.
- Base images live on the internal registry and are pulled by CI with its credentials.
  Never write registry hostnames into skills, notes or tickets — reference
  `CI_REGISTRY` / template variables instead.

## Workflow

1. **Read the current convention first.** Open an existing service Dockerfile and its
   `.gitlab-ci.yml` (any recently touched service in the same group). The shared CI
   templates in the env-config repository's `templates/ci-cd/c7/` are the source of
   truth for pipeline behaviour; the Dockerfile in the service repo is the source of
   truth for the image.
2. **Copy the two-stage shape.** Builder stage installs and compiles (`gradle build -x
   test`), runtime stage starts from a JRE image, copies the built jar, sets a non-root
   user, exposes the service port, and starts via `CMD java ... -jar`. Keep the stage
   split: builders are large, runtimes must stay small.
3. **Wire the tag.** The release pipeline passes `CI_TAG` as a build arg; the image
   records it as `APP_VERSION`. Keep the arg name and default (`dev`) consistent with
   siblings so pipelines can override uniformly.
4. **Check JVM flags deliberately.** The house set covers headless mode, timezone,
   entropy, startup heap, metaspace cap, server compiler and OOM dumps. Changing any of
   them is a runtime behaviour change: justify it in the MR and align with
   `9to5-heap-triage` if it concerns dumps.
5. **Resolve the heap story.** The image does not set `-Xmx`: the effective heap comes
   from the container memory limit and JVM ergonomics (container-aware), unless env
   config overrides it. Do not add environment-specific heap values to the Dockerfile;
   put them where the environment config lives.
6. **Fix the dump path before relying on dumps.** `-XX:+HeapDumpOnOutOfMemoryError`
   without `-XX:HeapDumpPath` writes into the container's filesystem; the dump is lost on
   restart. Candidates: a mounted volume with retention, or an explicit decision that
   dumps are not collected and incident diagnosis relies on live tooling.
7. **Wire CI minimally.** Include the shared templates; set only the per-service
   variables (`CI_REGISTRY_IMAGE`, `CI_REGISTRY_PATH`, service-specific needs). Do not
   override template jobs to "fix" a build without understanding the template; changes
   there affect every service.
8. **Verify what is verifiable here.** File-level review always; a Gradle build of the
   service if the toolchain is available; a local image build only when a container
   engine and registry access exist. Otherwise mark image build unverified and say what
   would prove it.
9. **Report** findings with proof labels and one next action.

## Rules worth enforcing

| Rule | Reason |
|---|---|
| Two stages, builder never shipped | Image size and attack surface |
| Runtime stage pinned JRE version from the internal registry | Reproducible builds without public-network dependencies |
| Non-root user in the runtime stage | Container hygiene |
| `TZ=UTC` and `-Duser.timezone=UTC` | Milestone and log timestamps stay comparable across services |
| One EXPOSE per real service port | Health checks and service discovery assume it |
| No environment-specific values baked into the image | Same artifact promotes through environments |
| Tag flows from CI, never from hand-built local images into releases | Release traceability |

## Safety

- Never print or commit registry credentials; CI variables carry them.
- Do not hardcode internal hostnames (registry, git server) in skill files or notes.
- A base-image bump is a release-affecting change: run the service's tests and record the
  old and new versions in the MR.
- Do not add `ENTRYPOINT` wrappers that mask the JVM exit code; the platform relies on it
  for restart behaviour.

## Handoffs

- Env vars, heap overrides, feature flags per environment → `9to5-env-config-sync`.
- Release pages and image-tag bookkeeping → `9to5-release-confluence-sync`.
- OOM dumps inside containers, dump analysis → `9to5-heap-triage`.
- What image actually runs in a namespace, restarts and OOMKills → `9to5-k8s-service-debug`.
- Shared-library versions inside the build → `9to5-lib-bump`.

## Stop conditions

- No sibling service to copy from and no template access: stop and say what is missing;
  do not invent a pipeline shape.
- Registry credentials unavailable for a local build: keep the change file-level and
  mark the build unverified.
- A change would alter JVM flags or dump behaviour without an incident or decision
  behind it: leave it out and flag the question in the MR instead.
