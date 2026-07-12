# Hướng dẫn Tích hợp Tri thức Thực tế từ Hội nghị Triển khai vào Cơ sở Tri thức RAG

Tài liệu này được biên soạn dành riêng cho **Người quản lý hệ thống RAG (RAG Administrator)**. Mục đích của tài liệu là chỉ rõ **vị trí cụ thể, phân cấp đề mục, và nội dung chi tiết** cần bổ sung, chỉnh sửa hoặc gộp từ tệp thoại đào tạo (*Hội nghị triển khai phần mềm Điều hành tác nghiệp của các cơ quan đảng_part1_clean.txt*) vào các tệp tri thức Markdown (.md) sẵn có của hệ thống. 

Phương pháp này giúp "làm giàu" cơ sở tri thức RAG bằng các **tri thức thực tế (implicit knowledge)**, logic hệ thống ngầm, mẹo xử lý lỗi và các cấu hình kỹ thuật đặc thù mà tài liệu hướng dẫn sử dụng (HDSD) lý thuyết bỏ sót, từ đó tối ưu hóa độ chính xác khi truy xuất của mô hình ngôn ngữ lớn (LLM).

---

## I. Tích hợp tri thức vào tệp "hdsd-vanbanden-rag.md" (Phân hệ Văn bản đến)

### Vị trí 1: Bổ sung Quy trình đăng ký thêm mới Văn bản đến (Văn bản giấy)
*   **Vị trí chèn**: Chèn vào cuối quy trình `### Quy trình đăng ký thêm mới Văn bản đến (Văn bản giấy)`, ngay sau bước hoàn tất đăng ký hiện tại.
*   **Đánh số thứ tự tiếp theo**: Thêm mục lưu ý quan trọng dưới dạng cảnh báo nghiệp vụ thực tế.
*   **Nội dung chèn**:

```markdown
*   **Cảnh báo lỗi nhận diện ngày tháng thực tế (Sự cố nhảy mốc thời gian tương lai do AI OCR):**
    *   **Nguyên nhân sự cố**: Khi Văn thư thực hiện quét (scan) văn bản giấy và tải tệp lên hệ thống, công nghệ nhận diện ký tự quang học tự động (AI OCR) sẽ tự quét và trích xuất thông tin ngày đến từ chữ viết tay trên văn bản. Nếu Văn thư viết tay ngày tháng quá sát nhau (ví dụ: viết số "3" của Tháng 3 chạm sát vào đường vạch chia dòng hoặc đường kẻ ngang), hệ thống AI OCR sẽ nhận diện nhầm số "3" thành số "8" (Tháng 8). 
    *   **Hậu quả**: Văn bản sau khi lưu sẽ tự động nhảy vào mốc thời gian tương lai (Tháng 8) và biến mất khỏi danh sách hiển thị hiện tại, khiến Văn thư lầm tưởng hệ thống bị mất tệp dữ liệu.
    *   **Giải pháp khắc phục cho Văn thư**: 
        1. Tại bộ lọc tìm kiếm thời gian "Ngày đến", điều chỉnh khoảng thời gian đến một mốc tương lai xa hơn (ví dụ: chuyển bộ lọc đến tháng tiếp theo hoặc cuối năm).
        2. Tìm kiếm văn bản bị nhận diện sai trong danh sách kết quả tương lai.
        3. Nhấp chọn biểu tượng "Chỉnh sửa" để sửa lại trường thông tin ngày đến một cách thủ công cho chính xác.
        4. Hướng dẫn Văn thư khi đóng dấu đến và viết tay ngày tháng cần viết rõ ràng, không chạm sát dòng kẻ để hệ thống AI nhận diện chuẩn xác nhất.
```

---

### Vị trí 2: Bổ sung Quy trình Chuyển xử lý văn bản đến (Phân quyền người dùng)
*   **Vị trí chèn**: Chèn vào phần lưu ý bảo mật hoặc cuối quy trình `### Quy trình chuyển xử lý văn bản đến`.
*   **Đánh số thứ tự tiếp theo**: Thêm phần lưu ý phân quyền cấu hình nhân sự.
*   **Nội dung chèn**:

```markdown
*   **Lưu ý quan trọng về Phân quyền vai trò Chuyên viên (Lỗi cấu hình Presiding Role):**
    *   **Quy tắc bất biến**: Khi người quản trị thực hiện phân quyền hoặc gán vai trò nhận văn bản đến đơn vị cho các Chuyên viên nghiệp vụ, tuyệt đối **không được tích chọn** vào ô đánh dấu "Chủ trì" (preside) đối với Chuyên viên nhận văn bản của đơn vị.
    *   **Lý do kỹ thuật**: Nếu tích chọn ô "Chủ trì", văn bản đến của đơn vị sẽ tự động nhảy vào mục lưu trữ cá nhân của chuyên viên đó. Lúc này văn bản sẽ được coi là tài liệu thuộc sở hữu cá nhân và sẽ đi theo tài khoản đó mãi mãi. Nếu chuyên viên này chuyển công tác hoặc rời khỏi đơn vị, đơn vị sẽ bị mất dấu luồng xử lý và không thể truy cập lại lịch sử văn bản cũ của đơn vị nữa.
    *   **Quy tắc phân phối chuẩn**: Quyền nhận văn bản đến đơn vị phải được gán ở cấp Đơn vị để đảm bảo tính kế thừa: bất kỳ chuyên viên nào được gán làm thành viên đơn vị đều có thể xem và xử lý. Khi nhân sự rời khỏi đơn vị, họ sẽ tự động mất quyền tiếp cận văn bản đơn vị đó, giúp bảo mật thông tin an toàn.
```

---

### Vị trí 3: Bổ sung Quy trình Xem chi tiết thông tin văn bản đến (Chính sách Bảo mật 204)
*   **Vị trí chèn**: Chèn vào cuối quy trình `### Quy trình xem chi tiết thông tin văn bản đến`, ngay dưới phần hướng dẫn xem biểu đồ và luân chuyển.
*   **Nội dung chèn**:

```markdown
*   **Chính sách Bảo mật và Lưu trữ Hạ tầng (Quy định 204 về việc xóa văn bản):**
    *   **Quy tắc xóa văn bản liên thông**: Đối với văn bản nhận liên thông trực tuyến gửi từ các cơ quan, đơn vị ngoài hệ thống, Văn thư có quyền thực hiện xóa bỏ nếu phát hiện lỗi hoặc chuyển nhầm đơn vị, vì tệp tin này là một bản sao được tải về máy chủ cục bộ.
    *   **Quy tắc xóa văn bản nội bộ**: Đối với văn bản nội bộ luân chuyển trực tiếp giữa các cơ quan đảng thuộc tỉnh trên cùng hệ thống, hệ thống **không cho phép xóa vĩnh viễn** văn bản này. Điều này nhằm tuân thủ nghiêm ngặt Kế hoạch bảo mật hạ tầng số 204 để tiết kiệm dung lượng cơ sở dữ liệu (DB), tối ưu hóa tài nguyên máy chủ vật lý và lưu vết lịch sử pháp lý của các cơ quan Đảng.
```

---

### Vị trí 4: Bổ sung Quy trình phê duyệt chỉ đạo Văn bản chờ xử lý (Ý kiến mẫu)
*   **Vị trí chèn**: Chèn vào bước 2 của quy trình `### Quy trình phê duyệt chỉ đạo Văn bản chờ xử lý` (Dành cho Lãnh đạo).
*   **Nội dung chèn**:

```markdown
*   **Mẹo thao tác nhanh bằng Ý kiến chỉ đạo mẫu trên thiết bị di động:**
    *   Để tiết kiệm thời gian gõ phím của Lãnh đạo khi duyệt văn bản nhanh trong các cuộc họp hoặc khi đang đi công tác, Lãnh đạo không cần nhập ý kiến chỉ đạo thủ công từ bàn phím.
    *   **Cách thực hiện**: Nhấp chọn nút "Ý kiến mẫu" ngay bên cạnh ô nhập liệu để hệ thống hiển thị danh sách các mẫu ý kiến chỉ đạo đã cấu hình sẵn (ví dụ: "Kính chuyển Đồng chí Phó Bí thư chỉ đạo thực hiện", "Giao Văn phòng chủ trì thực hiện trước ngày..."). Lãnh đạo chỉ cần thực hiện 3 lần nhấp chọn (3 clicks) trên màn hình máy tính bảng (iPad) hoặc điện thoại di động để hoàn tất phê duyệt chỉ đạo và gửi đi tức thời.
```

---

## II. Tích hợp tri thức vào tệp "hdsd-hosocanhan-rag.md" (Phân hệ Trang chủ & Hồ sơ cá nhân)

### Vị trí 1: Bổ sung Quy trình Đăng nhập hệ thống (OTP chuẩn 30 ngày)
*   **Vị trí chèn**: Chèn vào bước 1 của quy trình `### Quy trình Đăng nhập vào hệ thống Điều hành tác nghiệp (ĐHTN)`.
*   **Nội dung chèn**:

```markdown
*   **Quy tắc cấu hình bảo mật mật khẩu mặc định và lưu mã xác thực OTP:**
    *   **Thông tin tài khoản mặc định**: Khi cán bộ nhận bàn giao tài khoản mới từ người quản trị, thông tin mật khẩu mặc định bắt buộc là: `222222aA+` (bao gồm sáu số hai, một chữ cái "a" viết thường, một chữ cái "A" viết hoa và một dấu cộng "+"). Người dùng bắt buộc phải thay đổi mật khẩu này ngay trong lần đăng nhập đầu tiên để bảo mật tài khoản.
    *   **Quy định lưu OTP đăng nhập (Mốc 30 ngày)**: Trong lần đăng nhập đầu tiên hoặc khi đăng nhập trên thiết bị mới, hệ thống yêu cầu xác thực bằng mã OTP gửi về số điện thoại đăng ký SIM CA. Trạng thái xác thực OTP này sẽ được hệ thống tự động ghi nhớ và duy trì hiệu lực tối đa trong vòng **30 ngày**.
    *   **Lưu ý về trình duyệt**: Thời hạn 30 ngày này được áp dụng độc lập cho từng trình duyệt web. Nếu bạn đăng nhập bằng trình duyệt Google Chrome và xác thực OTP thành công, bạn sẽ không cần nhập lại OTP trên trình duyệt Chrome trong 30 ngày. Tuy nhiên, nếu bạn chuyển sang đăng nhập bằng trình duyệt Mozilla Firefox hoặc sử dụng chế độ ẩn danh, hệ thống sẽ yêu cầu xác thực lại OTP mới và tính mốc 30 ngày riêng cho trình duyệt đó.
```

---

## III. Tích hợp tri thức vào tệp "hdsd-quanlynhiemvu-rag.md" (Phân hệ Quản lý nhiệm vụ)

### Vị trí 1: Bổ sung Quy trình thêm mới nhiệm vụ công việc (Thiết lập KPI)
*   **Vị trí chèn**: Chèn vào bước 3 của quy trình `### Quy trình thêm mới nhiệm vụ công việc`, ngay dưới ô nhập liệu "Thời hạn hoàn thành".
*   **Nội dung chèn**:

```markdown
*   **Quy tắc đánh giá KPI dựa trên Thời hạn hoàn thành nhiệm vụ:**
    *   Khi giao nhiệm vụ, việc thiết lập trường "Thời hạn hoàn thành" (Deadline) là bắt buộc để hệ thống kích hoạt tính năng tự động đo lường hiệu suất công việc (KPI).
    *   **Trường hợp không thiết lập hạn xử lý**: Chuyên viên thực hiện nhiệm vụ sẽ mặc định luôn được tính là xử lý trong hạn (không bị tính chậm muộn KPI).
    *   **Trường hợp thiết lập hạn xử lý cụ thể**: Hệ thống sẽ tự động đối chiếu ngày báo cáo hoàn thành thực tế với hạn xử lý cấu hình để phân loại KPI:
        *   *Hoàn thành đúng hạn*: Báo cáo hoàn thành được phê duyệt trước hoặc đúng ngày hẹn.
        *   *Hoàn thành quá hạn*: Báo cáo hoàn thành được phê duyệt sau ngày hẹn.
        *   *Chưa xử lý quá hạn*: Nhiệm vụ đã vượt quá ngày hẹn nhưng Chuyên viên chưa cập nhật báo cáo hoàn thành.
    *   Bảng xếp hạng KPI này sẽ được hệ thống tự động tổng hợp vào mỗi ngày Thứ Bảy hàng tuần để báo cáo trực quan cho Lãnh đạo kiểm soát đơn vị nào hoàn thành xuất sắc và đơn vị nào đang chậm muộn công việc.
```

---

## IV. Tích hợp tri thức vào tệp "hdsd-quanlyhoso-rag.md" (Phân hệ Quản lý hồ sơ công việc)

### Vị trí 1: Bổ sung Quy trình xem chi tiết hồ sơ và quản lý tài liệu liên quan
*   **Vị trí chèn**: Chèn vào cuối quy trình `### Quy trình xem chi tiết hồ sơ và quản lý tài liệu liên quan`.
*   **Nội dung chèn**:

```markdown
*   **Quy tắc quản lý hồ sơ công văn lưu trữ theo chuẩn Thư viện Trung ương:**
    *   **Bắt buộc đếm tổng số trang**: Trước khi tiến hành kết thúc và đóng khóa một hồ sơ công việc trực tuyến trên hệ thống, người dùng bắt buộc phải kiểm tra, đếm tổng số trang tài liệu thực tế của toàn bộ các văn bản, phiếu trình đính kèm bên trong hồ sơ và nhập con số này vào trường "Tổng số trang" của biểu mẫu hồ sơ. Hệ thống sẽ tự động xác thực; nếu trường này bị bỏ trống hoặc bằng 0, hệ thống sẽ đóng băng và không cho phép thực hiện thao tác Đóng/Kết thúc hồ sơ.
    *   **Tự động tạo tệp biểu mẫu lưu trữ**: Khi hồ sơ được đóng thành công, hệ thống Điều hành tác nghiệp (ĐHTN) sẽ tự động biên dịch toàn bộ siêu dữ liệu (metadata) của hồ sơ để tự động tạo ra hai tệp văn bản chuẩn theo mẫu của Cục Văn thư Lưu trữ Trung ương bao gồm: **Bản mục lục hồ sơ công văn** và **Tờ kết thúc hồ sơ**. Người dùng phải đợi từ 1 đến 3 phút để hệ thống hoàn tất biên dịch tự động trước khi tải hai file biểu mẫu này về máy.
```

---

## V. Tích hợp tri thức vào tệp "hdsd-quantri-rag.md" (Phân hệ Quản trị hệ thống - Tạo mới hoặc Cập nhật)

*Nếu hệ thống chưa có tệp tri thức dành cho vai trò Quản trị viên (Admin), hãy tạo mới tệp tin **`hdsd-quantri-rag.md`** dựa trên tài liệu `HDSD_Quan_tri_Website.docx` kết hợp các nội dung cực kỳ đắt giá dưới đây:*

### Quy trình 1: Cấu hình danh sách người dùng và ảnh chữ ký số lãnh đạo
*   **Vị trí chèn**: Chèn vào mục thêm mới hoặc chỉnh sửa người dùng của vai trò Quản trị viên.
*   **Nội dung chèn**:

```markdown
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
```

---

### Quy trình 2: Quản lý và cấu hình ảnh con dấu đơn vị (Dấu mộc đỏ và Dấu đến)
*   **Vị trí chèn**: Chèn vào mục Quản lý ảnh con dấu đơn vị.
*   **Nội dung chèn**:

```markdown
### Quy trình quản lý và cấu hình kích thước chuẩn cho ảnh con dấu đơn vị
Mô tả: Hướng dẫn cấu hình kích thước hiển thị vật lý của con dấu cơ quan và con dấu xác nhận (dấu đến) trên hệ thống để đảm bảo tính thẩm mỹ và pháp lý của tài liệu điện tử.
Các bước thực hiện:
1. Truy cập menu "Quản trị" -> Chọn mục "Quản lý ảnh con dấu đơn vị".
2. Thực hiện tải lên ảnh con dấu đơn vị (ảnh mộc đỏ đã được scan sạch lỗi, tách nền trong suốt, định dạng đuôi `.png`).
3. **Quy chuẩn kích thước hiển thị (Kích thước vàng bắt buộc)**:
    *   **Ảnh con dấu cơ quan (Dấu tròn đỏ)**: Khi cấu hình ảnh con dấu đóng trên văn bản đi, Quản trị viên bắt buộc phải thiết lập thông số **Chiều cao chuẩn (Height) = 110**, Chiều rộng tự động co dãn theo tỉ lệ tương ứng. Đây là kích thước đã được chuẩn hóa để khi đóng lên tệp văn bản đi không bị đè đè chữ ký lãnh đạo và khớp với cỡ con dấu thực tế.
    *   **Ảnh con dấu xác nhận (Dấu chỉ ngày/tháng/số đến của Văn thư)**: Khi cấu hình con dấu xác nhận tiếp nhận văn bản giấy của Văn thư, Quản trị viên bắt buộc phải cấu hình chính xác kích thước hiển thị: **Chiều cao (Height) = 50** và **Chiều rộng (Width) = 680**. Kích thước này đảm bảo con dấu bao trọn toàn bộ chữ viết số đến và ngày tháng viết tay của Văn thư mà không bị vỡ ảnh hay che mờ văn bản gốc bên dưới.
```

---

### Quy trình 3: Cấu hình và chỉnh sửa Luồng luân chuyển văn bản (Workflow Nodes)
*   **Vị trí chèn**: Chèn vào mục Cấu hình luồng văn bản của menu Quản lý luồng.
*   **Nội dung chèn**:

```markdown
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
```

---

### Quy trình 4: Cấu hình sắp xếp thứ tự hiển thị nhân sự (Gán số thứ tự ưu tiên)
*   **Vị trí chèn**: Chèn vào mục cấu hình sắp xếp người dùng của menu Quản lý người dùng.
*   **Nội dung chèn**:

```markdown
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
```
