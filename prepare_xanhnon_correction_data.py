"""Source-checked correction pilot, with paired contexts and a frozen evaluation set.

All numeric scenarios are synthetic. This recipe never edits an older batch,
downloads unreviewed conversations, or changes the running model.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import random
import shutil
from zoneinfo import ZoneInfo

import chatbot
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_balanced_data import reviewed_record
from prepare_xanhnon_data import normalize, stable_id
from sensor_training_data import ROOT, digest, save_json

SOURCE = 'environment_correction_v10'

# Six training phrasings and one separate internal-validation phrasing per family.
# Histories are varied too; only the final answer is a learning target.
QUESTIONS = {
    'noise_duration': [
        'Muốn đỡ hại tai khi gặp âm thanh lớn thì nên đứng gần hay xa, nghe lâu hay ít?',
        'Tôi thường xuyên gặp tiếng xe rất lớn, nên điều chỉnh việc tiếp xúc ra sao?',
        'Ở chỗ ồn lâu để quen tai có giúp bảo vệ tai không?',
        'Nếu không tắt được nguồn ồn, mình có thể giảm tiếp xúc bằng cách nào?',
        'Nghe ồn hàng giờ thì có nên rút ngắn thời gian không bạn?',
        'Xin hai việc thực tế để bớt tiếp xúc tiếng ồn lớn.',
        'Âm thanh lớn không tránh hết được, làm sao giảm ảnh hưởng bằng thời gian và khoảng cách?',
    ],
    'ozone': [
        'Máy lọc cố ý phát ozone có phù hợp để bật trong phòng đang có người không?',
        'Có nên mua máy tạo O3 để chạy khi mình đang ngồi trong phòng?',
        'Ozone khử mùi có phải cứ bật cạnh người là ổn?',
        'Bạn nhận xét việc dùng thiết bị phát ozone lúc có người ở nhà nhé.',
        'Mình định ngồi trong phòng cùng máy sinh ozone, có nên không?',
        'Nhờ bạn nhắc điều cần tránh với máy cố ý sản sinh ozone trong nhà.',
        'Ở nhà có người, chọn chế độ cố ý tạo ozone để làm sạch không khí có hợp lý?',
    ],
    'history_weather': [
        'Đọc lại đúng dự báo ngày mai mình vừa nêu, chỉ nhiệt độ và độ ẩm nhé.',
        'Với bảng minh họa đó, thời tiết ngày tới có hai số nào?',
        'Chỉ lấy nhiệt độ và độ ẩm cho ngày mai từ tin mình vừa nhắn.',
        'Nhắc lại thông tin thời tiết hôm sau trong ví dụ vừa rồi giúp mình.',
        'Vậy hôm sau nhiệt độ, độ ẩm ra sao theo dữ liệu trên?',
        'Mình cần bản tóm tắt thời tiết ngày mai từ hai giá trị đó.',
        'Hãy nhắc lại hai trị số dự báo cho ngày kế sau ở lời nhắn trước.',
    ],
    'history_future_aqi': [
        'Theo giả định ngày mai vừa nêu, việc vận động ngoài trời nên điều chỉnh thế nào?',
        'Dùng riêng chỉ số giả định hôm sau để tư vấn đi dạo cho mình nhé.',
        'Vậy với mức của ngày tới trong ví dụ, nên cân nhắc buổi tập ra sao?',
        'Chỉ nhận xét kế hoạch vận động cho ngày mai theo số mình đưa.',
        'Theo mức AQI giả định hôm sau ấy, hoạt động ngoài trời cần lưu ý gì?',
        'Mình muốn lời khuyên cho ngày tiếp theo trong tình huống giả định này.',
        'Nếu dùng giá trị minh họa cho ngày kế sau, bạn khuyên điều chỉnh buổi vận động ra sao?',
    ],
    'pm_comparison': [
        'Bạn so kích thước giới hạn của bụi PM2.5 và PM10 nhé.',
        'PM10 có kích thước tối đa thường là bao nhiêu, so với PM2.5?',
        'Hai tên PM2.5, PM10 khác nhau ở mốc đường kính nào?',
        'Cho mình phân biệt hai nhóm PM10 và PM2.5 bằng đơn vị micromet.',
        'PM10 không có hại còn PM2.5 mới có hại đúng không?',
        'Cả PM2.5 lẫn PM10 đều có thể hít vào đường hô hấp chứ, kích thước ra sao?',
        'Đọc hai mốc đường kính trong tên các nhóm PM2.5 và PM10 cho mình.',
    ],
    'concentration': [
        'Giá trị bụi trong ví dụ có phải chính là số AQI bằng chừng đó?',
        'Từ con số microgam trên mét khối này, mình chép nguyên sang AQI được không?',
        'Nồng độ bụi trong tình huống trên và số AQI có cùng ý nghĩa không?',
        'Có thể dùng luôn giá trị PM2.5 được đưa làm chỉ số chất lượng không khí chứ?',
        'Số PM2.5 có đơn vị µg/m³ trong ví dụ là nồng độ hay chỉ số AQI?',
        'Phân biệt con số nồng độ vừa nêu với chỉ số AQI giúp mình.',
        'Mình có được lấy trực tiếp số đo bụi của ví dụ làm AQI không cần quy đổi?',
    ],
    'missing_aqi': [
        'Chưa có chỉ số AQI, bụi thấp thì đủ khẳng định chạy ngoài trời an toàn chưa?',
        'Ô AQI đang trống, có nên hiểu là không khí tốt để vận động?',
        'Dữ liệu AQI bị thiếu, mình có thể xem đó là chỉ số bằng không không?',
        'Thiếu US AQI thì bạn kết luận mức không khí hiện tại được chứ?',
        'Nếu hệ thống không có số AQI hợp lệ, bạn sẽ tư vấn buổi tập thế nào?',
        'AQI chưa lấy được, vậy đã đủ căn cứ bảo mọi người ra ngoài bình thường chưa?',
        'Không thấy US AQI cập nhật thì mình có được coi khu vực này là không ô nhiễm?',
    ],
    'current_over_history': [
        'Bỏ tình huống giả sử đó, đọc US AQI hiện tại trên bảng nhé.',
        'Còn US AQI đang cập nhật của Hà Nội thì ở mức nào?',
        'Mình hỏi số AQI bây giờ tại địa điểm đã chọn, không dùng ví dụ cũ.',
        'Dùng chỉ số US AQI hiện tại từ bảng để nhận xét lại nhé.',
        'Xin số AQI mới của Hà Nội và tên mức, bỏ qua giả định trước.',
        'Hãy nói chất lượng không khí Hà Nội lúc này theo số liệu hiện tại.',
        'Dừng giả định cũ nhé; US AQI đang có trên bảng Hà Nội thuộc loại nào?',
    ],
    'lung_followup': [
        'Các hạt nhỏ đó có khả năng xuống sâu trong phổi chứ?',
        'Nó nhỏ nên có thể được hít sâu vào phổi phải không?',
        'Loại bụi mình vừa nói có đi sâu trong phổi được không?',
        'Vậy hít vào thì các hạt ấy có thể vào sâu đến phổi?',
        'Hỏi tiếp loại hạt đó: nó có lọt sâu vào phổi không?',
        'Mình đang nói bụi ấy, có thể hít sâu vào phổi chứ?',
        'Những hạt vừa nhắc có thể theo hơi hít vào sâu trong phổi đúng không?',
    ],
    'no_equipment': [
        'Không có thiết bị lọc nào thì làm ngay việc gì để giảm bụi trong nhà?',
        'Mình muốn vài cách hạn chế bụi phòng ở mà chưa phải mua máy.',
        'Chưa có tiền mua thiết bị, tư vấn việc giảm bụi có thể làm luôn nhé.',
        'Ngoài mua máy, có cách tự làm ngay để bớt bụi không?',
        'Nếu chưa mua được thiết bị, mình cần lau và dùng cửa ra sao?',
        'Vẫn nói về bụi nhé, chưa có máy thì bắt đầu bằng việc nào?',
        'Lúc này mình không có thiết bị xử lý bụi, bạn chỉ vài việc thực hiện ngay được chứ?',
    ],
    'sensor_humidity': [
        'Ẩm cao và số đo bụi tăng cùng lúc, có đủ kết luận bụi thực sự tăng?',
        'Cảm biến PM báo cao lúc nồm, có thể khẳng định ô nhiễm tăng ngay chưa?',
        'Một cảm biến bụi giá rẻ lệch trạm vào hôm ẩm, cần xem lại điều gì?',
        'Vì trời ẩm mà cảm biến báo cao, bạn có chắc mọi phần chênh lệch là bụi thật?',
        'Đọc số cảm biến PM lúc độ ẩm lớn, mình có phải kiểm tra sai lệch không?',
        'Có thể tin tuyệt đối chênh lệch cảm biến bụi với trạm trong hôm nồm?',
        'Một thiết bị đo hạt tăng số khi độ ẩm lên cao, đã đủ bằng chứng bụi ngoài trời tăng thật?',
    ],
    'aqi_category': [
        'Theo số US AQI trong ví dụ, đó là mức gì và nên vận động ra sao?',
        'Bạn phân mức đúng chỉ số giả định vừa rồi và nhắc cách điều chỉnh hoạt động.',
        'Chỉ dùng US AQI minh họa trên, tên mức cùng lời khuyên là gì?',
        'Với giá trị giả sử mình đưa, bạn đọc đúng mức US AQI và tư vấn nhé.',
        'Mình muốn biết chỉ số US AQI ví dụ ấy thuộc loại nào, lưu ý khi ra ngoài?',
        'Phân mức giá trị US AQI giả định và nói ngắn gọn điều nên lưu ý.',
        'Từ số US AQI ở ví dụ vừa trao đổi, hãy gọi tên mức và đưa một lời khuyên hoạt động.',
    ],
    'aqi_definition': [
        'Mình chưa biết AQI, bạn giải nghĩa ngắn gọn được chứ?',
        'Dòng chữ AQI trên ứng dụng có ý nghĩa như thế nào?',
        'AQI diễn đạt điều gì về môi trường xung quanh?',
        'Người mới có thể hiểu chỉ số AQI trong một câu ra sao?',
        'Số AQI cao lên thường biểu thị điều gì?',
        'Giải nghĩa thuật ngữ chỉ số chất lượng không khí thật dễ hiểu nhé.',
        'Nếu giới thiệu AQI cho người lần đầu xem thì bạn sẽ nói thế nào?',
    ],
    'current_weather': [
        'Nhiệt độ và độ ẩm đang cập nhật tại Hà Nội là bao nhiêu?',
        'Mình cần đúng hai số thời tiết Hà Nội hiện tại nhé.',
        'Bảng đang cho biết nhiệt độ, độ ẩm Hà Nội lúc này thế nào?',
        'Đọc phần thời tiết hiện tại, chỉ nhiệt độ và độ ẩm giúp mình.',
        'Xin nhiệt độ hiện tại với độ ẩm ở nơi đang chọn.',
        'Hiện giờ Hà Nội có hai chỉ số thời tiết nào trên bảng?',
        'Giúp mình đọc gọn nhiệt độ và độ ẩm vừa cập nhật ở Hà Nội.',
    ],
    'greeting': [
        'Xanh Non ơi, xin chào nha.', 'Chào, có ai hỗ trợ không vậy?',
        'Hí Xanh Non, mình nhờ chút nhé.', 'Hello bạn trợ lý môi trường!',
        'Ê bạn ơi, mình muốn hỏi chuyện chút.', 'Xin chào bạn, mình đang ở đây nè.',
        'A lô Xanh Non, chào bạn buổi tối.',
    ],
    'ambiguous_time': [
        'Đến mai thì sao bạn?', 'Còn hôm kế thì sao?', 'Ngày tới ổn chứ nhỉ?',
        'Qua ngày mai tình hình sao?', 'Mình xem tiếp ngày sau được không?',
        'Vậy ngày tiếp theo nữa thế nào?', 'Chuyển sang ngày kế tiếp thì tình hình ra sao bạn?',
    ],
    'shorten': [
        'Nói lại đúng ý đó nhưng ngắn hơn nha.', 'Chốt lại bằng một câu dễ hiểu nhé.',
        'Mình muốn nghe gọn lại phần vừa nói.', 'Rút phần giải thích trên còn một câu thôi.',
        'Giải thích lại nhanh và dễ hiểu hơn nào.', 'Tóm tắt ý bạn vừa nói được không?',
        'Gom phần giải nghĩa ấy thành đúng một câu ngắn giúp mình.',
    ],
    'clarify_time': [
        'Mình định đi công viên vận động, tư vấn giúp nhé.',
        'Cho mình lời khuyên cho một buổi tập ngoài trời.',
        'Tôi cần cân nhắc kế hoạch đi dạo, bạn giúp được không?',
        'Mình đang lên kế hoạch ra ngoài chạy nhẹ.',
        'Bạn tư vấn buổi vận động ở công viên giúp tôi.',
        'Mình muốn đi bộ bên ngoài, nhờ bạn hỗ trợ.',
        'Có thể giúp mình cân nhắc một buổi ra ngoài tập thể dục không?',
    ],
    'correction': [
        'Không, mình chỉ muốn xem độ ẩm mới thôi.', 'Ý mình là độ ẩm thôi bạn nhé.',
        'Sửa lại giúp, mình cần mỗi phần trăm độ ẩm.', 'Mình hỏi riêng độ ẩm chứ không hỏi nhiệt độ.',
        'Chỉ cho mình phần độ ẩm hiện tại nha.', 'Đọc lại đúng độ ẩm, không cần số nhiệt độ.',
        'Bạn hiểu rộng quá, chỉ đọc giá trị độ ẩm mới nhất thôi nhé.',
    ],
    'why_time': [
        'Bạn hỏi thời gian để làm gì vậy?', 'Vì sao phải biết lúc mình đi?',
        'Giờ định tập có liên quan gì tới tư vấn?', 'Sao cần hỏi thêm ngày đi vậy bạn?',
        'Tại sao thông tin thời điểm lại cần thiết?', 'Bạn cần biết mình đi lúc nào để làm gì?',
        'Giải thích ngắn gọn vì sao bạn cần hỏi lúc mình định ra ngoài.',
    ],
}


def history(*texts):
    return [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': t} for i, t in enumerate(texts)]


def scenario(topic, index):
    """Answers are project-authored paraphrases of the source facts below."""
    q = QUESTIONS[topic][index]
    if topic in {'history_weather', 'history_future_aqi', 'current_weather', 'current_over_history'} and index < 6:
        # Same question, different supplied values: the answer must follow context.
        q = QUESTIONS[topic][index // 2]
    turns, sources = [], ['project']
    if topic == 'noise_duration':
        answer = ('Giảm thời gian tiếp xúc với tiếng ồn và đứng xa nguồn ồn. '
                  'Nếu phải ở nơi rất ồn, dùng nút tai hoặc chụp tai phù hợp; đừng nghe lâu hơn để quen tai.')
        sources = ['nidcd_noise']
    elif topic == 'ozone':
        answer = 'Không nên dùng thiết bị cố ý tạo ozone khi có người trong phòng, vì ozone có thể kích ứng phổi.'
        sources = ['epa_air_cleaners']
    elif topic == 'history_weather':
        temperature, humidity = round(21.7 + index * .8, 1), 54 + 4 * index
        turns = history(f'Bảng giả lập: Hà Nội hôm nay 30 °C, độ ẩm 90%; dự báo ngày mai {temperature:g} °C, độ ẩm {humidity}%.',
                        'Mình sẽ giữ riêng thông tin hôm nay và dự báo cho ngày mai.')
        answer = f'Theo dự báo minh họa bạn đưa, Hà Nội ngày mai {temperature:g} °C, độ ẩm {humidity}%.'
    elif topic == 'history_future_aqi':
        value = [44, 83, 126, 162, 228, 332, 193][index]
        level, advice = chatbot._aqi_guidance(value)
        turns = history(f'Tình huống giả lập: Hà Nội hôm nay US AQI 59, ngày mai giả sử US AQI {value}. Mình đang tính buổi vận động ngày mai.',
                        'Mình sẽ tư vấn theo giá trị giả định của ngày mai, không dùng số hiện tại.')
        answer = f'Theo giả định ngày mai US AQI {value}, mức {level}. {advice}'
        sources = ['airnow_aqi', 'airnow_particles', 'project']
    elif topic == 'pm_comparison':
        answer = ('PM2.5 thường có đường kính không quá 2,5 micromet; PM10 thường không quá 10 micromet. '
                  'Cả hai đều có thể được hít vào đường hô hấp và ảnh hưởng sức khỏe.')
        sources = ['epa_pm']
    elif topic == 'concentration':
        value = 14 + 5 * index
        turns = history(f'Ví dụ có nồng độ PM2.5 là {value} µg/m³.',
                        'Đó là nồng độ bụi tính bằng microgam trên mét khối.')
        answer = f'Không. {value} µg/m³ là nồng độ PM2.5; AQI là chỉ số quy đổi, không lấy nguyên số nồng độ làm AQI.'
        sources = ['airnow_aqi', 'epa_pm']
    elif topic == 'missing_aqi':
        answer = 'Chưa có US AQI hợp lệ nên mình chưa kết luận được mức không khí hiện tại. Ô trống không có nghĩa AQI bằng 0 hoặc không khí tốt.'
        sources = ['project', 'airnow_aqi']
    elif topic == 'current_over_history':
        turns = history(f'Giả sử ở một ví dụ trước đó US AQI bằng {310 + index}, mình cần giảm vận động không?',
                        'Đó là tình huống giả định; khi hỏi hiện tại cần đọc dữ liệu bảng mới.')
        value = [164, 181, 69, 124, 213, 47, 192][index]
        level, _ = chatbot._aqi_guidance(value)
        answer = f'Theo bảng hiện tại, Hà Nội có US AQI {value}, mức {level}.'
        sources = ['project', 'airnow_aqi']
    elif topic == 'lung_followup':
        turns = history(['Bạn giúp mình hiểu tên PM2.5 nhé.', 'Giải nghĩa ký hiệu PM2.5 một chút nha.',
                         'Mình muốn hiểu loại hạt được gọi là PM2.5.', 'Nói tới PM2.5 là nói hạt nhỏ cỡ nào?',
                         'Giới thiệu cho mình về loại bụi tên PM2.5.', 'Mình muốn tìm hiểu các hạt bụi PM2.5.',
                         'Giúp mình hiểu nhóm hạt có ký hiệu PM2.5 được chứ?'][index],
                        'PM2.5 chỉ nhóm hạt bụi có đường kính thường không quá 2,5 micromet.')
        answer = 'Có. Hạt PM2.5 rất nhỏ nên có thể theo hơi hít vào sâu trong phổi.'
        sources = ['epa_pm']
    elif topic == 'no_equipment':
        turns = history(['Mình muốn giảm bụi cho phòng ở cạnh đường.', 'Phòng mình gần đường nên thường có bụi vào.',
                         'Nhà gần xe cộ, mình cần hạn chế bụi phòng ở.', 'Tư vấn giảm bụi trong căn phòng gần đường giúp mình.',
                         'Mình cần vài cách giảm bụi vào nhà sát đường.', 'Làm gì để phòng cạnh đường xe đỡ bụi?',
                         'Bạn tư vấn cách hạn chế bụi vào phòng sát đường được chứ?'][index],
                        'Có thể giảm nguồn bụi và dùng thiết bị lọc phù hợp nếu có.',
                        ['Cảm ơn, mình hiểu bước đầu rồi.', 'Ừ, mình nắm được ý đầu rồi.', 'Cảm ơn phần tư vấn vừa rồi nha.',
                         'Mình hiểu cách bắt đầu rồi, cảm ơn.', 'Phần đó hữu ích, cảm ơn bạn.', 'Ừm, cảm ơn nha bạn.',
                         'Cảm ơn bạn, thông tin vừa rồi giúp mình hiểu hơn.'][index], 'Không có gì nhé!')
        answer = ('Bạn có thể lau bụi bằng khăn ẩm, hạn chế mở cửa phía đường lúc nhiều bụi và tránh khói thuốc, đốt nến trong nhà. '
                  'Những việc này giúp giảm nguồn bụi và bụi bay lại.')
        sources = ['epa_indoor_pm', 'epa_air_cleaners']
    elif topic == 'sensor_humidity':
        answer = ('Chưa đủ để kết luận bụi tăng thật. Độ ẩm có thể làm sai lệch cảm biến; '
                  'cần kiểm tra điều kiện đo, vị trí, thời điểm và đánh giá hoặc hiệu chuẩn thiết bị.')
        sources = ['epa_sensors']
    elif topic == 'aqi_category':
        value = [36, 78, 118, 158, 248, 348, 188][index]
        level, advice = chatbot._aqi_guidance(value)
        turns = history(f'Chỉ xét ví dụ giả lập US AQI bằng {value}, không phải số của bảng hiện tại.',
                        'Mình sẽ dùng đúng thang US AQI cho giá trị ví dụ đó.')
        answer = f'Với US AQI {value}, mức tương ứng là {level}. {advice}'
        sources = ['airnow_aqi', 'airnow_particles']
    elif topic == 'aqi_definition':
        answer = 'AQI là chỉ số diễn đạt chất lượng không khí và mức lo ngại đối với sức khỏe; số càng cao thì mức ô nhiễm càng đáng lo.'
        sources = ['airnow_aqi']
    elif topic == 'current_weather':
        answer = f'Hà Nội hiện {19.2 + index * 1.1:.1f} °C, độ ẩm {57 + index * 4}%.'
    elif topic == 'greeting':
        answer = ['Chào bạn, mình là Xanh Non! Bạn cần mình hỗ trợ điều gì về môi trường?',
                  'Mình đây! Bạn muốn hỏi về chỉ số môi trường hay cần tư vấn điều gì?'][index % 2]
    elif topic == 'ambiguous_time':
        turns = history(['Mình đang xem cả nhiệt độ, độ ẩm lẫn AQI.', 'Cùng xem thời tiết và chất lượng không khí nhé.',
                         'Mình muốn biết cả điều kiện thời tiết với chỉ số không khí.', 'Hỏi bạn về thời tiết và không khí cùng lúc được chứ?',
                         'Mình đang cân nhắc thời tiết và mức ô nhiễm không khí.', 'Mình xem nhiệt độ và AQI trên bảng.',
                         'Tôi muốn xem đồng thời phần thời tiết và phần chất lượng không khí.'][index],
                        'Hai phần có các chỉ số khác nhau; bạn có thể hỏi từng phần.')
        answer = 'Bạn muốn hỏi thời tiết hay chất lượng không khí ngày mai?'
    elif topic == 'shorten':
        turns = history(QUESTIONS['aqi_definition'][index],
                        'AQI diễn đạt chất lượng không khí và mức lo ngại đối với sức khỏe; số càng cao thì mức lo ngại càng lớn.')
        answer = 'AQI là thang báo mức ô nhiễm không khí: số càng cao thì càng đáng lo.'
        sources = ['airnow_aqi', 'project']
    elif topic == 'clarify_time':
        answer = 'Bạn định đi vào hôm nay hay ngày mai, khoảng mấy giờ?'
    elif topic == 'correction':
        turns = history(QUESTIONS['current_weather'][index],
                        'Bạn muốn xem cả nhiệt độ và độ ẩm phải không?')
        answer = f'Độ ẩm ở Hà Nội hiện là {57 + index * 4}%.'
    elif topic == 'why_time':
        turns = history(QUESTIONS['clarify_time'][index], 'Bạn định đi vào ngày nào, khoảng mấy giờ?')
        answer = 'Mình hỏi để dùng số đo hoặc dự báo đúng lúc bạn định đi. Bạn dự định đi khi nào?'
    else:
        raise ValueError(topic)
    return q, answer, sources, turns


def correction_records():
    result = {'train': [], 'validation': []}
    dialogue_topics = {'greeting', 'ambiguous_time', 'shorten', 'clarify_time', 'correction', 'why_time'}
    for topic in QUESTIONS:
        for index in range(7):
            q, answer, sources, turns = scenario(topic, index)
            component = 'dialogue' if topic in dialogue_topics else 'expertise'
            row = reviewed_record(f'{topic}:{index}', topic, q, answer, sources,
                                  component=component, history=turns, index=index)
            row.update(source=SOURCE, group_id=f'{SOURCE}:{topic}:{index}',
                       review='source_checked_correction_and_project_dialogue_policy',
                       prior_generation_feedback_used=True)
            if topic == 'missing_aqi':
                row['snapshot']['DuLieu']['US_AQI'] = None
                row['snapshot']['DuLieu']['PM25'] = 3
                # Rebuild the prompt from the missing snapshot, not a stale valid AQI.
                from prepare_xanhnon_runtime_data import runtime_record
                _, rebuilt = runtime_record(topic, index, q, answer, sources, row['snapshot'], turns)
                row['messages'] = rebuilt['messages']
            row['id'] = stable_id(row['group_id'] + json.dumps(row['messages'], ensure_ascii=False))[:20]
            result['train' if index < 6 else 'validation'].append(row)
    return result


def validate_records(partitions, cases):
    forbidden = {normalize(c['question']) for c in cases}
    forbidden.update(normalize(t['content']) for c in cases for t in c.get('history', []) if t['role'] == 'user')
    pair_owners, groups, ids = {}, {}, set()
    for split, rows in partitions.items():
        for row in rows:
            if row['id'] in ids or groups.get(row['group_id'], split) != split:
                raise ValueError('Duplicate record or cross-split source group')
            ids.add(row['id'])
            groups[row['group_id']] = split
            if normalize(row['original_question']) in forbidden:
                raise ValueError('Evaluation question in training/validation')
            for offset in range(1, len(row['messages']), 2):
                pair = row['messages'][offset:offset + 2]
                if normalize(pair[0]['content']) in forbidden:
                    raise ValueError('Evaluation history in training/validation')
                key = stable_id(normalize(json.dumps(pair, ensure_ascii=False, sort_keys=True)))
                if pair_owners.get(key, split) != split:
                    raise ValueError('Dialogue pair leaked between train and validation')
                pair_owners[key] = split
    return {'duplicate_record_ids_removed': 0, 'cross_split_pairs': 0}


def prepare(output, extra_cases):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty new output directory')
    recipe_hash = digest(Path(__file__))
    partitions = correction_records()
    cases, case_hash = evaluation_cases(extra_cases)
    deduplication = validate_records(partitions, cases)
    knowledge_path, supplement_path = ROOT / 'data/xanhnon/knowledge.json', ROOT / 'data/xanhnon/specialist_supplement.json'
    sources = {**json.loads(knowledge_path.read_text(encoding='utf-8'))['sources'],
               **json.loads(supplement_path.read_text(encoding='utf-8'))['sources']}
    for rows in partitions.values():
        for row in rows:
            if not set(row['source_ids']) <= set(sources):
                raise ValueError('Unattributed source')
    assert Counter(r['mixture_component'] for r in partitions['train']) == {'expertise': 84, 'dialogue': 36}
    assert Counter(r['mixture_component'] for r in partitions['validation']) == {'expertise': 14, 'dialogue': 6}
    if recipe_hash != digest(Path(__file__)):
        raise RuntimeError('Recipe changed while preparing data')
    output.mkdir(parents=True, exist_ok=True)
    for split, rows in partitions.items():
        random.Random(42).shuffle(rows)
        (output / (split + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    manifest = {
        'schema_version': 1, 'built_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
        'require_complete_dialogues': True, 'seed': 42,
        'counts': {s: dict(Counter(r['source'] for r in rows)) for s, rows in partitions.items()},
        'mixture_counts': {s: dict(Counter(r['mixture_component'] for r in rows)) for s, rows in partitions.items()},
        'new_dialogue_counts': {s: len(rows) for s, rows in partitions.items()},
        'required_train_sources': [SOURCE], 'required_train_topics': sorted(QUESTIONS),
        'artifacts_sha256': {s + '.jsonl': digest(output / (s + '.jsonl')) for s in partitions},
        'sources': [{'id': key, **value} for key, value in sources.items()],
        'rehearsal_sources': [], 'skipped_sources': [], 'deduplication': deduplication,
        'training_configuration': {'max_length': 1024, 'epochs': 1, 'learning_rate': .000075, 'start_from_active_release': True},
        'input_sha256': {'recipe': recipe_hash, 'runtime_recipe': digest(ROOT / 'prepare_xanhnon_runtime_data.py'),
                         'record_builder': digest(ROOT / 'prepare_xanhnon_balanced_data.py'),
                         'knowledge': digest(knowledge_path), 'specialist_cases': digest(supplement_path)},
        'evaluation_cases_sha256': case_hash, 'model_activated': False,
        'review': {'project_authored_targets_read': True, 'unreviewed_pool_copied': False,
                   'independent_expert_certification': False, 'sources_rechecked_at': '2026-10-21'},
        'limitations': [
            '120/20 rows are a small correction pilot, not evidence of general intelligence.',
            'Internal validation shares concepts with training, with separate questions and histories.',
            'Previous 28 generation cases informed corrections; they are a development regression suite.',
            'Eight newly authored confirmation cases remain outside this training batch.',
            'Synthetic readings do not predict real future weather or air quality.',
            '70/30 record ratio and learning rate are experiments, not proven optimal settings.',
            'Only actual generation comparison and answer review can justify activation.',
        ],
    }
    save_json(output / 'manifest.json', manifest)
    shutil.copy2(ROOT / 'data/xanhnon/LICENSE-APACHE-2.0.txt', output / 'LICENSE-APACHE-2.0.txt')
    (output / 'NOTICE.md').write_text(
        '# Xanh Non correction pilot v10\n\nProject-authored Vietnamese paraphrases of the primary source facts listed in manifest.json. '
        'Source links retain attribution; no original webpage is copied wholesale. '
        'All numeric readings and histories are synthetic. Only the final assistant answer is supervised. '
        'No previously rejected model output is used as a target; active v2 is the starting adapter.\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-cases', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output, args.extra_cases)
    print(json.dumps({k: result[k] for k in ('counts', 'mixture_counts', 'training_configuration')}, ensure_ascii=False))
