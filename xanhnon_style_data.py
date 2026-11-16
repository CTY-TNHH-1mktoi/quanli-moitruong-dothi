"""Project-authored conversational examples; readings are synthetic snapshots."""

OUTSIDE_REPLY = "Chào, tôi là chat bot môi trường xanh non tôi có thể giúp gì cho bạn"


def style_records(make_record):
    records = []

    def add(group, messages, sources=("project",)):
        records.append(make_record(messages, "environment_style", group,
                                   source_ids=list(sources), review="source_checked_project_examples",
                                   synthetic_snapshot=True))

    places = [("Hà Nội", 24.8, 95, 175), ("Đà Nẵng", 29, 70, 45),
              ("Thành phố Hồ Chí Minh", 31.5, 78, 82), ("Cần Thơ", 28, 84, 125),
              ("Hải Phòng", 22, 90, 200), ("Nha Trang", 25, 80, None)]
    for place, temperature, humidity, aqi in places:
        context = (f"Dữ liệu bảng giám sát do ứng dụng cung cấp:\nĐịa điểm đang chọn: {place}.\n"
                   f"Nhiệt độ: {temperature:g} °C; Độ ẩm: {humidity:g}%; "
                   + (f"US AQI: {aqi}; " if aqi is not None else "US AQI: chưa có dữ liệu; ")
                   + "Tiếng ồn: 72 dBA (tổng hợp khu vực).\n\nCâu hỏi của người dùng:\n")
        pairs = [
            (f"Thời tiết ở {place} giờ thế nào bạn?", f"Ở {place} hiện {temperature:g} °C, độ ẩm {humidity:g}%."),
            (f"Cho mình biết thời tiết {place} lúc này nhé.", f"{place} đang ở mức {temperature:g} °C, độ ẩm {humidity:g}%."),
            ("Tóm tắt thời tiết hiện tại cho mình với.", f"Ở {place} hiện {temperature:g} °C, độ ẩm {humidity:g}%."),
            ("Giờ nhiệt độ bao nhiêu vậy?", f"Hiện ở {place} là {temperature:g} °C."),
            ("Nói mỗi nhiệt độ thôi nhé.", f"Nhiệt độ hiện tại ở {place} là {temperature:g} °C."),
            ("Độ ẩm đang bao nhiêu bạn?", f"Độ ẩm ở {place} hiện là {humidity:g}%."),
            ("Mình chỉ cần số độ ẩm hiện tại.", f"Hiện độ ẩm ở {place} là {humidity:g}%."),
        ]
        for question, answer in pairs:
            add("weather_" + place, [{"role": "user", "content": context + question},
                                      {"role": "assistant", "content": answer}])

    missing = [
        ("AQI", "Không có AQI nhưng có nhiệt độ 25 °C và độ ẩm 80%.",
         "Không khí lúc này có ổn để ra ngoài không?",
         "Mình chưa có AQI nên chưa đủ dữ liệu để đánh giá không khí. Bạn cập nhật bảng giám sát giúp mình nhé."),
        ("weather", "Nhiệt độ và độ ẩm đều chưa có. US AQI là 75.",
         "Bạn xem giúp mình thời tiết hiện tại nhé.",
         "Mình chưa có số liệu thời tiết ở đây. Bạn cập nhật dữ liệu rồi mình xem tiếp nhé."),
        ("humidity", "Nhiệt độ 26 °C. Độ ẩm chưa có. Tiếng ồn 70 dBA.",
         "Độ ẩm bây giờ bao nhiêu vậy?",
         "Mình chưa có số đo độ ẩm hiện tại. Bạn thử cập nhật bảng giám sát nhé."),
        ("weather_partial", "Nhiệt độ 26 °C. Độ ẩm chưa có. US AQI chưa có.",
         "Thời tiết giờ thế nào bạn?", "Hiện nhiệt độ là 26 °C."),
    ]
    for group, data, question, answer in missing:
        for prefix in ("", "Bạn trả lời ngắn giúp mình: "):
            add("missing_" + group, [
                {"role": "user", "content": f"Dữ liệu bảng giám sát: {data}\nCâu hỏi của người dùng:\n{prefix}{question}"},
                {"role": "assistant", "content": answer},
            ])

    facts = [
        ("aqi", ["AQI là cái gì vậy bạn?", "Mình mới dùng app, giải thích AQI dễ hiểu với."],
         "Bạn có thể hiểu AQI là chỉ số cho biết không khí đang sạch hay ô nhiễm đến mức nào. Số càng cao thì mức lo ngại đối với sức khỏe càng lớn.", ("airnow_aqi",)),
        ("pm25", ["Nghe bụi mịn hoài mà mình chưa rõ nó là gì.", "PM2.5 là loại bụi như thế nào bạn nhỉ?"],
         "PM2.5 là những hạt bụi rất nhỏ, thường có đường kính không quá 2,5 micromet. Vì nhỏ như vậy, chúng có thể đi sâu vào phổi.", ("epa_pm",)),
        ("pm10", ["PM10 khác bụi mịn ở chỗ nào?", "Phân biệt hai loại bụi PM2.5, PM10 cho dễ hiểu nhé."],
         "Hai tên này phân biệt theo kích thước hạt bụi: PM2.5 thường không quá 2,5 µm, còn PM10 không quá 10 µm. PM2.5 nhỏ hơn và có thể đi sâu vào phổi.", ("epa_pm",)),
        ("units", ["Số bụi là 40 thì AQI cũng 40 đúng không?", "Mình đang nhầm số PM2.5 với AQI, giải thích ngắn với."],
         "Hai số đó khác nhau nhé. PM2.5 là nồng độ bụi, thường tính bằng µg/m³; AQI là chỉ số được quy đổi theo một thang đánh giá, nên không thể lấy số này thay số kia.", ("epa_pm", "airnow_aqi")),
        ("sources", ["Sao lại có bụi mịn trong thành phố?", "Bụi này thường phát sinh ở đâu vậy?"],
         "Bụi có thể đến từ công trường, đường bụi, hoạt động đốt và khí thải. Một phần bụi mịn còn hình thành trong không khí từ các chất ô nhiễm do giao thông, công nghiệp thải ra.", ("epa_pm",)),
        ("sensitive", ["AQI nói nhóm nhạy cảm là đang nhắc đến ai vậy?", "Ai cần chú ý hơn khi bụi mịn tăng bạn nhỉ?"],
         "Đó là những người dễ bị ảnh hưởng hơn, như người có bệnh tim hoặc phổi, trẻ em, người cao tuổi, người mang thai và người làm việc ngoài trời. Các nhóm này cần chú ý hơn khi AQI tăng.", ("airnow_particles",)),
        ("indoor", ["Vào nhà là tránh hết bụi mịn chưa?", "Mình ở trong nhà thì có còn gặp bụi mịn không?"],
         "Vẫn có thể có bụi trong nhà, từ ngoài trời lọt vào hoặc từ các nguồn như khói thuốc, nến và bếp đốt. Giảm nguồn phát bụi và dùng máy lọc phù hợp có thể giúp không khí trong phòng tốt hơn.", ("airnow_particles",)),
        ("filter", ["Máy lọc có xử lý được bụi trong phòng không bạn?", "HEPA giúp gì cho không khí trong nhà vậy?"],
         "Bộ lọc HEPA có thể giúp giảm hạt bụi trong phòng. Hiệu quả còn tùy thiết bị, diện tích phòng và nguồn phát bụi; dùng máy lọc không có nghĩa là không khí hoàn toàn sạch.", ("airnow_particles",)),
        ("missing", ["Ô AQI trống thì xem như bằng không được không?", "Chưa thấy số AQI có nghĩa không khí đang tốt à?"],
         "Chưa có số đo không có nghĩa là bằng 0 hoặc không khí đang tốt. Mình cần AQI hợp lệ của đúng địa điểm, thời gian mới đánh giá được.", ("project",)),
        ("forecast", ["Nhìn AQI lúc này có biết được tối mai không?", "Bạn có đoán AQI ngày sau từ số hiện tại được không?"],
         "Chỉ từ số hiện tại thì mình chưa thể kết luận cho ngày mai. Cần có dữ liệu dự báo đúng địa điểm và thời gian bạn muốn xem.", ("project",)),
        ("location", ["Lấy số ở Hà Nội nhận xét cho Đà Nẵng được chứ?", "Số đo nơi khác có dùng cho chỗ mình được không?"],
         "Không nên dùng thay như vậy vì chất lượng không khí thay đổi theo vị trí và thời gian. Bạn chọn đúng địa điểm trên bảng giám sát rồi mình xem theo số liệu ở đó nhé.", ("project",)),
        ("weather_air", ["Thấy trời mát thì chắc là không khí sạch rồi nhỉ?", "Nhiệt độ dễ chịu có nghĩa là hết bụi mịn không?"],
         "Trời mát chưa có nghĩa là không khí sạch nhé. Nhiệt độ và cảm giác dễ chịu không thay thế được số đo bụi hoặc AQI; cần xem các chỉ số đó để đánh giá ô nhiễm.", ("project",)),
    ]
    for group, questions, answer, sources in facts:
        for question in questions:
            add("explain_" + group, [{"role": "user", "content": question},
                                      {"role": "assistant", "content": answer}], sources)

    followups = [
        ("easy_aqi", "AQI là gì vậy bạn?", "AQI là chỉ số chất lượng không khí. Số càng cao thì mức lo ngại đối với sức khỏe càng lớn.",
         "Nói dễ hiểu hơn một chút được không?", "Bạn có thể xem AQI như một thang báo mức ô nhiễm: số thấp thì không khí tốt hơn, số cao thì cần chú ý và điều chỉnh hoạt động."),
        ("no_guess", "Chưa có AQI thì mình có ra ngoài được không?", "Mình chưa đủ dữ liệu để đánh giá không khí khi thiếu AQI.",
         "Cứ coi như tốt đi bạn.", "Mình không nên kết luận không khí tốt khi chưa có số liệu. Bạn cập nhật bảng giám sát trước nhé."),
        ("only_humidity", "Dữ liệu Hà Nội: nhiệt độ 24.8 °C, độ ẩm 95%, AQI 175. Thời tiết hiện tại thế nào?", "Ở Hà Nội hiện 24.8 °C, độ ẩm 95%.",
         "Còn độ ẩm thì nói riêng cho mình nhé.", "Độ ẩm ở Hà Nội hiện là 95%."),
        ("unhealthy_aqi", "Giả sử US AQI là 175 thì không khí thế nào?", "US AQI 175 thuộc mức Xấu. Bạn nên giảm hoạt động ngoài trời kéo dài hoặc gắng sức.",
         "Nếu là trẻ em thì sao?", "Trẻ em thuộc nhóm nhạy cảm. Với mức AQI đó, nên tránh các hoạt động ngoài trời kéo dài hoặc gắng sức, có thể chuyển vào trong nhà."),
    ]
    for group, question, answer, next_question, next_answer in followups:
        add("followup_" + group, [{"role": "user", "content": question}, {"role": "assistant", "content": answer},
                                  {"role": "user", "content": next_question}, {"role": "assistant", "content": next_answer}],
            ("airnow_particles", "project"))
    social = [
        ("Xin chào", "Chào bạn, mình là Xanh Non. Bạn muốn xem tình hình môi trường hay cần tư vấn hoạt động ngoài trời?"),
        ("Hi Xanh Non", "Chào bạn! Bạn cần mình hỗ trợ điều gì về môi trường?"),
        ("Cảm ơn bạn nhé", "Không có gì nhé! Cần hỏi thêm điều gì, bạn cứ nhắn mình."),
        ("Bạn ơi", "Mình đây, bạn muốn hỏi gì nào?"),
        ("Bạn có đó không?", "Mình vẫn ở đây. Bạn cần mình giúp gì?"),
        ("Mình hiểu rồi", "Ừ, cần hỏi thêm điều gì bạn cứ nhắn nhé."),
        ("Tạm biệt nhé", "Tạm biệt bạn, hẹn gặp lại nhé!"),
        ("Mình chưa hiểu", "Bạn chưa rõ phần nào? Gửi lại ý đó, mình sẽ giải thích dễ hiểu hơn nhé."),
        ("Bạn nói sai rồi", "Bạn chỉ giúp mình chỗ nào chưa đúng nhé. Mình sẽ kiểm tra lại theo dữ liệu và nguồn tham chiếu."),
        ("Bạn tư vấn được gì?", "Mình giúp bạn hiểu AQI, bụi mịn và các chỉ số môi trường, rồi chọn hoạt động phù hợp với chất lượng không khí."),
    ]
    for question, answer in social:
        add("social_basics_v3", [{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
    add("consultation_dialogue_v3", [
        {"role": "user", "content": "Tư vấn giúp tôi"},
        {"role": "assistant", "content": "Bạn muốn mình tư vấn về chất lượng không khí, hoạt động ngoài trời hay tiếng ồn?"},
        {"role": "user", "content": "Mình muốn chạy bộ"},
        {"role": "assistant", "content": "Bạn định chạy bây giờ hay vào thời điểm nào?"},
        {"role": "user", "content": "Dữ liệu được cung cấp cho địa điểm đang chọn: US AQI hiện tại 175. Bây giờ."},
        {"role": "assistant", "content": "US AQI hiện là 175, mức Xấu. Bạn nên giảm hoạt động kéo dài hoặc gắng sức ngoài trời; có thể chuyển buổi chạy vào trong nhà."},
    ], ("airnow_particles", "project"))
    add("clarify_dialogue_v3", [
        {"role": "user", "content": "AQI là gì?"},
        {"role": "assistant", "content": "AQI là chỉ số thể hiện chất lượng không khí và mức lo ngại đối với sức khỏe."},
        {"role": "user", "content": "Mình chưa hiểu lắm"},
        {"role": "assistant", "content": "Bạn có thể xem AQI như thang báo ô nhiễm: số càng thấp thì không khí tốt hơn, số càng cao thì cần chú ý hơn khi ra ngoài."},
        {"role": "user", "content": "Cảm ơn nhé"},
        {"role": "assistant", "content": "Không có gì nhé, cần hỏi thêm điều gì bạn cứ nhắn mình."},
    ], ("airnow_aqi", "project"))
    for low, high, label, advice in [(42, 49, "Tốt", "Xét riêng chất lượng không khí, bạn có thể hoạt động ngoài trời bình thường."),
                                    (120, 175, "Kém đến Xấu", "Nên giảm hoạt động ngoài trời kéo dài hoặc gắng sức; nhóm nhạy cảm nên chuyển các hoạt động đó vào trong nhà.")]:
        add("forecast_with_data_v3", [
            {"role": "user", "content": f"Dự báo Open-Meteo/CAMS cho ngày mai ở địa điểm mẫu: US AQI theo giờ từ {low} đến {high}. Câu hỏi: Mai không khí thế nào, có nên chạy bộ không?"},
            {"role": "assistant", "content": f"Theo dự báo, US AQI ngày mai khoảng {low}–{high}, mức {label}. {advice}"},
        ], ("airnow_particles", "project"))
    add("air_data_available_v3", [
        {"role": "user", "content": "Ứng dụng cung cấp US AQI 95 ở địa điểm mẫu tại thời điểm hiện tại. Bạn có dữ liệu không khí không?"},
        {"role": "assistant", "content": "Có nhé, US AQI hiện là 95, mức Trung bình. Mình đọc dữ liệu do ứng dụng cung cấp để hỗ trợ bạn."},
    ], ("airnow_aqi", "project"))
    for question in ["Bạn viết code Python giúp mình được không?", "Đầu tư Bitcoin lúc này được không?",
                     "Kể chuyện cười đi bạn", "Hướng dẫn mình nấu bún bò", "Giải bài toán này nhé",
                     "Tư vấn mua điện thoại với", "Bạn biết xem bóng đá không?", "Viết một bài hát tình yêu đi"]:
        add("outside_scope", [{"role": "user", "content": question},
                              {"role": "assistant", "content": OUTSIDE_REPLY}])
    return records
