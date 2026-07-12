# Hướng dẫn quản trị hệ thống nâng cao và Sổ tay xử lý sự cố Điều hành tác nghiệp (ĐHTN)

## I. Quy chuẩn thông số cấu hình hệ thống (System Standards)

### Quy trình cấu hình kích thước con dấu điện tử trên hệ thống
Mô tả: Hướng dẫn người quản trị thiết lập kích thước chuẩn xác cho các loại con dấu điện tử của cơ quan khi tải lên hệ thống để đảm bảo tính mỹ thuật và độ hiển thị chính xác trên văn bản ký duyệt.
Các thông số cấu hình chuẩn:
1.  **Đối với con dấu cơ quan chính thức**:
    *   Yêu cầu định dạng tệp tin: Hình ảnh không có nền (định dạng tệp `.png`).
    *   Chiều cao (height) chuẩn xác khi cấu hình tải lên hệ thống: **110**.
2.  **Đối với con dấu xác nhận (Dấu chỉ ngày, tháng, số đến)**:
    *   Yêu cầu hiển thị: Kích thước phải cân đối để khớp hoàn toàn với chữ ký số của lãnh đạo đơn vị.
    *   Chiều cao (height) chuẩn cấu hình: **50**.
    *   Chiều rộng (width) chuẩn cấu hình: **680**.

### Quy trình gán số thứ tự sắp xếp nhân sự khi luân chuyển văn bản
Mô tả: Thiết lập số thứ tự (mã ưu tiên hiển thị) cho danh sách cán bộ, lãnh đạo để danh sách luân chuyển văn bản luôn hiển thị đúng cấp bậc hành chính từ cao xuống thấp khi người dùng thao tác.
Quy tắc gán số thứ tự của người quản trị hệ thống:
1.  **Vị trí Bí thư đơn vị**: Gán số thứ tự hiển thị là **10** (để luôn luôn xuất hiện ở đầu danh sách).
2.  **Vị trí các Phó Bí thư hoặc Phó Chủ tịch**: Gán số thứ tự hiển thị là **15** hoặc **16** (hiển thị ngay sau Bí thư).
3.  **Vị trí Lãnh đạo Văn phòng**: Gán số thứ tự hiển thị là **31**.
4.  **Vị trí các Chuyên viên và nhân sự khác**: Người quản trị không cần gán số thứ tự thủ công, hệ thống Điều hành tác nghiệp (ĐHTN) sẽ tự động sắp xếp danh sách hiển thị theo thứ tự bảng chữ cái tiếng Việt.

---

## II. Sổ tay hướng dẫn khắc phục sự cố thực tế (Troubleshooting)

### Sự cố văn bản nhảy mốc thời gian tương lai do lỗi nhận dạng chữ viết (AI OCR)
Mô tả sự cố: Khi bộ phận văn thư thực hiện viết tay ngày tháng nhận văn bản đến quá sát nhau hoặc sát vạch chia dòng trên phiếu nhận, công cụ nhận dạng chữ viết tự động (AI OCR) của máy quét sẽ nhận diện nhầm ký tự (ví dụ: nhận diện nhầm "Tháng 3" thành "Tháng 8"). Hệ thống sẽ tự động lưu trữ văn bản vào mốc thời gian tương lai (Tháng 8) dẫn đến việc văn bản lập tức biến mất khỏi danh sách hiển thị xử lý của ngày hiện tại.
Cách thức khắc phục sự cố:
1.  **Bước 1**: Đăng nhập vào hệ thống Điều hành tác nghiệp (ĐHTN) bằng tài khoản có quyền văn thư hoặc tìm kiếm.
2.  **Bước 2**: Truy cập vào công cụ Tìm kiếm nâng cao của hệ thống.
3.  **Bước 3**: Tại ô lọc điều kiện thời gian, thay vì lọc ngày hiện tại, người dùng thiết lập mốc thời gian tìm kiếm ở tương lai (chọn lọc tìm kiếm đến mốc Tháng 8).
4.  **Bước 4**: Nhấn nút Tìm kiếm để truy xuất văn bản bị ẩn.
5.  **Bước 5**: Nhấn vào chi tiết văn bản, chọn nút "Chỉnh sửa" và tiến hành hiệu chỉnh lại ngày đến chính xác bằng tay. Nhấn "Ghi lại" để văn bản quay về đúng luồng hiển thị ngày hiện hành.

### Lỗi gán sai vai trò Chuyên viên chủ trì khi phân quyền nhận văn bản
Mô tả sự cố: Người quản trị gán sai vai trò khi phân quyền nhận văn bản đến của đơn vị cho Chuyên viên nghiệp vụ. Nếu vô tình tích chọn vào ô cấu hình "Chủ trì" (preside) đối với vai trò Chuyên viên nhận văn bản đơn vị, toàn bộ văn bản đến của đơn vị sẽ tự động chuyển thẳng vào kho mục lưu trữ cá nhân của riêng chuyên viên đó thay vì lưu trữ tại thư mục chung của đơn vị. Điều này gây ra mất mát luồng dữ liệu tác nghiệp khi chuyên viên này thực hiện chuyển công tác.
Cách thức phòng ngừa và cấu hình đúng:
1.  **Quy tắc cấu hình**: Tuyệt đối **không tích chọn** ô "Chủ trì" (preside) khi thiết lập phân quyền cho vai trò Chuyên viên nghiệp vụ nhận văn bản cấp đơn vị.
2.  **Kiểm tra**: Định kỳ kiểm tra bảng phân quyền luồng nhận văn bản để đảm bảo chỉ có Lãnh đạo hoặc Văn thư được gán quyền "Chủ trì" ở cấp đơn vị.

### Lỗi đứt gãy luồng văn bản do xóa Node (Nút vai trò) trong luồng cấu hình
Mô tả sự cố: Khi hiệu chỉnh luồng luân chuyển văn bản, người quản lý luồng tự ý xóa các Node (các nút hình tròn chứa chức danh/vai trò) cũ để tạo Node mới thay vì chỉ chỉnh sửa đường liên kết. Do mỗi Node được hệ thống gán một mã số ID định danh tuần tự vĩnh viễn ở phần cứng, việc xóa Node sẽ làm gãy chuỗi số ID tuần tự này, khiến các văn bản đang chạy dở dang trên luồng gặp lỗi hệ thống và không thể luân chuyển tiếp.
Cách thức phòng ngừa và cấu hình đúng:
1.  **Quy tắc chỉnh sửa**: Khi cần điều chỉnh luồng, người quản trị chỉ được phép xóa hoặc thay đổi các đường hành động (các mũi tên liên kết giữa các Node).
2.  **Cấm tuyệt đối**: Không được xóa các Node (Nút vai trò) đã có sẵn trên luồng cấu hình để tránh làm hỏng chuỗi liên kết ID.

---

## III. Quy định bảo mật đăng nhập hệ thống

### Quy định thời gian hiệu lực lưu mã OTP đăng nhập trên trình duyệt
Mô tả: Quy định về thời hạn duy trì trạng thái xác thực đăng nhập an toàn của cán bộ thông qua mã xác thực một lần (OTP).
Quy tắc bảo mật hệ thống:
1.  Sau khi người dùng nhập đúng mã OTP gửi qua điện thoại để xác thực đăng nhập lần đầu trên một thiết bị/trình duyệt web.
2.  Hệ thống Điều hành tác nghiệp (ĐHTN) sẽ lưu trạng thái xác thực này và có hiệu lực duy trì đăng nhập trên trình duyệt đó trong vòng tối đa **30 ngày** mà không yêu cầu người dùng phải nhập lại mã OTP ở các lần truy cập tiếp theo (trừ khi người dùng chủ động nhấn Đăng xuất hoặc xóa bộ nhớ đệm trình duyệt).
