# Init core — cấu hình và kiểm tra

Template tại `assets/init-core/` tạo 10 file. Java 17 / Boot 3.1.3 / Cloud 2022.0.4
khớp snapshot đã đọc, không phải lời khuyên chọn các version này cho mọi project mới.
Khi đổi starter version, kiểm tra lại dependency compatibility và source contract.

## Chuẩn bị

- Chọn version starter đã publish. Script chỉ kiểm tra cú pháp version, không chứng
  minh artifact tồn tại. Không dùng commit hash thay artifact version.
- Cấp MAVEN_REPOSITORY_URL (HTTPS), MAVEN_REPOSITORY_USERNAME/PASSWORD qua môi trường.
- Dùng Gradle wrapper từ service tương thích đã được kiểm tra, hoặc tạo wrapper với
  Gradle 8.3 đã cài: `gradle wrapper --gradle-version 8.3`. Template không chứa wrapper
  binary và không tự tải dependency trong lúc generate.
- Điền DB_WRITER_URL/USERNAME/PASSWORD và DB_READER_URL/USERNAME/PASSWORD. URL dạng
  `jdbc:oracle:thin:@//<host>:1521/<service>`. Local có thể trỏ cả hai về cùng database.
- REDIS_HOST/REDIS_PORT: revision này custom connection factory chỉ dùng host/port.
  Cấu hình password/SSL trong YAML không đủ để sửa factory; môi trường yêu cầu chúng
  cần thay đổi starter hoặc cấu hình bean có chủ đích trước khi startup.
- JWT_PUBLIC_KEY và JWT_PRIVATE_KEY chứa PEM đầy đủ; private key PKCS#8. Không dùng
  key mặc định trong source. JWT_JWK_SET_URI optional cho decoder; encoder vẫn cần keys.
- DB_ENCRYPTION_KEY phải khớp dữ liệu đang mã hóa nếu dùng converter; không đổi key
  ngẫu nhiên cho database có dữ liệu. Không ghi giá trị key vào source control.

## Generated code

GET `/v2/api/core/info` gọi CoreInfoUseCaseService; cần xác thực theo core security.
Không truy cập bảng nghiệp vụ, nhưng toàn bộ starter vẫn khởi tạo datasource/Redis/JWT.
CoreContextCleanupFilter bao ngoài servlet chain để dọn ThreadLocal trước/sau request
đồng bộ; async dispatch/worker cần scope riêng như coding.md. Khi starter đã sửa cleanup,
đánh giá bỏ filter trùng trách nhiệm. Không thêm permit-all /** để làm demo chạy nhanh.

## Verification

```bash
./gradlew compileJava
./gradlew bootJar
# Chỉ khi đã cấp hạ tầng và environment:
./gradlew bootRun
# Với token test phù hợp:
curl --fail-with-body -H "Authorization: Bearer $TEST_ACCESS_TOKEN" \
  http://localhost:8080/v2/api/core/info
```

Kiểm tra status/message/value trong JSON, không chỉ HTTP 200. Dùng `./gradlew dependencies`
để kiểm tra version resolution nếu artifact mới khác snapshot. Với feature ghi DB,
kiểm tra transaction route thực tế và schema migration trước khi coi integration hoàn tất.
Không đưa token hoặc connection secrets vào báo cáo.
