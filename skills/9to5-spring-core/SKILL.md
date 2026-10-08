---
name: 9to5-spring-core
description: Code and initialize Platform Spring services using microservice-spring-boot-starter. Use when asked to init core, bootstrap a service, scaffold controller/use-case/repository layers, use tech.outsource.core responses/auditing, configure writer-reader routing, or integrate the microservice starter. Derive APIs from the checked-out starter; generate an environment-driven Java 17 template rather than copying credentials or assuming stock Spring defaults.
license: MIT
compatibility: Python 3 for scaffolding; Java 17 and a compatible Gradle wrapper for compilation. Full startup requires the selected published starter and its dependencies, Oracle writer/reader settings, Redis and external JWT keys.
metadata:
  version: "1.0.1"
---

# Spring Core — coding và init service

Nguồn: `/home/example/workspace/microservice-spring-boot-starter`, package
`tech.outsource.core`. Snapshot đã đọc: `bfa01dd7623dc48c2dabbe400a591036929ec44e`.
Đây là thư viện starter, không phải executable service; không copy nguyên build.gradle
của thư viện làm application. Chi tiết bằng chứng: `references/source-map.md`.

## Workflow

1. Xác nhận checkout/commit và version starter mà service thực sự dùng. Không suy ra
   artifact đã publish từ tên branch hoặc hash; dùng `9to5-lib-bump` khi cập nhật version.
2. Đọc `references/source-map.md` và `references/coding.md` trước khi dùng core API.
3. Với service mới, dùng `assets/init-core/` qua script bên dưới. Template giữ package
   `tech.app` để khớp scan. Với repo hiện hữu, chỉ tích hợp các phần cần thiết sau khi đọc
   application/config hiện có, tránh tạo trùng bean.
4. Điền endpoint qua environment/secret injection. Không chép Nexus credentials,
   private key, MQTT/SMTP password hoặc encryption key có sẵn trong source.
5. Compile trước, kiểm tra context với hạ tầng test sau. Báo rõ compile-only hay đã
   startup/API verified; không coi file generated là ứng dụng chạy được ngay.
6. Đồng bộ môi trường qua `9to5-env-config-sync`, SQL qua `9to5-sql-migration`, conventions
   qua `9to5-spring-conventions`, Kafka/outbox qua `9to5-kafka`.

## Init core template

```bash
S=~/.config/opencode/skills/9to5-spring-core/scripts/init_core.py
python3 "$S" --output /tmp/opencode/example-service \
  --service-name example-service --starter-version '<verified-published-version>'
# Sau khi kiểm tra danh sách file:
python3 "$S" --output /tmp/opencode/example-service \
  --service-name example-service --starter-version '<verified-published-version>' --apply
```

Placeholder version ở trên phải thay bằng version thực đã xác minh. Script mặc định
dry-run, từ chối ghi đè bất kỳ file đích nào và không chạy Gradle, Git hay remote API.
Không cung cấp secret qua các flag của script.
Generate rồi build thư mục output, không build trực tiếp `assets/init-core/`.
Script bỏ qua cache/generated directories (như `.gradle/`, `build/`) nhưng giữ
template dotfiles như `.gitignore` và `.env.example`; không xóa cache hiện có.

Template gồm build/settings/properties, application.yml, application entry point,
core-info v2 controller → use-case → record response, và filter dọn thread-local ở
cuối request. Không tự tạo bảng/migration hay bật optional integration.
`references/init-core.md` ghi cấu hình bắt buộc và cách kiểm tra.

## Quy tắc coding chính

- Constructor injection, explicit imports, `Objects.isNull/nonNull` và util đúng
  package đang dùng; không bịa `CollectionUtils.isNotEmpty` trên Spring CollectionUtils.
- HTTP controller validate/bind, gọi public method của Spring `@Service` qua proxy.
  Đặt tên `*UseCaseService` nếu cần aspect ghi `createdProgram`.
- Ghi DB: `@Transactional` ở use-case boundary. Đọc replica: cân nhắc
  `@Transactional(readOnly = true)`. Không tự gọi method cùng instance để mong đổi route.
- Entity/repository: `tech.app.repository.database...`. Feature package bên ngoài cần
  EntityScan/EnableJpaRepositories rõ ràng; component scan không thay thế JPA scan.
- Chọn v1/v2 contract trước khi import response wrapper. V2 controller implement
  `V2API`; body status không đồng nghĩa HTTP status.
- `Auditable` dùng user ID số Integer; `StringAuditable` dùng String. Đối chiếu schema
  và JWT principal trước khi chọn, không thêm base class chỉ vì có sẵn.
- PageRequestCustom nhận page bắt đầu từ 1, cap size 500; validate page >= 1 và size > 0
  trước khi gọi. Dùng `PageImplResponse.of(page, request.current())` đúng overload.
- ThreadLocal context không tự truyền qua async/Kafka/scheduler. Tạo scope riêng và
  `clearContext()` trong finally; không chia sẻ mutable context giữa worker threads.

## Example output

Minh họa, không phải xác nhận môi trường đã deploy:

```text
Service: example-service
Source starter: bfa01dd7 (local checkout examined)
Artifact version: <verified-published-version>
Generated: Gradle config, application.yml, application/controller/use-case/DTO/filter
Package: tech.app
Endpoint: GET /v2/api/core/info (authenticated)
Compile: PASS / BLOCKED with the actual reason
Runtime: chưa kiểm tra — cần Oracle writer/reader, Redis và JWT keys
Response example: {"status":200,"message":"Thành công","value":{"service":"example-service"}}
```
