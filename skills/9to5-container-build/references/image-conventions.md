# Image and CI conventions for Platform services

Grounded in the service repositories under the Product workspace (Dockerfiles plus the
`.gitlab-ci.yml` include of the shared Product templates). Recheck a recently touched service
before copying any version number or flag.

## Dockerfile skeleton (two stages)

```dockerfile
# ---- builder ----
FROM <registry>/example/infras/build/gradle:8.3.0-jdk17-alpine AS builder

WORKDIR /app
COPY build.gradle .
COPY gradle.properties .
COPY settings.gradle .
COPY src ./src
COPY config ./config
COPY libs ./libs
COPY fonts ./fonts
RUN gradle build -x test

# ---- runtime ----
FROM <registry>/example/infras/images/jdk-eclipse-temurin:17.0.12_7-jre-alpine

ENV TZ="UTC"
ARG CI_TAG="dev"
ENV APP_VERSION $CI_TAG

WORKDIR /home/app/app
COPY --from=builder /app/build/libs/*-SNAPSHOT.jar application.jar

USER app
EXPOSE 8082

CMD java \
    -Djava.awt.headless=true \
    -Duser.timezone=UTC \
    -Djava.security.egd=file:/dev/./urandom \
    -Xms128m \
    -XX:MaxMetaspaceSize=256m \
    -server \
    -XX:+HeapDumpOnOutOfMemoryError \
    -jar /home/app/app/application.jar
```

`<registry>` is the internal registry supplied by CI configuration — never write its
hostname into notes or skill files. Copy source lists (`config`, `libs`, `fonts`) only
when the service actually has them; the font copy matters for JVM font rendering in
alpine JRE images.

## Flag table

| Flag / setting | Purpose | Caution |
|---|---|---|
| `-Djava.awt.headless=true` | No GUI stack in containers | Keep |
| `-Duser.timezone=UTC` + `ENV TZ` | Consistent timestamps | Business schedules still reference local time; document mappings |
| `-Djava.security.egd=file:/dev/./urandom` | Avoids early entropy stalls | Historic but harmless; keep for parity with siblings |
| `-Xms128m` | Small startup heap reservation | Not a heap cap; the cap comes from the container limit or env config |
| `-XX:MaxMetaspaceSize=256m` | Metaspace bound | Too low for heavy proxy/plugin stacks; raise only with evidence (heap dumps show metaspace) |
| `-server` | Server JIT | Keep |
| `-XX:+HeapDumpOnOutOfMemoryError` | Dump on OOM | Without `-XX:HeapDumpPath` the dump dies with the container |
| `USER app` | Non-root | Keep; files must be writable by that user where needed |
| `EXPOSE <port>` | Service port | Must match the Spring port and the namespace's service definition |

## CI wiring (per service)

```yaml
include:
  - project: '<devops group>/env-config'
    ref: main
    file:
      - '/templates/ci-cd/product/java-ci.yaml'
      - 'templates/ci-cd/product/product-cd.yaml'
variables:
  CI_REGISTRY_IMAGE: "<service-name>"
  CI_REGISTRY_PATH: "<group path, e.g. example/apps/product/<project>>"
```

Rules: include, don't fork, the templates; keep per-service variables minimal; changing a
template is a cross-service decision. The CD template is what maps git tags to released
images, which is why `9to5-release-confluence-sync` can read the image tag per service.

## Review checklist

1. Two stages; runtime stage contains only the jar and the JRE.
2. Base images pinned (tag + variant), from the internal registry.
3. `CI_TAG` arg → `APP_VERSION` env wiring intact.
4. Non-root user, correct `EXPOSE`, correct workdir.
5. JVM flag set unchanged, or the change justified and recorded.
6. Dump path decision explicit; if dumps matter, path is mounted and retained.
7. CI file includes the shared templates with the right ref; variables match the
   service's registry path.
8. No environment-specific values in the image; no secrets anywhere.
9. A base-image or flag change states old → new versions in the MR and names the test
   evidence.

## Pitfalls seen in the wild

- Dump-on-OOM set, dump path not set: an incident loses the only artifact that explains it.
- Metaspace cap copied from a small service into a proxy-heavy one: `OutOfMemoryError:
  Metaspace` with a heap that looks fine.
- `EXPOSE`/port drift after a service move: probes pass locally, fail in the namespace.
- SNAPSHOT jar glob matching two artifacts after a module split: the image silently ships
  the wrong jar; prefer an explicit jar name when the build becomes multi-module.
- Local hand-built images pushed with release tags: release bookkeeping then disagrees
  with git; tags flow only through CI.
