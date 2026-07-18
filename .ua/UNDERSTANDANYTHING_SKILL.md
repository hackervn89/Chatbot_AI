# Skill: Maintainable UnderstandAnything Knowledge Graph

## Mục tiêu

Tạo và duy trì knowledge graph có thể tin cậy để hiểu codebase, truy vết kiến trúc và đánh giá ảnh hưởng thay đổi. Graph là **bản đồ tĩnh**, không thay thế việc đọc mã nguồn trước khi sửa tính năng hoặc triển khai production.

## Phạm vi quét

### Bao gồm

- Mã nguồn chạy thực tế: Python, SQL, Dockerfile, YAML, shell/batch.
- Entry point, router, service, data model, pipeline, script vận hành.
- Template/UI khi được route hoặc service sử dụng.
- Tài liệu kiến trúc và vận hành có giá trị định hướng.

### Loại trừ mặc định

- Bí mật: `.env`, credential, token, private key.
- Output sinh tự động, cache, log, virtual environment, `.git`.
- Dữ liệu nhị phân hoặc tài liệu nguồn lớn khi chỉ đóng vai trò knowledge corpus, trừ khi cần mô tả chúng là resource.
- Thư mục tạm (`temp/`, `.agent_bridge/`) và artifacts phát sinh của tool.

Cập nhật `.ua/.understandignore` khi một nhóm file gây nhiễu cho graph. Không loại trừ code đang chạy chỉ để giảm số node.

## Chuẩn schema

### Node

Mỗi node phải có tối thiểu:

```json
{
  "id": "function:services/chat_engine.py:answer_question",
  "type": "function",
  "path": "services/chat_engine.py",
  "name": "answer_question",
  "label": "answer_question",
  "summary": "Điều phối phân loại câu hỏi, truy xuất RAG, gọi AI và lưu lịch sử.",
  "tags": ["chat", "rag", "orchestration"],
  "complexity": "complex"
}
```

Quy ước:

1. **ID phải dùng đường dẫn tương đối POSIX** với workspace; không chứa ổ đĩa hoặc đường dẫn máy cục bộ.
2. `name` là định danh ngắn, không rỗng. `label` là tên hiển thị; có thể trùng `name`.
3. `path` bắt buộc với mọi node gắn với một tệp. Node cấu trúc (project/layer) có thể không cần `path`.
4. `summary` mô tả trách nhiệm thực tế, không chỉ lặp lại tên.
5. `type` dùng nhất quán: `file`, `service`, `pipeline`, `function`, `class`, `table`, `schema`, `config`, `document`, `section`, `resource`.

### Edge

```json
{
  "source": "function:services/chat_engine.py:answer_question",
  "target": "function:services/rag_pipeline.py:hybrid_search",
  "type": "calls",
  "direction": "forward"
}
```

Chỉ tạo cạnh có bằng chứng từ code, cấu hình hoặc tài liệu:

- `contains`: file/module chứa function, class, table, section.
- `imports`: module A import module B.
- `calls`: hàm A gọi hàm B khi xác định được tĩnh.
- `defines`: file định nghĩa bảng, index hoặc resource.
- `configures`: cấu hình điều khiển service/hạ tầng.
- `deploys`: Compose/Docker/Caddy triển khai service.
- `related`: liên hệ kiến trúc đã được ghi rõ, không dùng thay cho `calls` hay `imports`.

Không tạo cạnh suy đoán. Hai đầu cạnh phải tồn tại trong `nodes`; cạnh trùng `(source, target, type)` phải được loại bỏ.

## Quy trình phân tích

1. Đọc `MAPCODE.md`, `PROJECT_OVERVIEW.md`, `.ua/.understandignore` để hiểu phạm vi và ranh giới.
2. Quét danh sách file theo ignore rules; lưu `scan-result.json` gồm `files`, `importMap`, framework và ngôn ngữ.
3. Phân tích code theo dependency direction: config/database/models → services → routers/main → scripts/templates.
4. Tạo node cấp tệp trước; sau đó tạo node function/class/table/index có vai trò hoặc độ phức tạp đáng kể.
5. Tạo `contains`, `imports`, `calls` có bằng chứng. Bổ sung layers và tour theo luồng người đọc hiểu hệ thống.
6. Chuẩn hóa graph bằng `python .ua/normalize_graph.py`.
7. Chạy quality gates trước khi sử dụng graph.

## Quality gates bắt buộc

Graph đạt yêu cầu khi:

- JSON hợp lệ cho `knowledge-graph.json`, `knowledge-graph-en.json` (nếu có), `layers.json`, `tour.json`, `review.json`, `meta.json`.
- `nodesMissingName = 0`.
- `nodesMissingPath = 0` cho node gắn với tệp.
- `danglingEdges = 0`.
- Không còn đường dẫn tuyệt đối trong node ID, edge, layer hoặc tour.
- Cạnh `imports` phản ánh `scan-result.json.importMap` đối với các file đã có node cấp tệp.
- `layers[].nodeIds` và `tour[].nodeIds` đều tham chiếu node tồn tại.
- `meta.json` ghi commit và thời điểm phân tích/chuẩn hóa.

Node cô lập không mặc định là lỗi: tài liệu hoặc resource độc lập có thể hợp lệ. Cần đánh giá theo loại node. Node code cô lập cần được kiểm tra vì có thể thiếu import/call hoặc là mã không còn sử dụng.

## Cập nhật sau khi code thay đổi

1. Sinh lại graph từ trạng thái commit hiện tại.
2. Chạy normalizer để sửa tính di động và bổ sung metadata/quality report.
3. So sánh số node, edge, import coverage và số node cô lập với phiên bản trước.
4. Đọc trực tiếp các hotspot có thay đổi (entrypoint, router, service, model) để xác nhận summary/call edge.
5. Không chỉnh sửa code ứng dụng chỉ nhằm làm đẹp graph.

## Hạn chế cần nhớ

- Python dynamic imports, dependency injection, framework decorator và LLM-driven routing có thể không được suy ra đầy đủ bằng phân tích tĩnh.
- `calls` là quan hệ bảo thủ; thiếu cạnh tốt hơn cạnh sai.
- Graph chỉ đúng đến commit/timestamp ghi trong `meta.json`.
