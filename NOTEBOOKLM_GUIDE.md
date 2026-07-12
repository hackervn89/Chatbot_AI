# 📖 Hướng Dẫn Định Dạng Tri Thức RAG Bằng NotebookLM

> Tài liệu này hướng dẫn cách sử dụng Google NotebookLM để phân tích tài liệu thô (PDF, Word, văn bản ghi chép...) và chuyển hóa chúng thành định dạng Markdown (`.md`) chuẩn tối ưu 100% cho hệ thống RAG Chuyên Viên Ảo.

---

## 📐 1. Tại Sao Cần Định Dạng Chuẩn Markdown?
Hệ thống RAG của chúng ta sử dụng module **Phân đoạn ngữ nghĩa (`semantic_chunk`)**. Bộ chia này sẽ cắt tài liệu dựa vào tiêu đề heading Markdown (`#`, `##`, `###`).
*   Nếu tài liệu định dạng lộn xộn: AI sẽ bị cắt nửa chừng câu hỏi hoặc nửa chừng bước thao tác, dẫn đến câu trả lời của Chatbot bị thiếu thông tin hoặc sai lệch.
*   Nếu định dạng chuẩn Markdown: Từng quy trình, từng nghiệp vụ sẽ được gom gọn hoàn chỉnh trong 1 chunk, giúp Chatbot trả lời cực kỳ chính xác.

---

## 🛠️ 2. Quy Trình Thực Hiện Trên NotebookLM

### Bước 1: Tải tài liệu nguồn lên NotebookLM
1. Truy cập [Google NotebookLM](https://notebooklm.google.com/).
2. Tạo một Notebook mới (ví dụ đặt tên: *Chuẩn hóa tri thức Đảng bộ*).
3. Tải lên các tài liệu thô của bạn (PDF, Word, file TXT hoặc dán liên kết).

### Bước 2: Chạy Prompt chuẩn hóa cấu trúc
Dán đoạn prompt dưới đây vào khung chat của NotebookLM để yêu cầu AI phân tích và biên soạn lại văn bản theo chuẩn RAG Markdown.

---

## ✍️ 3. Prompt Mẫu Cho NotebookLM (Hãy Copy Đoạn Này)

```text
Bạn là một chuyên gia cấu trúc dữ liệu cho hệ thống RAG (Retrieval-Augmented Generation). 
Nhiệm vụ của bạn là đọc toàn bộ tài liệu nguồn tôi đã cung cấp và chuyển đổi/tái cấu trúc nó thành định dạng Markdown (.md) chuẩn hóa theo đúng các quy tắc dưới đây.

QUY TẮC CẤU TRÚC VĂN BẢN:
1. Tiêu đề lớn nhất (Tên tài liệu): Sử dụng duy nhất 1 tiêu đề cấp 1 (#) ở đầu tài liệu.
   Ví dụ: # Hướng dẫn sử dụng tính năng Lịch họp Đảng ủy

2. Tiêu đề nhóm nội dung: Sử dụng tiêu đề cấp 2 (##) để chia nhóm lớn.
   Ví dụ: ## I. Thao tác trên thiết bị di động (Mobile)

3. Tiêu đề cho từng quy trình/nghiệp vụ cụ thể (QUAN TRỌNG NHẤT): Sử dụng tiêu đề cấp 3 (###) cho mỗi quy trình độc lập. Đây là anchor để hệ thống cắt chunks tri thức.
   Ví dụ: ### Quy trình duyệt lịch họp dành cho Bí thư

4. Nội dung chi tiết trong mỗi quy trình (###):
   - Viết rõ ràng, rành mạch từng bước (Bước 1, Bước 2, Bước 3...).
   - Các nút bấm, nhãn giao diện hoặc tên trường thông tin phải được đặt trong dấu ngoặc kép hoặc viết hoa rõ ràng (ví dụ: bấm nút "Phê duyệt", chọn trạng thái "Hoàn thành").
   - Nếu tài liệu gốc có nhắc đến hình ảnh minh họa, hãy giữ nguyên ký hiệu hình ảnh dạng "Hình N" (Ví dụ: "...như hiển thị ở Hình 2"). Không được xóa nhãn hình ảnh này.

5. Loại bỏ hoàn toàn nhiễu:
   - Loại bỏ số trang (ví dụ: Trang 1/24).
   - Loại bỏ các dòng Header/Footer lặp đi lặp lại của trang.
   - Loại bỏ các câu chuyển tiếp không mang giá trị tri thức (ví dụ: "Chào mừng quý vị đến với...", "Bảng mục lục dưới đây...").

Dưới đây là cấu trúc mẫu bạn phải tuân thủ:

# [Tên tài liệu tri thức]

## [Nhóm nội dung 1]

### [Quy trình cụ thể A]
Mô tả ngắn gọn về quy trình này.
Các bước thực hiện:
1. Bước 1: Truy cập vào mục "..." trên giao diện (Hình 1).
2. Bước 2: Điền đầy đủ thông tin vào trường "..." và nhấn nút "...".
3. Bước 3: Đợi hệ thống phê duyệt.

### [Quy trình cụ thể B]
...

Hãy phân tích toàn bộ tài liệu đã tải lên và xuất ra nội dung Markdown (.md) hoàn chỉnh theo đúng cấu trúc trên. Không thêm bớt ý kiến cá nhân hoặc câu giới thiệu của AI ở đầu/cuối kết quả. Chỉ trả về mã Markdown thô.
```

---

## 📝 4. Ví Dụ Minh Họa Kết Quả Đầu Ra

Sau khi NotebookLM chạy xong, kết quả trả về sẽ có dạng chuẩn như sau:

```markdown
# Hướng dẫn xử lý Văn bản đến cấp xã

## I. Quy trình dành cho Văn thư

### Bước 1: Tiếp nhận và đăng ký văn bản đến
Mục đích: Đưa văn bản giấy hoặc văn bản điện tử của cấp trên vào hệ thống quản lý.
Các bước thực hiện:
1. Truy cập vào menu "Văn bản đến" -> chọn "Đăng ký văn bản" (Hình 1).
2. Quét (scan) văn bản giấy sang tệp PDF và tải lên trường "Tệp đính kèm".
3. Điền các thông tin pháp lý bắt buộc: Số ký hiệu, Ngày ban hành, Cơ quan ban hành.
4. Nhấn nút "Lưu nháp" để hoàn tất đăng ký bước đầu.

### Bước 2: Trình xin ý kiến chỉ đạo của Bí thư
Mục đích: Xin ý kiến phân phối công việc từ Thường trực Đảng ủy.
Các bước thực hiện:
1. Tại danh sách văn bản đến, chọn văn bản vừa đăng ký.
2. Nhấn nút "Trình xin chỉ đạo" (Hình 2).
3. Chọn người nhận là "Bí thư Đảng ủy xã" và nhập nội dung xin ý kiến chỉ đạo.
4. Nhấn "Gửi đi".
```

---

## 📥 5. Cách Đưa Vào Hệ Thống RAG Sau Khi Chuẩn Hóa
1. Copy kết quả Markdown từ NotebookLM.
2. Lưu lại thành tệp có phần mở rộng `.md` (Ví dụ: `huong_dan_van_ban_den.md`).
3. Truy cập vào giao diện quản trị của bạn tại: `https://bot.conghaiso.vn/admin/documents`.
4. Nhấn nút **"+ Nạp tài liệu mới"**.
5. Chọn danh mục phù hợp (Tri thức gốc hoặc Tri thức cập nhật).
6. Tải tệp `.md` vừa lưu lên. Chọn **"Lưu Nháp"** để kiểm tra lại trên hệ thống trước khi chính thức kích hoạt RAG.
