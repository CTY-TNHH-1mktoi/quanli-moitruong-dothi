# Ghi nhận nguồn

## Vietnamese Chatting Dataset

- Phát hành: MrCookieDev.
- Nguồn: https://huggingface.co/datasets/MrCookieDev/Vietnamese-Chatting-Dataset
- Commit: `9491ec151089c13a80a1bf901090c2365b1e4bda`.
- Tệp gốc: `hypermamba_data.jsonl`.
- Giấy phép công bố tại dataset card: Apache-2.0.

## Vietnamese Multi-turn Chat Alpaca

- Phát hành: 5CD-AI.
- Nguồn: https://huggingface.co/datasets/5CD-AI/Vietnamese-Multi-turn-Chat-Alpaca
- Commit: `3a1bef5b6681fe78eeaa25a97c4da1a2a1145a9e`.
- Tệp gốc: `vi_chatalpaca_cleaned.json`.
- Giấy phép công bố tại dataset card: Apache-2.0.

## Thay đổi của dự án

Chọn một phần dữ liệu, lọc theo quy tắc, bỏ định dạng in đậm và một số lời mở đầu; giữ tiền tố hội thoại gồm các lượt hoàn chỉnh; chuẩn hóa sang `messages`; thêm system prompt Xanh Non, metadata nguồn; chia train/validation theo nhóm. Không khẳng định mọi câu trả lời gốc đều đúng.

`knowledge.json` và các mẫu `environment_qa` được dự án biên soạn bằng tiếng Việt dựa trên các nguồn ghi trong từng mục; phân biệt nguồn kiến thức công khai với quy tắc riêng của ứng dụng.
