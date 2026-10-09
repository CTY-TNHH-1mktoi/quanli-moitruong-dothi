# Mô hình và tích hợp AI

Bản nháp tham khảo, chuẩn bị 10/10/2026. Người dự kiến rà soát: Trần Trọng Nghĩa. Đầu ra sau rà soát: `docs/ai/MODEL_CARD.md`.

## Random Forest

Artifact hiện có: `environment_rf.joblib`; code nạp: `environment_predictor.py`; script huấn luyện tham khảo: `train_environment_rf.py`. Bundle chứa hai bộ phân loại không khí/tiếng ồn.

| Thứ tự | Feature mô hình | Trường dữ liệu | Đơn vị |
|---|---|---|---|
| 1 | `pm25` | `PM25` | µg/m³ |
| 2 | `pm10` | `PM10` | µg/m³ |
| 3 | `temperature_c` | `NhietDo` | °C |
| 4 | `humidity_pct` | `DoAm` | % |
| 5 | `noise_db` | `TiengOn` | dBA, giá trị NoiseCapture tổng hợp |

Thiếu/nonfinite một feature → `TrangThai: thieu_du_lieu` và danh sách trường thiếu; đủ chỉ số mới dự đoán. Nhãn RF tham khảo được trình bày riêng với US AQI của Open-Meteo.

Script huấn luyện hiện dùng iSCAPE và nhãn quy tắc: PM2.5 ≤12 / ≤35.4 / ≤150 / >150; tiếng ồn <55 / <70 / ≥70. Đây không phải nhãn chuyên gia hay AQI chính thức. Nguồn huấn luyện châu Âu khác nguồn suy luận ở Việt Nam. Metadata đánh giá của artifact gốc chưa được cung cấp, nên chưa kết luận accuracy/F1 của artifact đó. Script huấn luyện có thể tạo metadata khi chạy lại nhưng sẽ ghi đè mô hình; lượt rà soát này chỉ kiểm tra mô hình đã có.

## Chatbot Xanh Non

Trọng số người dùng cung cấp thuộc Qwen2.5 0.5B Instruct tiếng Việt. Bản gốc `models/xanhnon-qwen2.5-0.5b-vietnamese/`; bản chuyển đổi F16 `models/xanhnon-f16.gguf`. Các thư mục lớn được chia sẻ riêng theo README.

- Backend ưu tiên llama.cpp CPU; fallback Transformers khi cấu hình phù hợp.
- Tokenizer/chat template của mô hình; ngữ cảnh gồm nơi đang chọn, số đo và trường thiếu.
- Mặc định `CHATBOT_MAX_NEW_TOKENS=-1`: sinh đến EOS; context shift giữ đầu vào và token gần nhất. Không có timeout cắt phản hồi theo thời gian.
- SSE gửi từng đoạn; dừng chủ động hoặc mất kết nối kết thúc phần sinh đang chạy. Một lượt sinh tại một thời điểm; yêu cầu khác có thể nhận 429.
- Lịch sử/địa điểm được tách ở UI; ngữ cảnh câu mới phải đúng nơi. Hội thoại hiện lưu trong bộ nhớ trang, không lưu SQL.

## Cần kiểm chứng và ghi rõ

1. RF đủ 5 trường và thiếu tiếng ồn; đối chiếu trạng thái, không điền dữ liệu nơi khác.
2. Kiểm thử streaming/Unicode/lượt bận/tiếp tục tới EOS bằng `test_chat_stream.py`.
3. Trên máy đủ mô hình, chọn một nơi và hỏi tên nơi, PM2.5, tiếng ồn; đối chiếu snapshot mới nhất.
4. Ghi thời gian nhận chữ đầu/hoàn tất nếu đã đo; phân biệt kết quả mock và model thật.
5. Nêu giới hạn: LLM có thể trả lời sai, RF minh họa, mô hình không khí là CAMS, tiếng ồn không phải số đo trực tiếp thời gian thực.

Ghi kết quả kiểm chứng ở `docs/ai/TEST_RESULT.md`.
