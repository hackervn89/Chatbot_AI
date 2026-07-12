# 📖 Hướng Dẫn Định Dạng Tri Thức RAG Bằng NotebookLM

> Tài liệu này hướng dẫn cách sử dụng Google NotebookLM để phân tích tài liệu thô (PDF, Word, văn bản chỉ đạo của Đảng...) và chuyển hóa chúng thành định dạng Markdown (`.md`) chuẩn tối ưu 100% cho hệ thống RAG Chuyên Viên Ảo.

---

## 📐 1. Tại Sao Cần Định Dạng Chuẩn Markdown?
Hệ thống RAG sử dụng module **Phân đoạn ngữ nghĩa (`semantic_chunk`)** để tự động chia nhỏ tài liệu dựa vào tiêu đề heading Markdown (`#`, `##`, `###`).
*   **Nếu định dạng lộn xộn:** AI sẽ cắt nửa chừng câu hỏi, điều khoản hoặc quy trình, làm chatbot trả lời thiếu chính xác.
*   **Nếu định dạng chuẩn Markdown:** Từng quy trình thao tác hoặc từng Điều khoản pháp lý sẽ được gom gọn hoàn chỉnh trong 1 chunk (khối tri thức), giúp Chatbot trả lời cực kỳ đầy đủ và chuẩn xác.

---

## 🛠️ 2. Quy Trình Thực Hiện Trên NotebookLM
1. Truy cập [Google NotebookLM](https://notebooklm.google.com/).
2. Tạo một Notebook mới (ví dụ đặt tên: *Chuẩn hóa tri thức Đảng bộ*).
3. Tải lên tài liệu thô của bạn (PDF, Word, file TXT).
4. Tùy thuộc vào loại tài liệu, hãy copy **Prompt tương ứng** dưới đây dán vào khung chat của NotebookLM để AI xử lý và xuất ra Markdown chuẩn.

---

## 📂 PHẦN A: DÀNH CHO TÀI LIỆU HƯỚNG DẪN SỬ DỤNG PHẦN MỀM (HDSD)
*Dành cho tài liệu có các bước bấm nút, màn hình, hình ảnh thao tác thực tế.*

### ✍️ Prompt NotebookLM cho tài liệu HDSD:
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
   - Nếu muốn đính kèm hình ảnh minh họa, hãy chèn trực tiếp liên kết ảnh tĩnh dạng Markdown (ví dụ: `![Mô tả ảnh](https://domain.com/path/to/image.png)`).

5. Loại bỏ hoàn toàn nhiễu:
   - Loại bỏ số trang (ví dụ: Trang 1/24).
   - Loại bỏ các dòng Header/Footer lặp đi lặp lại của trang.
   - Loại bỏ các câu chuyển tiếp không mang giá trị tri thức (ví dụ: "Chào mừng quý vị đến với...", "Bảng mục lục dưới đây...").

Dưới đây là cấu trúc mẫu, ví dụ cụ thể mà bạn cần tuân thủ:

# [Tên tài liệu tri thức]

## [Nhóm nội dung 1]

### [Quy trình cụ thể A]
Mô tả ngắn gọn về quy trình này.
Các bước thực hiện:
1. Bước 1: Truy cập vào mục "..." trên giao diện.
2. Bước 2: Điền đầy đủ thông tin vào trường "..." và nhấn nút "...".
3. Bước 3: Đợi hệ thống phê duyệt.
Không thêm bớt ý kiến cá nhân hoặc câu giới thiệu của AI ở đầu/cuối kết quả. Chỉ trả về mã Markdown thô.
```

### 📝 Ví dụ kết quả đầu ra cho tài liệu HDSD:
```markdown
# Hướng dẫn xử lý Văn bản đến cấp xã

## I. Quy trình dành cho Văn thư

### Bước 1: Tiếp nhận và đăng ký văn bản đến
Mục đích: Đưa văn bản giấy hoặc văn bản điện tử của cấp trên vào hệ thống quản lý.
Các bước thực hiện:
1. Truy cập vào menu "Văn bản đến" -> chọn "Đăng ký văn bản".
2. Quét (scan) văn bản giấy sang tệp PDF và tải lên trường "Tệp đính kèm".
3. Điền các thông tin pháp lý bắt buộc: Số ký hiệu, Ngày ban hành, Cơ quan ban hành.
4. Nhấn nút "Lưu nháp" để hoàn tất đăng ký bước đầu.
```

---

## 📂 PHẦN B: DÀNH CHO VĂN BẢN CHỈ ĐẠO, NGHỊ QUYẾT, QUY ĐỊNH CỦA ĐẢNG
*Dành cho tài liệu pháp lý, quy chế điều lệ, các văn bản hành chính Khối Đảng.*

### ✍️ Prompt NotebookLM cho Văn bản Đảng:
```text
Bạn là một chuyên gia cấu trúc dữ liệu cho hệ thống RAG (Retrieval-Augmented Generation) của Khối Đảng.
Nhiệm vụ của bạn là đọc toàn bộ văn bản chỉ đạo, nghị quyết, quy định, chỉ thị của Đảng được cung cấp và tái cấu trúc nó thành định dạng Markdown (.md) chuẩn tối ưu cho RAG theo đúng các quy tắc dưới đây.

QUY TẮC CẤU TRÚC VĂN BẢN ĐẢNG:
1. Tên văn bản (Tiêu đề cấp 1 #): Ghi đầy đủ tên văn bản, số ký hiệu, ngày ban hành và cơ quan ban hành.
   Ví dụ: # Nghị quyết số 18-NQ/TW ngày 25/10/2017 của Ban Chấp hành Trung ương khóa XII

2. Các chương / Phần lớn (Tiêu đề cấp 2 ##): Chia theo cấu trúc lớn của văn bản gốc (Chương I, Chương II...).
   Ví dụ: ## Chương I: Quy định chung

3. Các điều khoản cụ thể (Tiêu đề cấp 3 ### - QUAN TRỌNG NHẤT):
   - Mỗi Điều, Mục, hoặc Khoản lớn độc lập phải được tách thành một tiêu đề cấp 3 (###).
   - Quy tắc đính kèm ngữ cảnh (Self-Contained Context): Tại mỗi tiêu đề cấp 3, bạn BẮT BUỘC phải đưa thông tin viết tắt của tên văn bản vào đầu tiêu đề để khi hệ thống cắt chunks, đoạn văn bản đó vẫn tự mang đầy đủ ngữ cảnh thuộc văn bản nào.
     Định dạng tiêu đề: ### [Viết tắt tên văn bản] Điều N: [Tên điều]
     Ví dụ: ### [NQ 18-NQ/TW] Điều 1: Mục tiêu và yêu cầu

4. Nội dung chi tiết trong mỗi điều (###):
   - Giữ nguyên văn phong hành chính trang trọng của Đảng.
   - Sử dụng danh sách gạch đầu dòng hoặc đánh số rõ ràng (1., 2., a., b...) để các khoản, điểm được rành mạch.
   - Nếu điều khoản có tham chiếu đến điều khác (ví dụ: "...theo quy định tại Điều 5 của Nghị quyết này"), hãy ghi chú rõ điều tham chiếu.

5. Loại bỏ hoàn toàn nhiễu:
   - Loại bỏ số trang, header/footer.
   - Loại bỏ phần ký tên đóng dấu và danh sách nơi nhận ở cuối văn bản (ví dụ: "T/M BAN CHẤP HÀNH...", "Nơi nhận:...").
   - Đối với người ký chỉ cần ghi: Văn bản ký bởi [Họ tên người ký], [Chức vụ].

Hãy phân tích toàn bộ tài liệu đã tải lên và xuất ra nội dung Markdown (.md) hoàn chỉnh theo đúng cấu trúc trên. Không thêm bớt ý kiến cá nhân hay câu giới thiệu của AI ở đầu/cuối kết quả. Chỉ trả về mã Markdown thô.
```

### 📝 Ví dụ kết quả đầu ra cho Văn bản Đảng:
```markdown
# Quy định số 24-QĐ/TW ngày 30/7/2021 của Ban Chấp hành Trung ương về thi hành Điều lệ Đảng

## Chương I: Đảng viên

### [QĐ 24-QĐ/TW] Điều 1: Tuổi đời và trình độ học vấn của người vào Đảng
1. Về tuổi đời:
   - Người vào Đảng phải từ 18 tuổi đến đủ 60 tuổi (tính theo tháng).
   - Việc kết nạp vào Đảng những người trên 60 tuổi do Ban Thường vụ Tỉnh ủy xem xét, quyết định.
2. Về trình độ học vấn:
   - Người vào Đảng phải có bằng tốt nghiệp trung học cơ sở hoặc tương đương trở lên.

### [QĐ 24-QĐ/TW] Điều 2: Thủ tục kết nạp đảng viên
Các bước thực hiện thủ tục kết nạp đảng viên bao gồm:
a) Người vào Đảng phải tự làm đơn xin vào Đảng.
b) Báo cáo trung thực lý lịch với chi bộ.
c) Được hai đảng viên chính thức giới thiệu (theo quy định cụ thể tại Điều 3 Quy định này).
```

---

## 📥 5. Quy Trình Nạp Vào RAG Sau Khi Chuẩn Hóa
1. Copy kết quả Markdown từ NotebookLM.
2. Lưu lại thành tệp có phần mở rộng `.md` (Ví dụ: `quy_dinh_24_qd_tw.md`).
3. Truy cập vào giao diện quản trị: `https://bot.conghaiso.vn/admin/documents`.
4. Nhấn nút **"+ Nạp tài liệu mới"**.
5. Chọn danh mục phù hợp và tải tệp `.md` lên.
6. Chọn chế độ **"Lưu Nháp"** để kiểm tra lại trên Dashboard và chạy AI thẩm định trước khi kích hoạt.
