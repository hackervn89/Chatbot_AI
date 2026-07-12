# Hướng dẫn Quản trị hệ thống Điều hành tác nghiệp (ĐHTN) nâng cao

## I. Cấu hình thông số nhân sự và con dấu đơn vị

### Quy trình cấu hình danh sách người dùng và đăng ký chữ ký số cho Lãnh đạo
Mô tả: Hướng dẫn người quản trị khởi tạo tài khoản cán bộ và cấu hình tệp ảnh chữ ký chuẩn để hệ thống tự động nhận diện chữ ký số của Lãnh đạo.
Các bước thực hiện:
1. Đăng nhập hệ thống bằng tài khoản Quản trị viên (Admin) được phân quyền -> Truy cập menu "Quản trị" -> Chọn "Quản lý người dùng".
2. Nhấn nút "Thêm mới" (biểu tượng icon dấu cộng) nằm ở góc trên bên phải màn hình.
3. Kê khai các thông tin bắt buộc của cán bộ (Họ tên, chức vụ, đơn vị gốc...).
4. **Quy tắc vàng khi nhập tên Lãnh đạo để AI nhận diện chữ ký**:
    *   Khi nhập thông tin họ tên của Lãnh đạo, người quản trị **bắt buộc phải nhập ký tự chữ thường chuẩn** (ví dụ: nhập "Nguyễn Văn A"), tuyệt đối không được viết hoa toàn bộ chữ cái (như "NGUYỄN VĂN A"). 
    *   Hệ thống Điều hành tác nghiệp (ĐHTN) đã được cấu hình công cụ trí tuệ nhân tạo (AI) tự động chuyển đổi định dạng hiển thị. Việc viết thường chuẩn giúp thuật toán AI so khớp chính xác tên Lãnh đạo với chứng thư số đăng ký, từ đó tự động bắt trúng vị trí đóng dấu mộc và hiển thị ảnh chữ ký của Lãnh đạo lên file PDF khi duyệt văn bản mà không bị lệch vị trí chữ ký.
5. **Cấu hình ảnh chữ ký số của Lãnh đạo**:
    *   Tệp ảnh chữ ký của Lãnh đạo tải lên hệ thống bắt buộc phải được cắt sát biên, định dạng ảnh không nền (nền trong suốt) đuôi `.png`.
    *   Quản trị viên tải tệp ảnh lên tại trường "Quản lý ảnh chữ ký" và nhấn "Ghi lại".

### Quy trình quản lý và cấu hình kích thước chuẩn cho ảnh con dấu đơn vị
Mô tả: Hướng dẫn cấu hình kích thước hiển thị vật lý của con dấu cơ quan và con dấu xác nhận (dấu đến) trên hệ thống để đảm bảo tính thẩm mỹ và pháp lý của tài liệu điện tử.
Các bước thực hiện:
1. Truy cập menu "Quản trị" -> Chọn mục "Quản lý ảnh con dấu đơn vị".
2. Thực hiện tải lên ảnh con dấu đơn vị (ảnh mộc đỏ đã được scan sạch lỗi, tách nền trong suốt, định dạng đuôi `.png`).
3. **Quy chuẩn kích thước hiển thị (Kích thước vàng bắt buộc)**:
    *   **Ảnh con dấu cơ quan (Dấu tròn đỏ)**: Khi cấu hình ảnh con dấu đóng trên văn bản đi, Quản trị viên bắt buộc phải thiết lập thông số **Chiều cao chuẩn (Height) = 110**, Chiều rộng tự động co dãn theo tỉ lệ tương ứng. Đây là kích thước đã được chuẩn hóa để khi đóng lên tệp văn bản đi không bị đè chữ ký lãnh đạo và khớp với cỡ con dấu thực tế.
    *   **Ảnh con dấu xác nhận (Dấu chỉ ngày/tháng/số đến của Văn thư)**: Khi cấu hình con dấu xác nhận tiếp nhận văn bản giấy của Văn thư, Quản trị viên bắt buộc phải cấu hình chính xác kích thước hiển thị: **Chiều cao (Height) = 50** và **Chiều rộng (Width) = 680**. Kích thước này đảm bảo con dấu bao trọn toàn bộ chữ viết số đến và ngày tháng viết tay của Văn thư mà không bị vỡ ảnh hay che mờ văn bản gốc bên dưới.

### Quy trình cấu hình thứ tự hiển thị nhân sự trong sơ đồ cây luân chuyển
Mô tả: Thiết lập số thứ tự ưu tiên cho từng tài khoản để danh sách Ban Lãnh đạo luôn hiển thị cố định ở đầu màn hình luân chuyển văn bản, giúp Văn thư và Chuyên viên chọn người ký duyệt nhanh nhất.
Các bước thực hiện:
1. Truy cập menu "Quản trị" -> Chọn "Quản lý người dùng" -> Chọn tài khoản cần gán thứ tự ưu tiên -> Nhấn chọn biểu tượng "Chỉnh sửa" (icon bút chì).
2. Di chuyển đến trường thông tin "Số thứ tự sắp xếp" và nhập con số ưu tiên theo đúng quy chuẩn phân cấp của toàn tỉnh sau đây:
    *   **Mức số 10**: Chỉ áp dụng gán cho vị trí **Bí thư đơn vị** (đảm bảo Bí thư luôn đứng vị trí số 1 trên cùng danh sách hiển thị).
    *   **Mức số 15 hoặc 16**: Áp dụng gán cho vị trí các **Phó Bí thư** hoặc **Phó Chủ tịch đơn vị**.
    *   **Mức số 31**: Áp dụng gán cho các **Lãnh đạo văn phòng / Ủy viên Ban thường vụ**.
    *   **Để trống (không nhập số)**: Áp dụng cho toàn bộ các **Chuyên viên nghiệp vụ và Nhân viên**. Hệ thống sẽ tự động sắp xếp danh sách chuyên viên còn lại ở phía dưới theo thứ tự bảng chữ cái tiếng Việt (A, B, C...).
3. Nhấn nút "Ghi lại" để cập nhật cấu hình sắp xếp hiển thị lên toàn hệ thống.

---

## II. Cấu hình Luồng xử lý Văn bản (Workflows)

### Quy trình cấu hình luồng luân chuyển và nguyên tắc bảo toàn Node
Mô tả: Hướng dẫn người quản trị thiết lập sơ đồ luồng luân chuyển văn bản đến và đi bằng biểu đồ đồ họa trực quan trên hệ thống.
Các bước thực hiện:
1. Vào menu "Quản trị" -> Chọn "Quản lý luồng" -> Kích đúp vào luồng cần sửa đổi hoặc bấm "Thêm mới" -> Chọn mục "Cấu hình luồng".
2. Hệ thống hiển thị giao diện đồ họa. Nhấp chuột chọn biểu tượng "Tạo Node bắt đầu" (Node đầu vào), "Tạo Node xử lý" (Node trung gian) hoặc "Tạo Node kết thúc" để vẽ các vị trí vai trò trong luồng luân chuyển. Chọn biểu tượng hành động mũi tên để vẽ luồng đi của văn bản từ Node này sang Node khác.
3. **Quy tắc an toàn hệ thống (Ngăn ngừa lỗi đứt gãy luồng văn bản)**:
    *   *Được phép chỉnh sửa/xóa*: Quản trị viên có toàn quyền chỉnh sửa hoặc xóa bỏ các đường mũi tên hành động liên kết giữa các Node luồng để thay đổi hướng đi văn bản.
    *   *TẬP TRUNG CẢNH BÁO - TUYỆT ĐỐI KHÔNG XÓA NODE SẴN CÓ*: Khi luồng dữ liệu đang chạy trong thực tế, quản trị viên **tuyệt đối không được xóa các Node vai trò cũ** để tạo lại Node mới thay thế. 
    *   *Nguyên nhân kỹ thuật*: Mỗi Node khi được tạo ra lần đầu tiên sẽ được hệ thống gán một mã ID định danh duy nhất và duy trì một chuỗi số ID tuần tự khép kín. Việc xóa Node cũ để tạo Node mới sẽ phá vỡ chuỗi số ID định danh tuần tự của cơ sở dữ liệu, khiến toàn bộ các văn bản đang chạy dở trên luồng đó bị treo, không thể chuyển tiếp tiếp tục và hệ thống sẽ báo lỗi không tìm thấy điểm đến.
    *   *Cách xử lý đúng khi thay đổi nhân sự*: Quản trị viên chỉ cần kích đúp chuột vào Node vai trò hiện tại và chọn cấu hình thay đổi Đơn vị/Cá nhân gán với Node đó, giữ nguyên Node gốc trên sơ đồ biểu đồ luồng.
