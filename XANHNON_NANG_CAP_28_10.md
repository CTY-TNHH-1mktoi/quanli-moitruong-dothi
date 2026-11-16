# Xanh Non — mục tiêu trước thứ Tư 28/10/2026

## Kết quả cần bàn giao

Một bản chatbot chạy được trong ứng dụng, có hội thoại minh họa và kết quả kiểm tra thực tế. Ưu tiên giao tiếp tự nhiên, hiểu hội thoại nhiều lượt và biết hỏi lại để tư vấn. Chưa làm đăng nhập hay cá nhân hóa.

## Tiêu chí chấp nhận

- Theo được chủ đề, địa điểm và thời điểm qua ít nhất ba lượt hỏi đáp, kể cả câu ngắn như “còn mai?”. Hỏi lại khi chủ đề thực sự chưa rõ.
- Dùng đúng nhiệt độ, độ ẩm, PM2.5/PM10 và AQI theo dữ liệu được cung cấp. Không tự tạo giá trị khi thiếu dữ liệu; không dùng dữ liệu hiện tại để khẳng định dự báo.
- Tư vấn có biện pháp thực hiện được; tôn trọng điều kiện người dùng đã nói, ví dụ chưa có máy lọc. Không đảo ngược lời khuyên về giảm tiếp xúc bụi hay tiếng ồn.
- Trả lời tiếng Việt ngắn, đúng câu hỏi; không chèn chỉ dẫn nội bộ, lời chào dài hoặc đoạn thừa về chỉ số người dùng không hỏi.
- Chạy được cả trả lời thường và trả lời theo luồng trong ứng dụng. Đo thời gian đến chữ đầu tiên, thời gian hoàn tất và bộ nhớ trên chính máy đang dùng.
- So sánh cùng câu hỏi, dữ liệu và điều kiện chạy với bản đang dùng; đọc lại câu trả lời, không chỉ dựa vào điểm kiểm tra tự động. Có một nhóm câu hỏi mới ngoài bộ phát triển nếu phương án vượt qua vòng đầu.

## Các mốc dự kiến

| Ngày | Kết quả cần có |
| --- | --- |
| 23–24/10 | Chốt đánh giá v15. Thử mô hình nền mạnh hơn, đo chất lượng và tài nguyên trước khi chọn. |
| 25/10 | Tích hợp phương án được chọn với ngữ cảnh hội thoại, dữ liệu theo địa điểm/thời điểm và tài liệu chuyên môn. |
| 26/10 | Có bản dùng thử trong ứng dụng, kiểm tra các hội thoại thực tế và sửa lỗi chính. |
| 27/10 | Kiểm tra hồi quy, hiệu năng, dữ liệu thiếu/cũ; đóng gói bản ổn định và cách quay lại bản trước. |
| 28/10 | Sử dụng bản đã chốt từ 27/10; không để việc nâng cấp chính sang ngày này. |

Các mốc là kế hoạch thực hiện, chưa phải kết quả đã đạt. Công việc nền chỉ tiếp tục khi tiến trình thực sự còn chạy trên máy; tài liệu này không tạo lịch tự chạy Codex.

## Hướng triển khai

1. Giữ nguyên ứng dụng đang dùng trong lúc đánh giá v15.
2. Không mở tiếp các lượt fine-tune nhỏ khi chưa xác định được lỗi và lợi ích đo được.
3. Chuẩn bị bản thử nghiệm Qwen3-4B-Instruct-2507 ở định dạng Q4_K_M. Đây là ứng viên, chưa phải mô hình đã chọn; phải kiểm tra tiếng Việt, tốc độ và RAM.
4. Dùng dữ liệu đo/dự báo và tài liệu có nguồn làm chứng cứ cho câu trả lời. Dữ liệu cảm biến lịch sử không được coi là dự báo hiện tại hay tự biến thành kiến thức tư vấn.
5. Chỉ tích hợp phương án vượt qua kiểm tra chất lượng. Lỗi nghiêm trọng về bịa số liệu, đơn vị hoặc lời khuyên an toàn phải được xử lý trước khi áp dụng.

## Nguồn mô hình thử nghiệm

- Mô hình gốc và giấy phép: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Bản GGUF do Unsloth phát hành: https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
- Revision GGUF cố định: `a06e946bb6b655725eafa393f4a9745d460374c9`.
- Tệp: `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2.497.281.120 byte.
- SHA-256 công bố trong metadata LFS: `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`.

Ứng viên có kết quả kiểm tra đầu ra trực tiếp tốt hơn v2 trên bộ phát triển, nhưng chưa đủ điều kiện thay thế bản chính; xem kết quả và giới hạn bên dưới.

## Kết quả đã xác minh ngày 23/10

- V15 hoàn tất 168/168 bước. Trong phép so sánh đầu ra mô hình trực tiếp với cùng profile `grounded-v15`, kiểm tra tự động đạt 40/48 so với v2 đạt 16/48. Đây không phải tỷ lệ chính xác của toàn ứng dụng.
- Có bốn trường hợp bị đánh dấu kém hơn v2. Khi đọc cả 48 đầu ra còn phát hiện bịa AQI khi dữ liệu thiếu và đảo ngược lời khuyên khép cửa lúc ngoài trời nhiều bụi. V15 bị loại, chưa kích hoạt.
- Báo cáo gốc: `D:/XanhNon-auto-training/meaning-review-v15-offline-20261023-retry1/`.
- Qwen3-4B Q4_K_M đã tải và kiểm tra đúng SHA-256. Đánh giá đủ 48 tình huống đạt tự động 42/48, có 2 trường hợp bị đánh dấu kém hơn v2. Đã đọc lại toàn bộ câu trả lời và lưu 8 vấn đề; ứng viên chưa sẵn sàng áp dụng.
- Bản trả lời rỗng ở câu 34 được giữ nguyên là thất bại; 33 câu trước đó được bảo toàn khi tiếp tục đánh giá, không sinh lại để thay kết quả.
- Phép thử nạp lại mô hình từng câu mất trung bình 49,1 giây cho 47 câu có thời gian được lưu; câu rỗng được giữ lại không có số đo thời gian Python. Đây chưa phải độ trễ của chatbot giữ mô hình sẵn trong bộ nhớ.
- Báo cáo ứng viên: `D:/XanhNon-auto-training/qwen3-4b-base-review-20261023-run2/`.
- Đã đo thông lượng CPU và Intel Iris Xe/Vulkan bằng runtime b11471 riêng: sinh token 2,54 so với 6,49 token/giây, GPU nhanh hơn khoảng 2,55 lần. Xử lý prompt 256 token đạt 85,28 so với 123,83 token/giây. Mỗi phép thử lặp hai lần, cùng hai luồng CPU. Báo cáo tại `D:/XanhNon-auto-training/qwen3-4b-hardware-20261023/`. Đây là phép đo tổng hợp sau nạp mô hình, chưa phải độ trễ chat trong ứng dụng.
- Đã đo ba tình huống qua HTTP nội bộ với mô hình được giữ sẵn trong bộ nhớ: GPU hiện chữ đầu sau 1,29–3,52 giây, hoàn tất sau 5,45–12,41 giây; CPU tương ứng 4,51–12,43 và 15,98–28,66 giây. Thời gian nạp GPU riêng là 40,80 giây. Báo cáo: `D:/XanhNon-auto-training/qwen3-4b-warm-chat-20261023/`. Đây chưa phải độ trễ qua Flask và bộ lọc đầu ra. CPU/GPU đều dùng ngữ cảnh 4096 token; phép thử nạp lại từng câu trước đó dùng 10240 token nên không thể quy toàn bộ chênh lệch cho GPU.

## Bản chạy thử ngày 24/10

- Đã mở ứng dụng thử tại http://127.0.0.1:5002 với Qwen3-4B Q4_K_M trên Intel Iris Xe/Vulkan. Cấu hình chỉ áp dụng cho tiến trình thử; tệp phát hành chính vẫn là v2, ứng dụng cổng 5000 tiếp tục chạy.
- 40 kiểm thử tích hợp/cấu hình đã qua: ngữ cảnh, hỏi lại, dữ liệu thiếu, trả lời theo luồng và cấu hình GPU. Chưa kiểm tra trực quan giao diện bằng trình duyệt.
- Sáu yêu cầu HTTP thực tế đều trả 200, gồm chào hỏi, chức năng, hỏi lại chủ đề chưa rõ, giảm bụi khi không có máy lọc, dự báo nối tiếp và một câu cần mô hình trả lời theo luồng. Đây là kiểm tra hoạt động có giới hạn, không phải tỷ lệ chính xác tổng thể.
- Câu “tư vấn mai thế nào” sau hội thoại thời tiết tại Phúc Yên đã lấy đúng dự báo Phúc Yên cho 25/10 từ Open-Meteo, không lặp lại số hiện tại trong lịch sử. Câu “mai thế nào” không có lịch sử hỏi lại thời tiết hay không khí.
- Câu cần mô hình “Vì sao gió yếu có thể khiến bụi khó phát tán?” hiện câu đầu sau 9,50 giây và hoàn tất sau 15,05 giây qua API ứng dụng. Bộ lọc phát câu hoàn chỉnh nên thời gian này khác số đo token trực tiếp. Đầu ra còn câu hỏi mời trao đổi thừa và cách diễn đạt chuyên môn cần kiểm tra thêm.
- Bốn câu chào hỏi/chức năng/hỏi lại/biện pháp giảm bụi được xử lý bằng logic có sẵn trong ứng dụng; kết quả này không chứng minh mô hình 4B tự học thêm những hành vi đó.
- Nhật ký và toàn bộ phản hồi: `D:/XanhNon-auto-training/qwen3-4b-app-preview-20261024/http-smoke-results.json`. Chưa thay thế bản chính, chưa mở lượt huấn luyện mới.

## Lượt LoRA 4B bắt đầu ngày 24/10, 02:06

- Theo yêu cầu train tiếp, đã chuẩn bị bản NF4 phục vụ huấn luyện, cùng mô hình gốc Qwen3-4B-Instruct-2507. Đây là định dạng và mức lượng tử khác GGUF Q4_K_M dùng để trả lời; phải kiểm tra đầu ra sau khi xuất adapter.
- Nguồn: `unsloth/Qwen3-4B-Instruct-2507-bnb-4bit`, revision `f12db89cd5156e090618dded9b4367f23f8f3b33`. SHA-256 trọng số: `f632ab95da1d8f307237094aca7c7dfa9e416b6d2f87bdd8ecda6dadfedb204d`. Đã xác minh trọng số, tokenizer và các tệp cấu hình.
- 64 mẫu train: 32 mẫu sửa lỗi giao tiếp/đơn vị/chủ thể/hỏi lại, 32 mẫu ôn tập có đáp án đã kiểm tra. 16 mẫu validation; thêm 8 câu xác nhận giữ ngoài SFT. Không chép nguyên câu hỏi từ bộ đánh giá vào train/validation. Đây là một lượt hiệu chỉnh nhỏ, chưa phải bằng chứng tăng độ chính xác.
- LoRA mới bắt đầu từ mô hình nền 4B; không tiếp tục các adapter 0.5B bị loại. Chỉ cập nhật q_proj/v_proj ở bốn lớp cuối, rank 8, một epoch, accumulation 4, learning rate 0,00002; dự kiến 16 bước. NF4 tính toán float32 trên CPU hai luồng; không dùng Vulkan để huấn luyện.
- Kiểm tra thực trên Qwen3 nhỏ đã xác nhận NF4 backward có gradient, optimizer thay đổi adapter và giữ trọng số nền cố định. Các kiểm tra khôi phục optimizer/RNG cũng đã qua.
- Có checkpoint adapter kèm optimizer/RNG sau mỗi bước. Worker ghi trạng thái tiến trình, lỗi và kết quả; không tự kích hoạt ứng viên. Loss validation trước/sau không phải độ chính xác câu trả lời.
- Nhật ký/trạng thái: `D:/XanhNon-auto-training/qwen3-4b-lora-cycle-20261024/`. Candidate: `D:/XanhNon-auto-training/qwen3-4b-lora-20261024/`.
- Tạm dừng bản thử cổng 5002 để nhường RAM. Bản chính cổng 5000 và tệp phát hành v2 giữ nguyên.

## Hoàn tất lượt LoRA và bắt đầu so sánh, 24/10

- Lượt huấn luyện hoàn tất lúc 07:02:19 (+07), đủ 16/16 bước và 64 mẫu. Thời gian trong trainer 17.640,6 giây, khoảng 4 giờ 54 phút. Đã lưu đủ 16 checkpoint và adapter cuối; không còn tiến trình train chạy.
- Loss trên cùng 16 mẫu validation giảm từ 5,2486206 xuống 5,1986803, khoảng 0,95%. Mức giảm nhỏ này chưa chứng minh chatbot trả lời tốt hơn.
- SHA-256 adapter safetensors: `1912ce87462898f93f1dfdb801af3ed88c0c85712fbb88b4023583e4cecf2dcb`.
- Xuất LoRA F16 GGUF thành công, SHA-256 `99a77a13e95761c1c3e39e8a1f18921d17f806e0f49a5070333a44510bf90287`. Converter llama.cpp b11471, commit `42b021b4dc42be573f1e1463528532fc8294c650`. Dùng cấu hình mô hình gốc không lượng tử; đã so khớp các chiều kiến trúc với cấu hình NF4. Bản xuất đầu với cấu hình NF4 bị converter từ chối; log lỗi được giữ lại.
- Đã nạp adapter trên GPU và sinh một câu thử thành công trong 9,51 giây (nạp mô hình riêng 15,83 giây). Câu thử lấy từ dữ liệu train nên chỉ xác nhận chạy được, không tính là bằng chứng tổng quát hóa.
- Bắt đầu so sánh đầu ra trực tiếp với cùng GGUF nền, GPU, prompt, tham số sinh và 56 tình huống: 48 câu phát triển và 8 câu mới giữ ngoài SFT. Mỗi tình huống chạy cả bản nền và bản có adapter. Giữ phản hồi rỗng/cắt cụt là lỗi, ghi toàn bộ đầu ra để đọc lại; không tự triển khai từ điểm tự động.
- Trạng thái/báo cáo: `D:/XanhNon-auto-training/qwen3-4b-lora-review-20261024/`. Bản chính vẫn v2; cổng 5002 tiếp tục tạm dừng để đủ RAM cho đánh giá.

## Kết quả so sánh và sửa ứng dụng, 24/10 buổi sáng

- LoRA 4B: 56/56 phản hồi trước và sau huấn luyện giống hệt nhau khi sinh tham lam trên GGUF Q4_K_M; cả hai đạt tự động 47/56. Đã xác nhận adapter có trọng số khác 0, được server nạp với scale 1. Lượt train không mang lại cải thiện đầu ra trong phép thử triển khai này; không áp dụng adapter. Không suy rộng rằng adapter không thể có tác dụng trong điều kiện khác.
- Đã đọc cả 56 phản hồi duy nhất và đối chiếu 112 đầu ra. Báo cáo: `qwen3-4b-lora-review-20261024/manual-answer-review.json` trong ổ lưu trữ D.
- Phát hiện lỗi bộ chuẩn bị ngữ cảnh: từ “Tôi” bị coi là “tối”; một số yêu cầu đọc số liệu lại không nhận được địa điểm/số liệu đã có. Đã sửa trong profile thử `grounded-v16`.
- Bản profile đầu có lỗi thay mất chứng cứ AQI giả định và sinh lời khuyên 10h–16h không có nguồn; đã dừng ở 23/64 câu. Toàn bộ đầu ra và mã đã đóng băng được giữ tại `qwen3-4b-profile16-review-20261024`.
- Bản sửa hẹp kiểm tra đủ 64 câu đạt tự động 59/64 so với 50/64, còn một lỗi hỏi lại chủ đề. Sau hai chỉnh sửa ngữ cảnh, kết quả tăng thành 60/64 và không có lỗi mới theo bộ kiểm tra tự động. Vòng cuối chỉ sinh lại hai câu có đầu vào thay đổi; 62 câu được dùng lại sau khi so khớp toàn bộ mảng tin nhắn. Không coi đây là một lượt chạy mới 64 câu.
- Cả 64 câu hiện là dữ liệu phát triển vì đã tham gia phân tích lỗi. Điểm trên không phải độ chính xác chuyên môn. Còn lỗi diễn đạt, giả định vị trí người dùng, nhãn nguồn số minh họa và một đoạn lẫn ký tự tiếng Trung; profile chỉ được mở để dùng thử riêng, chưa thay mô hình chính.
- Báo cáo cuối: `D:/XanhNon-auto-training/qwen3-4b-profile16-review-20261024-patch2/`.
- Đã áp dụng riêng các sửa đổi hội thoại vào ứng dụng chính cổng 5000: nhận lời gọi trợ lý tự nhiên hơn, giữ chủ đề sau lời gọi đó, giải thích vì sao cần hỏi thời điểm. 32 kiểm thử đã qua; HTTP JSON và SSE đã kiểm tra. Hai câu giao tiếp trả lời trong 0,03–0,06 giây; hỏi tiếp dự báo Hà Nội ngày mai đúng sau một lượt gọi trợ lý, mất 2,07 giây ở lần thử. Đây là số đo đơn lẻ.
- Tệp phát hành mô hình chính vẫn là v2, SHA-256 manifest `6e16a3c432e6440877e025f877530f9c3ad623d43c745016af028fcab2f78564`. Bằng chứng triển khai hội thoại: `D:/XanhNon-auto-training/app-dialogue-improvements-20261024/`.
- Đã mở lại bản 4B/profile v16 tại http://127.0.0.1:5002, kiểm tra trạng thái ready và HTTP/SSE thực tế. Câu mở cần mô hình hiện câu đầu sau 6,45 giây, hoàn tất 10,78 giây ở lần thử; không coi tốc độ hoặc câu trả lời này là bảo đảm cho câu khác. Nội dung giải thích chuyên môn mở vẫn cần bổ sung chứng cứ nguồn. Nhật ký: `D:/XanhNon-auto-training/qwen3-4b-app-preview-20261024-v16/`. Không có lượt train mới đang chạy.

## Lượt thử tín hiệu cập nhật v16, bắt đầu 24/10 lúc 10:17

- Theo yêu cầu train tiếp, đã mở worker mới tại `D:/XanhNon-auto-training/qwen3-4b-v16-signal-cycle-20261024/`. Trạng thái hiện hành nằm trong `D:/XanhNon-auto-training/current-training.json`; trạng thái lượt trước được lưu riêng, không ghi đè kết quả cũ.
- Chuẩn bị lại dữ liệu bằng profile v16. Những mẫu có nhiệm vụ/chứng cứ không khớp đáp án bị loại khỏi tập được chọn; các câu giải thích lý do hỏi thời điểm được viết lại để giữ đúng chủ thể và thông tin đã biết. Nhật ký kiểm tra từng mẫu: `qwen3-4b-v16-signal-data-20261024/alignment-audit.json`.
- Đây là pilot nhỏ: 16 mẫu train bao phủ 16 chủ đề, 4 mẫu validation. Đã xác nhận cả 20 hội thoại nằm trọn trong giới hạn token; không có mẫu bị cắt. Giữ ngoài SFT 24 tình huống trả lời: 16 tình huống phát triển và 8 cách hỏi mới, toàn bộ đầu vào/tiêu chí đóng băng trước khi train. Các khái niệm vẫn liên quan dữ liệu phát triển, không phải bộ kiểm định chuyên gia độc lập.
- Bắt đầu adapter mới từ nền NF4, không nạp adapter bị loại. q_proj/v_proj bốn lớp cuối, rank 8, learning rate 0,0003, accumulation 2, một epoch, tổng 8 bước. Learning rate cao gấp 15 lần lượt trước là một giả thuyết thử nghiệm, chưa chứng minh tốt hơn. Lưu đầy đủ checkpoint và optimizer/RNG sau mỗi bước.
- Huấn luyện CPU hai luồng; cho phép Windows dùng bộ nhớ ảo khi RAM sát ngưỡng, kiểm tra còn đủ RAM+swap trước khi nạp. Bản thử cổng 5002 tạm dừng để nhường bộ nhớ; ứng dụng chính cổng 5000 vẫn chạy.
- Sau khi train, worker tự xuất LoRA GGUF và sinh cả bản nền/bản có adapter với đúng 24 đầu vào đã đóng băng, cùng runtime GPU, tham số và thang chấm. Nếu đầu ra không thay đổi hoặc xuất hiện hồi quy sẽ ghi rõ; không triển khai từ loss hoặc điểm tự động. Vẫn cần đọc câu trả lời trước khi quyết định áp dụng.
- 17 kiểm thử dữ liệu/rubric/profile đã qua trước khi mở worker. Chưa có kết quả train hoặc cải thiện đầu ra của lượt này tại thời điểm bắt đầu.

## Kiểm tra hoàn tất pilot v16, 24/10 lúc 11:58–12:00

- Hoàn tất đủ 8/8 bước, 16 mẫu train và 8 checkpoint có optimizer/RNG. Thời gian trainer 3.914,9 giây (khoảng 65 phút, có đo validation trước/sau). Không còn tiến trình train hay đánh giá chạy.
- Loss validation 4,4884593 xuống 3,7918609 (giảm 15,52%). Phép so sánh đầu ra hoàn tất lúc 11:34:41: cả hai bản đạt tự động 21/24; 9/24 phản hồi thô thay đổi. Mức cập nhật đã tác động đến đầu ra triển khai, nhưng chưa chứng minh tăng chất lượng tư vấn.
- Đã đọc đủ 24 cặp phản hồi và xem chứng cứ liên quan. Bản mới chỉ lặp câu gọi trợ lý kèm emoji; thêm ánh sáng vào lời giải thích lý do hỏi thời điểm; thêm mốc thử lại sau vài giờ không có căn cứ. Hai thay đổi còn lại chủ yếu rút ngắn câu hoặc đổi dấu câu. Rubric cũ không phát hiện đủ các vấn đề trên.
- Quyết định: `rejected_new_dialogue_regressions`. Giữ adapter/kết quả để phân tích, không áp dụng và không tự mở rộng cùng công thức chỉ vì loss giảm. Báo cáo đọc tay: `D:/XanhNon-auto-training/qwen3-4b-v16-signal-cycle-20261024/answer-review/manual-answer-review.json`.
- Bản chính vẫn v2. Điểm 21/24 là kết quả tự động gốc, không chỉnh lại lịch sử sau khi phát hiện lỗi rubric. Bộ kiểm tra cho lượt sau được bổ sung phát hiện lặp câu hỏi, nhận nhầm vị trí vật lý từ địa điểm đang chọn và hai chi tiết vượt chứng cứ đã quan sát.

## Lượt sửa hội thoại v16, bắt đầu 24/10 lúc 12:26

- Theo yêu cầu train tiếp, đã mở adapter mới từ nền NF4 đã xác minh, không tiếp tục adapter pilot bị loại. Candidate: `D:/XanhNon-auto-training/qwen3-4b-v16-repair-lora-20261024/`; worker và log: `D:/XanhNon-auto-training/qwen3-4b-v16-repair-cycle-20261024/`.
- 48 mẫu train gồm 24 mẫu mới sửa lời gọi trợ lý, giải thích lý do hỏi thời điểm, xử lý AQI thiếu và đọc đúng địa điểm/số liệu; thêm 24 mẫu ôn tập thuộc 12 chủ đề còn lại. Có 8 mẫu validation riêng. Tổng cộng 16 chủ đề train, không cắt bớt hội thoại để vừa token.
- Khi đọc bản nháp đã phát hiện nhánh giải thích AQI thiếu không đưa tên địa điểm vào đầu vào mô hình; đáp án nháp lại có tên từ snapshot ẩn. Bản được chọn loại tên không có chứng cứ. Thư mục train chính xác là `qwen3-4b-v16-repair-data-20261024-reviewed`; thư mục không có hậu tố reviewed chưa được sử dụng để train. Các câu hỏi/đầu vào đánh giá vẫn giữ nguyên SHA-256 khi sửa tập train.
- Mở rộng LoRA từ q_proj/v_proj sang q_proj/v_proj/o_proj/gate_proj/up_proj/down_proj ở bốn lớp cuối. Rank 8, learning rate 0,0001, accumulation 4, một epoch, tổng 12 bước; CPU NF4 float32 hai luồng, checkpoint có optimizer/RNG sau mỗi bước. Thay đổi phạm vi cập nhật là thử nghiệm, chưa có bằng chứng cải thiện đầu ra.
- Đã kiểm tra backward trên Qwen3 NF4 nhỏ: cả sáu nhóm projection có trọng số adapter thay đổi, mô hình nền đóng băng; xuất GGUF đủ 12 tensor LoRA cho một lớp. Các kiểm tra khôi phục checkpoint và dữ liệu/rubric đã qua; bốn kiểm tra dữ liệu mới được chạy lại sau khi sửa tên địa điểm không có trong chứng cứ.
- Đóng băng trước train 80 tình huống trả lời: 72 tình huống phát triển đã dùng trước đó và 8 cách hỏi mới. Không đưa câu hỏi/lịch sử của bộ đánh giá vào SFT. Đây không phải bộ kiểm định chuyên gia độc lập.
- Sau train, worker tự sinh cả bản nền và bản có adapter với cùng đầu vào/tham số trên GPU, xác nhận adapter thật sự được server nạp với scale 1, lưu phản hồi thô và so sánh hồi quy. Việc triển khai vẫn cần đọc lại câu trả lời; loss thấp hơn không đủ để áp dụng.
- Bản chính cổng 5000 tiếp tục chạy. Bản thử cổng 5002 tạm dừng để nhường RAM. Worker có trạng thái thực, kèm trình theo dõi mỗi 30 giây trong tối đa 8 giờ; không tạo lịch tự đánh thức Codex.
- Xác minh lúc 12:28:51: worker còn sống, trainer thực đang chạy, giai đoạn baseline validation, 0/12 bước cập nhật. Có 1.720.320 tham số adapter được phép học; cả 48/48 mẫu train và 8/8 mẫu validation được mã hóa trọn vẹn. API trạng thái chatbot bản chính trả `training` trong thời gian huấn luyện; không coi đây là trạng thái chat sẵn sàng. Trang giám sát tiếp tục được phục vụ.

## Kết quả lượt sửa hội thoại v16, 24/10

- Train hoàn tất đủ 12/12 bước và 12 checkpoint; thời gian trainer 8.800,5 giây, khoảng 2 giờ 27 phút. Loss validation 5,0774137 xuống 4,2218414. Không coi mức giảm này là độ chính xác câu trả lời.
- Hoàn tất so sánh đủ 80 cặp đầu ra lúc 15:13:01: điểm tự động bản nền 68/80, adapter 67/80, có 34 phản hồi thô thay đổi. Hai câu chuyển từ đạt sang không đạt; hai câu vốn đã không đạt có thêm vi phạm mới.
- Đã đọc cả 80 cặp phản hồi. Có cải thiện nhỏ về độ gọn ở một số câu đọc số liệu và xử lý dữ liệu thiếu, nhưng vẫn có lặp câu hỏi, thêm ánh sáng/mốc thử lại không có trong chứng cứ, nhầm địa điểm đang chọn với nơi người dùng ở, lẫn ký tự tiếng Trung và diễn đạt quá rộng so với hướng dẫn nguồn.
- Bộ chấm còn hạn chế: mất dấu hỏi và thiếu từ khóa không đồng nghĩa mất toàn bộ ý nghĩa câu trả lời. Đọc tay ghi rõ các trường hợp này; giữ nguyên kết quả tự động gốc để tránh chỉnh điểm sau khi biết đầu ra.
- Quyết định `rejected_no_overall_gain_and_grounding_regressions`: không áp dụng adapter, không tự mở thêm lượt train cùng công thức. Báo cáo đầy đủ: `D:/XanhNon-auto-training/qwen3-4b-v16-repair-cycle-20261024/answer-review/manual-answer-review.json`. Hướng tiếp theo là xử lý độ bám nguồn và ngữ cảnh trước khi lặp lại fine-tune.
- Không còn tiến trình train hoặc đánh giá chạy. Bản chính giữ v2; mở lại bản 4B/profile v16 không có adapter bị loại tại cổng 5002.

## Nâng cấp luồng hội thoại đã áp dụng, 24/10

- Sau phản hồi rằng train chưa đem lại nâng cấp sử dụng được, không mở thêm lượt train. Tái hiện lỗi trực tiếp qua HTTP: hỏi vì sao cần biết giờ lại nhận tư vấn AQI; hỏi còn Đà Nẵng thì sao bị trả lời ngoài phạm vi.
- Đã sửa nhận diện câu hỏi ngày giờ đang chờ với nhiều cách diễn đạt; lời cảm ơn/gọi trợ lý không làm mất câu hỏi đang chờ. Lời hỏi vì sao giờ được giải thích trực tiếp, không đọc AQI thay thế.
- Ghi nhớ giờ cụ thể khi người dùng bổ sung ngày. Ví dụ nói 18h30 rồi trả lời ngày mai sẽ dùng dự báo của ngày mai trong khung 18:00–19:00, phù hợp độ phân giải theo giờ của nguồn. Đổi lại sang bây giờ sẽ bỏ mốc giờ cũ.
- Câu đổi địa điểm ngắn giữ chủ đề và ngày đã hỏi. Thời tiết/không khí ở địa điểm mới được lấy đúng nguồn theo tọa độ của địa điểm đó, không lấy số của địa điểm đang chọn trên bảng. Không đổi địa điểm của dashboard. Câu hỏi ngoài chuyên môn xen vào sẽ kết thúc ngữ cảnh cũ.
- Tách tên địa điểm khỏi từ mô tả điều kiện: Đà Nẵng không còn bị hiểu thành từ nắng sau khi bỏ dấu. Nhận diện địa điểm theo danh sách có sẵn; chưa phải dịch vụ tìm mọi địa danh.
- 58 kiểm thử qua, gồm 9 kiểm thử mới cho các lỗi thực và nguồn số liệu; đã kiểm tra JSON/SSE. Khởi động lại cả cổng 5000 và bản thử 5002 để nạp mã mới.
- 7 lượt HTTP thực qua trên cổng 5000: câu hỏi lý do 0,043 giây thay vì trả nhầm AQI mất 3,402 giây ở lần đo trước; câu đổi địa điểm hiện tại lấy đúng số Open-Meteo ở Đà Nẵng trong 2,553 giây; đổi địa điểm giữ ngày mai 0,072 giây; giữ giờ khi bổ sung ngày trả dự báo đúng khung 18:00–19:00. Đây là số đo từng lần, không bảo đảm độ trễ mọi câu hỏi.
- Cả hai ứng dụng báo ready. Trọng số phát hành chính vẫn giữ nguyên; lợi ích này đến từ sửa cách xử lý hội thoại và đọc dữ liệu. Bằng chứng, mã trước/sau và phản hồi HTTP: `D:/XanhNon-auto-training/app-context-upgrade-20261024/`.

## Đổi chỉ số và giờ trong hội thoại, đã áp dụng 24/10 lúc 19:33

- Tái hiện qua HTTP: sau câu hỏi nhiệt độ Đà Nẵng ngày mai lúc 18h, câu còn độ ẩm bị chuyển về số cũ Hà Nội; còn AQI trả về hiện tại; đổi sang 19h bị trả lời ngoài phạm vi.
- Đã bổ sung giữ địa điểm, ngày và giờ khi đổi ngắn giữa nhiệt độ, độ ẩm, thời tiết và US AQI. Chỉ số mới lấy từ nguồn tương ứng; không lấy số trong câu trả lời trước. Đổi sang ngày kia hoặc sang thành phố khác tiếp tục dùng đúng chỉ số và giờ đang trao đổi.
- Nhận thêm cách đổi giờ như đổi sang 19h, vậy 19h thì sao, chuyển sang 19:00 giúp mình. Giữ ngày cũ, thay giờ cũ. Câu hiện tại bỏ ngày và giờ dự báo trước đó. Chọn cả thời tiết và AQI hoặc trả lời câu hỏi làm rõ chủ đề đều giữ được giờ cụ thể; trước đây chuẩn hóa dấu câu có thể làm mất dấu hai chấm của giờ.
- Nếu đã có giờ nhưng thiếu ngày, hỏi một câu ngắn về ngày thay vì trả số hiện tại. Không kế thừa giả định, định nghĩa, số đo người dùng tự nêu hoặc chủ đề đã bị ngắt bởi yêu cầu không liên quan.
- 137 kiểm thử qua trong 14 mô-đun, gồm 11 kiểm thử mới. Một kiểm thử cũ được cập nhật để xác nhận truy vấn địa điểm mới lấy số riêng từ nguồn thay vì bắt buộc từ chối; số giả lập khác hẳn số của địa điểm đang chọn. Điểm kiểm thử không phải độ chính xác chuyên môn tổng quát.
- Đã khởi động lại cổng 5000 và 5002, cả hai báo ready. Kiểm tra 9 lượt HTTP trên bản chính, gồm JSON/SSE, và 1 lượt trên bản thử. Đọc độc lập lại nguồn Open-Meteo/CAMS khớp số trong câu trả lời. Các câu truy vấn đã có cache mất khoảng 0,036–0,135 giây; lượt đầu thời tiết 1,202 giây, AQI 3,896 giây. Đây là số đo từng lần.
- Bằng chứng: `D:/XanhNon-auto-training/app-reading-followups-20261024/`, gồm mã trước/sau, diff, log kiểm thử, phản hồi HTTP và đối chiếu nguồn. Manifest mô hình chính vẫn cùng SHA-256; không có adapter train mới được áp dụng và không mở lượt train mới trong lần sửa này.
- Giới hạn: chuyển chỉ số mới hiện bao phủ bốn nhóm nêu trên; dự báo theo giờ và địa điểm trong danh sách hiện có, phụ thuộc khả năng cung cấp dữ liệu của nguồn. Các câu tư vấn mở ngoài những nhánh đã kiểm chứng vẫn cần đánh giá tiếp.
