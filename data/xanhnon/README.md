# Dữ liệu Xanh Non

## Đã nạp

250 mẫu Vietnamese Chatting, 400 hội thoại Vietnamese Multi-turn, 118 mẫu môi trường nền, 101 mẫu luyện cách diễn đạt và 30 mẫu biện pháp tư vấn có nguồn: tổng 899 mẫu, gồm 812 train và 87 validation. Số lượng từng tập và nguồn nằm trong `manifest.json`. Chuẩn bị các mẫu mới không đồng nghĩa đã huấn luyện hay thay mô hình đang dùng.

- `train.jsonl`, `validation.jsonl`: dùng cho fine-tune, gồm `messages`, nguồn, mã nhóm và mức kiểm tra.
- `knowledge.json`: 26 chủ đề có nguồn, được chatbot tra cứu trực tiếp bằng `chat_knowledge.py`.
- `LICENSE-APACHE-2.0.txt`, `NOTICE.md`: giấy phép và ghi nhận dữ liệu gốc.

## Chất lượng và tách tập

Bộ lọc giữ tối đa ba lượt hỏi/đáp hoàn chỉnh và câu trả lời bên ngoài không quá 80 từ. Loại mẫu quá dài thay vì cắt ngang; loại danh tính chatbot khác, lời hứa thực hiện thao tác không có trong ứng dụng, một số chủ đề ngoài phạm vi và lỗi dịch dễ nhận biết. Ưu tiên ví dụ liên quan môi trường.

Các mẫu bên ngoài được lọc tự động, chưa được kiểm chứng từng câu. Chúng chỉ dùng luyện giao tiếp, không làm nguồn kiến thức môi trường trong RAG. Các biến thể cùng chủ đề, cùng nhóm tình huống AQI và hội thoại trùng cặp hỏi/đáp được giữ cùng tập. Mỗi nguồn đều có nhóm dành riêng cho validation.

Kiến thức môi trường tham khảo [AirNow AQI Basics](https://www.airnow.gov/aqi/aqi-basics/), [EPA/AirNow Particle Pollution Guide](https://www.airnow.gov/sites/default/files/2023-03/air-quality-guide-for-particle-pollution_0.pdf) và [EPA PM Basics](https://www.epa.gov/pm-pollution/particulate-matter-pm-basics). Các mục thiếu dữ liệu, địa điểm, thời gian và nguồn API là quy tắc ứng dụng, không gán thành kết luận của EPA.

Nhóm `environment_advice` bổ sung biện pháp từ EPA về bụi trong nhà, máy lọc, ẩm mốc và giảm rác; NIH/NIDCD về giảm tiếp xúc tiếng ồn; CDC về hoạt động trong thời tiết nóng. URL và nguồn của từng mẫu được ghi trong `knowledge.json` và `manifest.json`. 30 mẫu được giữ theo nhóm chủ đề: 25 train, 5 validation; các mẫu cũ giữ nguyên tập bằng `--preserve-split`.

## Tạo lại dữ liệu

Chạy từ thư mục dự án bằng PowerShell:

```powershell
.\.venv\Scripts\python.exe prepare_xanhnon_data.py
```

Script tải đúng commit ghi trong manifest; cache dữ liệu gốc và README nguồn tại `.runtime/xanhnon-data/raw/` (khoảng 70 MB). Sau lần đầu có thể dùng `--offline`. Chuẩn bị dữ liệu không tự cập nhật trọng số mô hình.

## Kiểm tra và huấn luyện

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-train.txt
.\.venv\Scripts\python.exe train_xanhnon.py
```

Lệnh trên chỉ kiểm tra tokenizer, nhãn assistant, giới hạn ngữ cảnh và tách tập; báo cáo tại `.runtime/xanhnon-data/preflight.json`. Với giới hạn token, chỉ giữ các lượt hoàn chỉnh vừa ngữ cảnh.

Để huấn luyện ứng viên LoRA trên safetensors gốc:

```powershell
.\.venv\Scripts\python.exe train_xanhnon.py --train --output .runtime/xanhnon-training/candidate-v1
```

Mặc định một lượt dữ liệu, LoRA rank 8 trên `q_proj`/`v_proj`, tích lũy gradient 4 mẫu. Tự dùng CUDA khi có, CPU float32 khi không có. Máy hiện tại không có CUDA nên chạy đầy đủ trên CPU có thể lâu; các tham số `--limit`, `--max-steps`, `--validation-limit`, `--max-length` cho phép chạy thử có giới hạn, được ghi rõ trong báo cáo.

Lượt luyện cách diễn đạt sử dụng `--last-layers 8`, chỉ học LoRA ở 8 lớp cuối (180.224 tham số). Loss chỉ tính ở vị trí token assistant cần dự đoán; cách tính đã được kiểm tra tương đương loss và gradient đầy đủ. `--checkpoint-every 20` lưu adapter mỗi 20 bước; tiến độ ghi ở `progress.json`. `--adapter PATH` cho phép học tiếp từ một adapter có sẵn với optimizer mới.

`--train-source environment_style` giới hạn lượt học tiếp vào các mẫu cách diễn đạt, giữ nguyên tập validation để so sánh. Khi thiếu RAM, `--allow-cpu-paging` cho phép CPU sử dụng bộ nhớ ảo nếu RAM và swap còn ít nhất 6 GiB; tốc độ có thể chậm hơn. Đây là tùy chọn riêng cho lúc train, không thay cấu hình chạy chatbot.

`xanhnon_style_data.py` tạo 86 ví dụ riêng, gồm diễn đạt ngắn, số đo giả lập có ngữ cảnh, thiếu dữ liệu, hội thoại tiếp nối và câu giới thiệu cố định khi ngoài chuyên môn. Số đo giả lập chỉ dùng làm ví dụ đầu vào, không thay dữ liệu giám sát hiện tại.

Adapter được lưu riêng kèm loss validation trước/sau và thời gian. Script không thay mô hình đang chạy. Loss giảm chưa chứng minh câu trả lời tốt hơn; cần đánh giá câu trả lời độc lập trước khi merge adapter, chuyển GGUF và cập nhật đường dẫn mô hình.

## Kiểm tra câu trả lời và phát hành

`evaluate_xanhnon.py` so sánh trực tiếp khả năng sinh câu trả lời của GGUF trên 11 câu hỏi hồi quy, không đi qua các câu trả lời tạo sẵn. `--through-app` kiểm tra cả luồng ứng dụng, gồm các câu trả lời từ dữ liệu và kiến thức đã kiểm chứng. Hai mô hình phải được so sánh cùng chế độ. Có cả số đo mới để kiểm tra việc đọc ngữ cảnh. Báo cáo giữ văn bản gốc, số từ, thời gian, thông tin bắt buộc và nội dung thừa. Nguyên văn các câu hỏi này không nằm trong tập train; một số chủ đề và số đo ví dụ trùng mẫu luyện. Bộ kiểm tra nhỏ này không đại diện cho mọi hội thoại.

`export_xanhnon.py` merge adapter sang một thư mục mới và dùng bộ chuyển đổi llama.cpp đi kèm để xuất GGUF F16. Sau khi đọc so sánh câu trả lời, tùy chọn `--activate --evaluation PATH` mới ghi `models/xanhnon-active.json`; ứng dụng đọc tệp này khi khởi động. Trọng số gốc được giữ nguyên. Backend Transformers sử dụng adapter tương ứng; biến môi trường cấu hình rõ ràng vẫn được ưu tiên.

Trong lúc huấn luyện, marker có PID và thời điểm tạo tiến trình giúp ứng dụng không khởi tạo thêm mô hình. Bảng điều khiển và các câu trả lời nhanh vẫn hoạt động; câu cần suy luận báo đang cập nhật. Marker của tiến trình đã kết thúc không chặn ứng dụng.

## Bản đã áp dụng ngày 19/10/2026

- Chặng hỗn hợp: giữ checkpoint 60 bước, 240 lượt mẫu; chưa chạy hết lượt 772 mẫu ban đầu.
- Chặng cách diễn đạt: học tiếp 21 bước trên toàn bộ 81 mẫu `environment_style` thuộc tập train, optimizer mới. Tổng cộng 81 bước và 321 lượt trình bày mẫu, có mẫu được học lại.
- Cùng 24 mẫu validation: loss gốc 2,03645 → checkpoint 60 là 1,88572 → bản tập trung 1,91189. Chọn bản tập trung theo kết quả hội thoại; loss của chặng này không tốt hơn checkpoint 60.
- Sinh tự do: model gốc 5/11, bản tập trung 8/11. Luồng ứng dụng với cùng quy tắc: model gốc 9/11, bản tập trung 11/11; trung bình 28,7 → 16,5 từ. Các quy tắc về AQI giả định, so sánh kích thước bụi và tiếp nối về phổi xử lý các lỗi còn lại của model.
- 103 kiểm thử phần mềm đạt. Mô hình gốc giữ nguyên; bản phát hành nằm tại `models/xanhnon-style-lora-v2`, GGUF mới tại `models/xanhnon-style-v2-f16.gguf`.
- Các file HF trung gian, GGUF checkpoint 60 và một phần cache tạm Git LFS được chuyển sang `D:\Codex-demoth1-intermediates-20261019` khi ổ C hết chỗ. Tệp cần để chạy ứng dụng vẫn ở thư mục dự án.
- Cache Git LFS của riêng repo được đặt tại `D:/Codex-demoth1-lfs-storage-20261019` qua cấu hình local `lfs.storage`. Các đối tượng LFS hiện có đã được sao chép vào vị trí này để tiếp tục dùng Git khi ổ C ít chỗ.

Tham khảo: [PEFT/LoRA](https://huggingface.co/docs/peft/main/en/conceptual_guides/lora), [Qwen2.5 SFT](https://qwen.readthedocs.io/en/v2.5/training/SFT/llama_factory.html).
