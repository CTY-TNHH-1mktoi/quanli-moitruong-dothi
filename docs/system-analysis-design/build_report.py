from pathlib import Path
from datetime import datetime
import ast, hashlib, json, re, shutil
from docx import Document
from docx.shared import Inches, Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

BASE=Path(__file__).resolve().parent
PROJECT=BASE.parents[1]
ASSETS=BASE/'assets'
TARGET=BASE/'Phan_tich_thiet_ke_he_thong_Quan_ly_moi_truong_do_thi_Xanh_Non.docx'
doc=Document()
section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.top_margin=Cm(2.15);section.bottom_margin=Cm(2.0)
section.left_margin=Cm(2.4);section.right_margin=Cm(2.0)
section.header_distance=Cm(.85);section.footer_distance=Cm(.85)
section.different_first_page_header_footer=True
WIDTH=section.page_width-section.left_margin-section.right_margin
plain=[];figures=[];tables=[]

def fontstyle(style,size,bold=False):
    st=doc.styles[style] if style in doc.styles else doc.styles.add_style(style,1)
    st.font.name='Times New Roman';st.font.size=Pt(size);st.font.bold=bold;st.font.color.rgb=RGBColor(0,0,0)
    rf=st.element.get_or_add_rPr().rFonts
    for attr in list(rf.attrib):
        if 'theme' in attr.lower():del rf.attrib[attr]
    for attr in ['ascii','hAnsi','eastAsia','cs']:rf.set(qn('w:'+attr),'Times New Roman')
    for border in st.element.xpath('.//w:pBdr'):border.getparent().remove(border)
    st.font.italic=False
    return st
normal=fontstyle('Normal',12.5)
normal.paragraph_format.line_spacing=1.18;normal.paragraph_format.space_after=Pt(6)
normal.paragraph_format.widow_control=True
for style,size in [('Title',22),('Subtitle',14),('Heading 1',16),('Heading 2',14),('Heading 3',13),('TOC Heading',16)]:
    s=fontstyle(style,size,style not in ('Subtitle',))
    s.paragraph_format.space_before=Pt(12);s.paragraph_format.space_after=Pt(7);s.paragraph_format.keep_with_next=True
for name in ['FigureCaption','TableCaption']:
    s=fontstyle(name,11.5);s.paragraph_format.space_before=Pt(6);s.paragraph_format.space_after=Pt(8)
for name in ['SourceNote','SmallText']:
    s=fontstyle(name,10.5);s.paragraph_format.space_after=Pt(5);s.paragraph_format.line_spacing=1.05
fontstyle('Header',10);fontstyle('Footer',10)
for sty in ['TOC 1','TOC 2']:
    s=fontstyle(sty,11.5,sty=='TOC 1');s.paragraph_format.line_spacing=1.08;s.paragraph_format.space_after=Pt(3)
settings=doc.settings.element
doc.settings.odd_and_even_pages_header_footer=False
u=OxmlElement('w:updateFields');u.set(qn('w:val'),'true');settings.append(u)
lang=OxmlElement('w:lang');lang.set(qn('w:val'),'vi-VN');normal.element.get_or_add_rPr().append(lang)
doc.core_properties.title='Phân tích và thiết kế hệ thống thông tin quản lý và giám sát môi trường đô thị'
doc.core_properties.subject='Dự án demoth1 và chatbot Xanh Non'
doc.core_properties.author='Nhóm 1';doc.core_properties.keywords='SRS, DFD, UML, ERD, Xanh Non, demoth1'
doc.core_properties.comments=''

def field(p,instruction,placeholder=''):
    r=p.add_run(); b=OxmlElement('w:fldChar');b.set(qn('w:fldCharType'),'begin');r._r.append(b)
    r=p.add_run();t=OxmlElement('w:instrText');t.set(qn('xml:space'),'preserve');t.text=' '+instruction+' ';r._r.append(t)
    r=p.add_run();e=OxmlElement('w:fldChar');e.set(qn('w:fldCharType'),'separate');r._r.append(e)
    if placeholder:p.add_run(placeholder)
    r=p.add_run();e=OxmlElement('w:fldChar');e.set(qn('w:fldCharType'),'end');r._r.append(e)

hp=section.header.paragraphs[0];hp.text='PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG   |   DEMOTH1';hp.alignment=WD_ALIGN_PARAGRAPH.RIGHT
fp=section.footer.paragraphs[0];fp.alignment=WD_ALIGN_PARAGRAPH.CENTER;field(fp,'PAGE')

def p(text='',style=None,boldlead=None):
    para=doc.add_paragraph(style=style)
    if boldlead and text.startswith(boldlead):para.add_run(boldlead).bold=True;para.add_run(text[len(boldlead):])
    else:para.add_run(text)
    if not style:para.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    plain.append(text);return para

def h(text,level=2):
    plain.append('#'*level+' '+text);return doc.add_paragraph(text,f'Heading {level}')

def chapter(number,title):
    para=h(f'CHƯƠNG {number}  {title.upper()}',1);para.paragraph_format.page_break_before=True

def label(title,text):
    para=p(title+' '+text,boldlead=title)
    if title=='Thiết kế và bằng chứng.':para.alignment=WD_ALIGN_PARAGRAPH.LEFT

def bullets(items):
    for t in items:
        pp=p(t);pp.paragraph_format.left_indent=Cm(.45);pp.paragraph_format.first_line_indent=Cm(-.35)
        pp.text='• '+t

def steps(items):
    for i,t in enumerate(items,1):
        pp=p(f'{i}. {t}');pp.paragraph_format.left_indent=Cm(.5);pp.paragraph_format.first_line_indent=Cm(-.5);pp.paragraph_format.space_after=Pt(3)

def table(title,heads,rows,widths=None):
    n=len(tables)+1;cap=p(f'Bảng {n}. {title}','TableCaption');cap.paragraph_format.keep_with_next=True;tables.append(title)
    t=doc.add_table(rows=1,cols=len(heads));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    weights=widths or [1]*len(heads);total=sum(weights)
    for i,v in enumerate(weights):t.columns[i].width=int(WIDTH*v/total)
    for i,x in enumerate(heads):t.rows[0].cells[i].text=x
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        cells=t.add_row().cells
        for i,v in enumerate(row):cells[i].text=str(v)
    borders=OxmlElement('w:tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'5');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    t._tbl.tblPr.append(borders)
    for ri,row in enumerate(t.rows):
        trPr=row._tr.get_or_add_trPr();ns=OxmlElement('w:cantSplit');trPr.append(ns)
        for ci,c in enumerate(row.cells):
            c.width=int(WIDTH*weights[ci]/total);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcPr=c._tc.get_or_add_tcPr();mar=OxmlElement('w:tcMar')
            for side in ['top','left','bottom','right']:
                e=OxmlElement('w:'+side);e.set(qn('w:w'),'85');e.set(qn('w:type'),'dxa');mar.append(e)
            tcPr.append(mar)
            sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E9EDF1' if ri==0 else ('F7F8FA' if ri%2==0 else 'FFFFFF'));tcPr.append(sh)
            for pp in c.paragraphs:
                pp.paragraph_format.space_after=Pt(1);pp.paragraph_format.space_before=Pt(1);pp.paragraph_format.line_spacing=1.06
                if ri==0:pp.paragraph_format.keep_with_next=True
                pp.alignment=WD_ALIGN_PARAGRAPH.LEFT
                for r in pp.runs:r.font.name='Times New Roman';r.font.size=Pt(11);r.bold=ri==0
    p('',style='SmallText').paragraph_format.space_after=Pt(1)
    plain.extend([' | '.join(heads)]+[' | '.join(map(str,row)) for row in rows]);return t

def picture(filename,title,note=None,maxheight=6.3,width=None):
    from PIL import Image
    path=ASSETS/filename
    im=Image.open(path);w,hx=im.size
    wi=(width or WIDTH/914400);hi=wi*hx/w
    if hi>maxheight:wi*=maxheight/hi
    para=p();para.alignment=WD_ALIGN_PARAGRAPH.CENTER;para.paragraph_format.keep_with_next=True
    run=para.add_run();run.add_picture(str(path),width=Inches(wi))
    for el in run._r.xpath('.//wp:docPr'):el.set('descr',title)
    n=len(figures)+1;figures.append(title)
    cp=p(f'Hình {n}. {title}','FigureCaption');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    if note:p(note,'SourceNote')

def hyperlink(para,text,url):
    link=OxmlElement('w:hyperlink');link.set(qn('r:id'),para.part.relate_to(url,RT.HYPERLINK,is_external=True))
    r=OxmlElement('w:r');pr=OxmlElement('w:rPr');col=OxmlElement('w:color');col.set(qn('w:val'),'000000');pr.append(col);u=OxmlElement('w:u');u.set(qn('w:val'),'single');pr.append(u);r.append(pr)
    tx=OxmlElement('w:t');tx.text=text;r.append(tx);link.append(r);para._p.append(link)

def cover():
    for _ in range(2):p()
    cp=p('BÁO CÁO PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG','Subtitle');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    cp=p('Hệ thống thông tin quản lý\nvà giám sát môi trường đô thị','Title');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER;cp.paragraph_format.space_before=Pt(28);cp.paragraph_format.space_after=Pt(24)
    cp=p('Dự án demoth1\nTrợ lý môi trường Xanh Non','Subtitle');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for _ in range(4):p()
    cp=p('Nhóm 1','Subtitle');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    cp=p('Hồ sơ phân tích chức năng  Mô hình hóa hệ thống\nThiết kế dữ liệu  Thiết kế giao diện  Kiểm thử');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    cp=p('Tháng 10 năm 2026');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER;cp.paragraph_format.space_before=Pt(45)
    doc.add_page_break()
    p('MỤC LỤC','TOC Heading');field(p(),'TOC \\o "1-2" \\h \\z \\u','Mục lục được cập nhật khi hoàn thiện tài liệu.')
    doc.add_page_break()
    p('DANH MỤC HÌNH','TOC Heading');field(p(),'TOC \\t "FigureCaption,1" \\h \\z','Danh mục hình.')
    p('DANH MỤC BẢNG','TOC Heading');field(p(),'TOC \\t "TableCaption,1" \\h \\z','Danh mục bảng.')
    doc.add_page_break()
    p('DANH MỤC TỪ VIẾT TẮT','TOC Heading')
    table('Các thuật ngữ sử dụng trong báo cáo',['Viết tắt','Ý nghĩa'],[
      ('API','Giao diện lập trình ứng dụng'),('AQI','Chỉ số chất lượng không khí'),('BFD','Sơ đồ phân rã chức năng'),('CAMS','Dịch vụ giám sát khí quyển Copernicus'),('DFD','Sơ đồ luồng dữ liệu'),('ERD','Sơ đồ thực thể và quan hệ'),('FK và PK','Khóa ngoại và khóa chính'),('GGUF','Định dạng tệp mô hình dùng cho suy luận cục bộ'),('LoRA','Kỹ thuật tinh chỉnh mô hình bằng các ma trận hạng thấp'),('PM2.5 và PM10','Bụi có đường kính khí động học tương ứng không lớn hơn 2,5 và 10 micromet'),('RF','Random Forest'),('SRS','Đặc tả yêu cầu phần mềm'),('SSE','Luồng sự kiện từ máy chủ tới trình duyệt qua HTTP'),('UML','Ngôn ngữ mô hình hóa thống nhất'),('UTC+7','Múi giờ được sử dụng cho dữ liệu tại Việt Nam')],[1.3,5])

def ch1():
    chapter(1,'Tổng quan đề tài')
    h('1.1 Bối cảnh và bài toán')
    p('Hệ thống quản lý và giám sát môi trường đô thị tập hợp dữ liệu chất lượng không khí, thời tiết và tiếng ồn theo địa điểm. Trên cùng một giao diện, người sử dụng có thể xem chỉ số, theo dõi các lần cập nhật, nhận cảnh báo, lập báo cáo và trao đổi với trợ lý Xanh Non. Bài toán trọng tâm là giữ cho thông tin về địa điểm, thời gian, nguồn và cách diễn giải thống nhất trong toàn bộ các thao tác này.')
    p('Các nguồn của dự án không có cùng đặc tính. Nhiệt độ, độ ẩm và chất lượng không khí được lấy qua Open-Meteo; tiếng ồn được tổng hợp từ dữ liệu cộng đồng NoiseCapture. Vì vậy, một màn hình có thể đồng thời chứa dữ liệu mô hình gần thời điểm hiện tại và số liệu tiếng ồn đã được thu thập từ trước. Việc ghi rõ nguồn và thời điểm giúp người sử dụng hiểu đúng ý nghĩa của từng giá trị [T01]–[T03].')
    h('1.2 Mục tiêu hệ thống')
    p('Hệ thống cung cấp khả năng tra cứu môi trường theo danh mục địa điểm, trực quan hóa phân bố AQI trên bản đồ, lưu các bản ghi phục vụ theo dõi và tạo báo cáo. Chatbot giải thích các chỉ số và hỗ trợ tư vấn trong phạm vi môi trường; những câu hỏi về hiện tại và dự báo được gắn với dữ liệu tương ứng, thay vì dùng số liệu đã ghi nhớ trong trọng số mô hình.')
    h('1.3 Phạm vi phân tích')
    p('Báo cáo mô tả phiên bản mã nguồn demoth1 được khảo sát ngày 27/10/2026. Phạm vi bao gồm ứng dụng web, API Flask, sáu bảng SQL Server, hai kho SQLite phục vụ học từ hội thoại và góp ý, mô hình Random Forest, mô hình ngôn ngữ cục bộ và các công cụ chuẩn bị dữ liệu huấn luyện. Các đường dẫn trong phần bằng chứng được tính từ thư mục gốc của dự án.')
    p('Phiên bản khảo sát sử dụng danh mục 86 địa điểm tham chiếu. Địa điểm là đơn vị tra cứu, không phải hồ sơ trạm cảm biến. Ứng dụng chưa có đăng nhập, vai trò tài khoản, quản lý thiết bị hay quy trình giao việc xử lý cảnh báo. Các mô hình trong báo cáo giữ đúng phạm vi này; tác nhân người vận hành chỉ thực hiện công việc trên máy và bằng công cụ dòng lệnh.')
    h('1.4 Công nghệ và tổ chức triển khai')
    table('Thành phần công nghệ của phiên bản khảo sát',['Thành phần','Công nghệ và vai trò','Bằng chứng'],[
      ('Giao diện','HTML, CSS, JavaScript; CSS Volt Free 1.4.1; điều hướng theo hash','static/index.html; dashboard.js; vendor/volt/SOURCE.md'),
      ('Bản đồ','Leaflet 1.9.4; nền OpenStreetMap; lớp màu AQI bằng Canvas','static/map.js; air-overlay.js'),
      ('Máy chủ','Flask; các blueprint cho báo cáo, bản đồ và góp ý','app.py; environment_reports.py; air_quality_map.py'),
      ('Lưu trữ','SQL Server qua pyodbc; SQLite cục bộ; tệp JSON','Các tệp schema SQL; chat_feedback.py; chat_learning.py'),
      ('Phân loại môi trường','Hai bộ phân loại Random Forest nạp từ joblib','environment_predictor.py; environment_rf.joblib'),
      ('Trợ lý hội thoại','XanhNon-Style-v2; nền Qwen2.5 0.5B; llama.cpp chạy cục bộ','models/xanhnon-active.json; native_chatbot.py'),
      ('Dữ liệu học','JSONL; Transformers, PEFT LoRA; đánh giá và xuất GGUF riêng','train_xanhnon.py; export_xanhnon.py')],[1.2,2.9,2.5])
    h('1.5 Cơ sở lập báo cáo')
    p('Nguồn chính của hồ sơ là mã Python, JavaScript, HTML, các lược đồ SQL, danh mục địa điểm, cấu hình bản mô hình và bộ kiểm thử trong repository. Các tài liệu kỹ thuật chính thức được dùng để xác định ký pháp UML, chức năng thư viện và ý nghĩa nguồn dữ liệu. Kết quả kiểm thử đã lưu được ghi kèm ngày và phạm vi; kết quả của một tập tình huống không được quy đổi thành tỷ lệ chính xác chung của chatbot.')

def ch2():
    chapter(2,'Khảo sát hiện trạng')
    h('2.1 Đối tượng sử dụng và nhu cầu thông tin')
    p('Người sử dụng truy cập trực tiếp ứng dụng web để xem môi trường tại địa điểm quan tâm. Họ cần biết chỉ số nào đã có dữ liệu, dữ liệu được cập nhật lúc nào, cảnh báo thuộc địa điểm nào và nội dung tư vấn dựa trên thông tin gì. Người vận hành phụ trách khởi chạy dịch vụ, kết nối cơ sở dữ liệu, kiểm tra mô hình và xử lý dữ liệu học bằng công cụ cục bộ. Đây là hai nhóm trách nhiệm nghiệp vụ, không phải hai vai trò đăng nhập trong ứng dụng.')
    table('Tác nhân và phạm vi tương tác',['Mã','Tác nhân','Tương tác thực tế'],[
      ('A01','Người sử dụng web','Tra cứu, xem chỉ số và bản đồ, xem cảnh báo, lập báo cáo, chat và gửi lời xác nhận hữu ích.'),
      ('A02','Người vận hành trên máy','Đọc trạng thái, cấu hình môi trường, duyệt góp ý, chuẩn bị dữ liệu và chạy công cụ huấn luyện.'),
      ('E01','Open-Meteo','Cung cấp dữ liệu thời tiết, chất lượng không khí và dự báo theo tọa độ.'),
      ('E02','NoiseCapture','Cung cấp tệp dữ liệu tiếng ồn cộng đồng tại Việt Nam.'),
      ('E03','OpenStreetMap','Cung cấp ảnh nền bản đồ cho trình duyệt.')],[.6,1.7,4.3])
    h('2.2 Quy trình hiện tại')
    p('Khi mở ứng dụng, trình duyệt tải danh mục địa điểm, khôi phục lựa chọn gần nhất và yêu cầu snapshot môi trường của địa điểm đó. Máy chủ kiểm tra cache, gọi các nguồn khi cần, tạo cảnh báo và phân tích, rồi lưu kết quả vào SQL Server. Sau đó, trình duyệt đọc lịch sử và cảnh báo để hoàn thiện nội dung hiển thị. Khi người sử dụng đổi địa điểm, các phản hồi thuộc yêu cầu cũ được loại bỏ để tránh ghép số liệu giữa hai nơi.')
    p('Bản đồ dùng tọa độ tham chiếu của địa điểm đã chọn, đồng thời tải lưới AQI theo vùng đang xem. Báo cáo được tạo từ các bản ghi đã lưu trong kỳ 1, 7 hoặc 30 ngày. Hội thoại gửi kèm địa điểm và một số lượt hỏi đáp gần nhất; máy chủ xác định chủ đề, thời gian và nguồn dữ liệu cần dùng trước khi tạo phản hồi.')
    h('2.3 Hiện trạng các nhóm chức năng')
    table('Kết quả đối chiếu phạm vi chức năng',['Nhóm','Hiện trạng','Căn cứ'],[
      ('Địa điểm','Đã triển khai danh mục, tìm kiếm, ghi nhớ lựa chọn và chọn địa điểm gần nhất','locations.json; static/locations.js'),
      ('Giám sát','Đã triển khai cập nhật, lưu snapshot, năm thông số chính và US AQI','app.py; static/script.js'),
      ('Bản đồ','Đã triển khai nền bản đồ, marker tham chiếu và lớp AQI nội suy','map.js; air-overlay.js; air_quality_map.py'),
      ('Cảnh báo','Đã triển khai sinh theo ngưỡng và lịch sử trong nút chuông','build_alerts; CanhBao; dashboard.js'),
      ('Báo cáo','Đã triển khai tạo, lưu, mở lại, xuất CSV và in bằng trình duyệt','environment_reports.py; static/reports.js'),
      ('Chatbot','Đã triển khai các nhánh quy tắc, tra cứu tri thức, đọc dữ liệu và sinh cục bộ','chatbot.py; chat_knowledge.py; native_chatbot.py'),
      ('Học từ trao đổi','Đã triển khai tiếp nhận câu hỏi mới và góp ý; việc học trọng số là quy trình riêng','chat_learning.py; chat_feedback.py; train_xanhnon.py')],[1.1,3.5,2])
    h('2.4 Đặc điểm dữ liệu và giới hạn nghiệp vụ')
    p('Dữ liệu không khí là kết quả của mô hình do nguồn cung cấp, có độ phân giải theo ô lưới. Các địa điểm gần nhau có thể có cùng giá trị. Đối với bản đồ, API chỉ định CAMS Global và trả metadata độ phân giải 45 km; màu được nội suy để hiển thị liên tục, không tạo ra độ chính xác tương đương đo trực tiếp trên từng tuyến đường.')
    p('Tiếng ồn được lọc trong bán kính tham chiếu 2 km và tổng hợp theo năng lượng có trọng số. Nếu không có ô dữ liệu phù hợp, trường tiếng ồn để trống. Trạng thái “Hệ thống hoạt động” phản ánh việc tải dữ liệu thành công trên giao diện, không xác nhận sự hoạt động của một mạng trạm vật lý.')
    p('Lịch sử trong SQL là lịch sử các snapshot ứng dụng đã lưu. Đồ thị PM2.5 hiển thị tối đa 12 snapshot gần nhất; các điểm không nhất thiết cách đều về thời gian. Hệ thống không suy ra rằng toàn bộ thời gian giữa hai lần cập nhật đã được quan trắc liên tục.')

def ch3():
    chapter(3,'Phương pháp phân tích và thiết kế')
    h('3.1 Phân tích theo chức năng')
    p('Phân tích theo chức năng bắt đầu từ các công việc mà hệ thống phải thực hiện. BFD chia nghiệp vụ thành những nhóm có mục tiêu rõ ràng. DFD thể hiện dữ liệu đi từ tác nhân qua các tiến trình, được đọc hoặc ghi ở kho nào và trả về dưới dạng gì. Trong dự án này, cập nhật dữ liệu, đánh giá ngưỡng và lập báo cáo là những luồng phù hợp để phân tích theo cách đó.')
    p('Sơ đồ ngữ cảnh xác định ranh giới ứng dụng; DFD mức 0 phân rã các tiến trình chính; mức 1 mô tả cập nhật môi trường. Mã FR, UC và BR lần lượt định danh chức năng, ca sử dụng và quy tắc, được dùng thống nhất trong đặc tả và kiểm thử.')
    h('3.2 Phân tích hướng đối tượng')
    p('UML được dùng để mô tả mục tiêu của tác nhân, sự phối hợp giữa thành phần và vòng đời của mô hình hội thoại. Use Case biểu diễn hành vi nhìn từ người sử dụng; Activity biểu diễn trình tự công việc; Sequence thể hiện các lời gọi giữa giao diện, API, lớp xử lý và lưu trữ. Class Diagram mô tả các lớp Python thực sự tồn tại và trách nhiệm của chúng [T04].')
    p('Đối tượng địa điểm, snapshot, cảnh báo và báo cáo được phân tích ở cấp miền nghiệp vụ. Trong mã nguồn hiện tại, nhiều đối tượng được biểu diễn bằng dictionary hoặc hàng SQL, không phải lớp ORM. Báo cáo phân biệt mô hình miền với sơ đồ lớp triển khai để không đồng nhất tên bảng với tên lớp.')
    table('Đối chiếu hai cách phân tích trong dự án',['Nội dung','Theo chức năng','Theo đối tượng'],[
      ('Trọng tâm','Công việc và dữ liệu vào ra','Trách nhiệm và sự cộng tác'),('Mô hình chính','BFD, DFD, đặc tả tiến trình','Use Case, Class, Activity, Sequence, State'),('Ứng dụng trong demoth1','Làm rõ cập nhật, cảnh báo, tổng hợp báo cáo','Làm rõ repository, runtime chatbot và xử lý nhiều lượt'),('Căn cứ triển khai','Các hàm điều phối trong app.py và chatbot.py','LocationStore, ReportRepository, AirMapRepository, NativeChatbot và các lớp lưu học')],[1.2,2.7,2.7])
    h('3.3 Cách tổ chức hồ sơ')
    p('Phân tích chức năng là trục mô tả nghiệp vụ, phù hợp với cách điều phối bằng hàm và module trong Flask. UML bổ sung tương tác và trách nhiệm; ERD mô tả lưu trữ. Các mô hình được liên kết với yêu cầu, API, dữ liệu và kiểm thử.')

def ch4():
    chapter(4,'Đặc tả yêu cầu hệ thống')
    h('4.1 Yêu cầu chức năng và điều kiện truy cập')
    p('Danh mục chức năng được chuẩn hóa thành 18 mã. FR01–FR16 phục vụ thao tác trên ứng dụng và xử lý dữ liệu liên quan; FR17–FR18 phục vụ theo dõi và vận hành mô hình. Mỗi mã có một ca sử dụng tương ứng, ví dụ FR03 liên kết UC03. Các chức năng web không yêu cầu tài khoản; thao tác vận hành dùng quyền của tài khoản hệ điều hành đang chạy dự án.')
    table('Danh mục yêu cầu chức năng',['Mã','Yêu cầu cần đạt','Tác nhân'],[
      ('FR01','Chọn và tìm kiếm địa điểm hoặc chức năng trong danh mục','A01'),('FR02','Lấy vị trí thiết bị và tự chọn địa điểm gần nhất trong danh sách','A01'),('FR03','Cập nhật dữ liệu theo địa điểm và lưu snapshot nhất quán','A01, E01, E02'),('FR04','Hiển thị chỉ số, đơn vị, nguồn và thời điểm cập nhật','A01'),('FR05','Xem marker, di chuyển, phóng to và mở bản đồ lớn','A01, E03'),('FR06','Tải và hiển thị lớp màu chất lượng không khí theo vùng','A01, E01'),('FR07','Xem đồ thị PM2.5 từ các snapshot gần nhất','A01'),('FR08','Xem lịch sử cảnh báo đúng địa điểm bằng nút chuông','A01'),('FR09','Xem kết quả hai mô hình Random Forest và trạng thái dữ liệu','A01'),('FR10','Tạo và lưu báo cáo kỳ 1, 7 hoặc 30 ngày','A01'),('FR11','Tra cứu danh sách và mở nội dung báo cáo đã lưu','A01'),('FR12','Xuất dữ liệu báo cáo thành CSV hoặc in bằng trình duyệt','A01'),('FR13','Gửi câu hỏi và điều khiển phiên hội thoại Xanh Non','A01'),('FR14','Giữ ngữ cảnh chủ đề, địa điểm và thời gian qua nhiều lượt','A01, E01'),('FR15','Giải thích chỉ số và tư vấn từ tri thức có nguồn','A01'),('FR16','Ghi nhận lời xác nhận hữu ích và câu hỏi mới phù hợp','A01'),('FR17','Tra cứu trạng thái runtime của chatbot','A02'),('FR18','Chuẩn bị dữ liệu, huấn luyện và kiểm tra mô hình ứng viên','A02')],[.65,5.1,.85])
    h('4.2 Quy tắc nghiệp vụ')
    table('Các quy tắc nghiệp vụ sử dụng trong đặc tả',['Mã','Quy tắc'],[
      ('BR01','Mã địa điểm phải thuộc danh mục; bỏ trống dùng Hà Nội. Mã không hợp lệ trả lỗi thay vì tự gán sang địa điểm khác.'),
      ('BR02','Cache snapshot hiệu lực 600 giây theo từng địa điểm. Khóa riêng ngăn yêu cầu cùng địa điểm tạo đồng thời nhiều bản ghi trong một tiến trình.'),
      ('BR03','Thời gian lấy dữ liệu, thời gian nguồn thời tiết, thời gian nguồn không khí và thời gian đo tiếng ồn có ý nghĩa riêng; metadata nguồn được giữ trong ChiTiet.'),
      ('BR04','Không có tiếng ồn phù hợp thì trả null. Không dùng tiếng ồn của địa điểm khác để lấp chỗ trống.'),
      ('BR05','Cảnh báo được sinh cho từng thông số có giá trị và liên kết với Manguon; hai mức lưu là Trung bình và Cao.'),
      ('BR06','Phân loại Random Forest chỉ chạy khi đủ năm giá trị hữu hạn. Nhãn của mô hình không thay thế chỉ số US AQI.'),
      ('BR07','Báo cáo chỉ dùng bản ghi và cảnh báo cùng địa điểm, nằm trong kỳ 1, 7 hoặc 30 ngày; nội dung được lưu thành snapshot JSON.'),
      ('BR08','Số liệu thiếu không được dùng như một lần đo bằng 0 khi tính thống kê báo cáo; số thiếu được đếm riêng.'),
      ('BR09','Ngữ cảnh hội thoại gồm tối đa tám cặp hỏi đáp hoàn chỉnh; đổi địa điểm trên giao diện sử dụng lịch sử riêng.'),
      ('BR10','Dữ liệu hiện tại và dự báo phải được lấy theo địa điểm, thời gian đã giải nghĩa. Không lấy số đã xuất hiện trong câu trả lời cũ làm nguồn mới.'),
      ('BR11','Câu hỏi ngoài phạm vi nhận câu giới thiệu cố định; câu hỏi thiếu chủ đề hoặc ngày quan trọng có thể được hỏi lại.'),
      ('BR12','Học từ chat chỉ tái sử dụng câu trả lời kiến thức ổn định đã đối chiếu nguồn. Góp ý cần kiểm tra trước khi thành dữ liệu huấn luyện.'),
      ('BR13','Lưới bản đồ tối đa 196 điểm; vùng thiếu dữ liệu để trống, không tô màu bằng giá trị giả.'),
      ('BR14','Phản hồi cũ đến muộn không thay thế dữ liệu của địa điểm mới đang chọn trên giao diện.')],[.65,5.95])
    h('4.3 Yêu cầu phi chức năng có căn cứ')
    table('Giới hạn và hành vi phi chức năng hiện có',['Mã','Nội dung có thể kiểm tra','Bằng chứng'],[
      ('NFR01','Cập nhật có cache 600 giây; trình duyệt yêu cầu lại mỗi 605 giây khi trang mở. Đây là chu kỳ yêu cầu, không phải cam kết độ trễ nguồn.','app.py; static/script.js'),
      ('NFR02','Luồng chat có status, delta và done hoặc error; có thể dừng nhận khi đang sinh.','chatbot.stream_reply; static/chat.js'),
      ('NFR03','Câu hỏi tối đa 8.000 ký tự, history tối đa 16 message đúng cặp; body chat không quá 2 MiB.','validate_chat; app.chat'),
      ('NFR04','Lỗi một phần lịch sử hoặc cảnh báo được hiển thị riêng; đổi địa điểm loại phản hồi quá hạn.','static/script.js'),
      ('NFR05','Truy vấn SQL dùng tham số; dữ liệu chat hiển thị bằng textContent. Không có chức năng xác thực tài khoản.','app.py; environment_reports.py; static/chat.js'),
      ('NFR06','Giao diện đã có kiểm tra trình duyệt ở 1.600 px và 390 px; hỗ trợ bàn phím cho menu, tìm kiếm và đóng hộp nổi.','browser-checks.json; dashboard.js'),
      ('NFR07','Dữ liệu báo cáo và snapshot dùng JSON không chấp nhận NaN; RF và thống kê loại giá trị không hữu hạn.','environment_reports.py; environment_predictor.py'),
      ('NFR08','Runtime sinh mô hình được khóa tránh chồng phiên; giới hạn tài nguyên được kiểm tra trước huấn luyện.','_generation_lock; training_state.py; daily_train_xanhnon.py')],[.8,4.4,1.5])
    h('4.4 Điều kiện nghiệm thu theo phạm vi')
    p('Một chức năng được xác nhận bằng hành vi đầu ra và trạng thái dữ liệu, không chỉ bằng sự có mặt của nút giao diện. Cập nhật phải giữ đúng mã địa điểm và quan hệ bản ghi; báo cáo mở lại phải khớp nội dung đã lưu; câu hỏi nối tiếp phải dùng đúng chủ đề và ngày giờ; tình huống thiếu dữ liệu phải trả trạng thái hoặc thông báo phù hợp. Chương 12 trình bày dữ liệu kiểm thử, điều kiện thực hiện và bằng chứng kết quả của từng nhóm yêu cầu.')

def ch5():
    from function_specs import render_functions
    chapter(5,'Phân tích chức năng nghiệp vụ')
    h('5.1 Cây phân rã và cách đọc đặc tả')
    p('Cây chức năng gồm sáu nhánh. Nhóm tra cứu xác định địa điểm và trình bày số liệu; nhóm cập nhật tiếp nhận, đánh giá và lưu; bản đồ và xu hướng cung cấp góc nhìn không gian và thời gian; báo cáo tổng hợp lịch sử; hội thoại hỗ trợ giải thích và tư vấn; vận hành quản lý dữ liệu học và trạng thái mô hình.')
    picture('01_bfd.png','Cây phân rã chức năng của hệ thống',maxheight=5.8)
    p('Các chức năng dưới đây đều có mã nguồn triển khai. FR01–FR15 là nghiệp vụ sử dụng trực tiếp; FR16 hỗ trợ ghi nhận dữ liệu cải thiện; FR17–FR18 thuộc vận hành cục bộ. Trạng thái triển khai không đồng nghĩa với mọi yêu cầu đều đã được chứng minh bằng kiểm thử trực tiếp; kết quả và phạm vi kiểm chứng được ghi tại chương 12. Mức ưu tiên của FR01–FR15 là cốt lõi trong sản phẩm, FR16–FR18 là hỗ trợ vận hành.')
    render_functions((p,h,label,steps))

def ch6():
    chapter(6,'Mô hình hóa hệ thống')
    h('6.1 Ranh giới hệ thống và sơ đồ ngữ cảnh')
    p('Ranh giới hệ thống bao gồm phần giao diện, API, lưu trữ nghiệp vụ, chatbot và công cụ học trên máy. Người sử dụng cung cấp địa điểm, câu hỏi và kỳ báo cáo; người vận hành cung cấp lệnh cùng dữ liệu đã chuẩn bị. Open-Meteo, NoiseCapture và OpenStreetMap là hệ thống bên ngoài. SQL Server, SQLite và mô hình cục bộ nằm trong ranh giới thiết kế, không phải tác nhân người dùng.')
    picture('02_context.png','Sơ đồ ngữ cảnh của hệ thống',maxheight=5.5)
    h('6.2 DFD mức 0')
    p('DFD mức 0 tổ chức thành năm tiến trình. Tiến trình 1.0 phục vụ địa điểm và bản đồ; 2.0 cập nhật và đánh giá; 3.0 tạo báo cáo; 4.0 hội thoại và góp ý; 5.0 chuẩn bị và huấn luyện. Các kho D1–D8 là nhóm lưu trữ logic, không mặc định tương ứng một bảng. Cụ thể, D3 gồm CanhBao và PhanTichAI; D7 gồm hai cơ sở dữ liệu SQLite; D8 gồm JSONL, manifest và tệp mô hình.')
    picture('03_dfd0.png','DFD mức 0 phần tra cứu giám sát và báo cáo',maxheight=7.1)
    picture('03b_dfd0_chat.png','DFD mức 0 phần hội thoại và huấn luyện',maxheight=5.2)
    p('DFD mức 0 được trình bày ở hai hình cùng cấp; tác nhân và kho được lặp lại khi cần để các dòng dữ liệu rõ ràng. Tiến trình 4.0 đọc D2 và nguồn dự báo theo ngữ cảnh, không yêu cầu mỗi câu hỏi phải tạo snapshot SQL. Ảnh nền bản đồ do trình duyệt trao đổi trực tiếp với OpenStreetMap trong phạm vi 1.0. Các kho ghép trong một khung là nhóm logic, không bổ sung bảng mới. Tất cả thao tác đọc ghi kho đều đi qua tiến trình xử lý.')
    h('6.3 DFD mức 1 của cập nhật dữ liệu')
    picture('04_dfd1_update.png','DFD mức 1 của tiến trình cập nhật và đánh giá',maxheight=6.3)
    p('Đầu vào của tiến trình 2.0 là mã địa điểm và yêu cầu cập nhật; đầu ra là snapshot hoặc lỗi. Khi phân rã, các bước 2.1–2.5 giữ nguyên hai đầu giao tiếp đó. Nhánh cache trả cùng cấu trúc JSON với nhánh lấy mới. Lưu bản ghi, cảnh báo và phân tích chỉ diễn ra khi đã có dữ liệu nguồn sử dụng được và việc commit thành công.')
    table('Đặc tả các tiến trình con của cập nhật',['Tiến trình','Đầu vào','Xử lý và đầu ra'],[
      ('2.1 Xác định địa điểm','location','Kiểm tra danh mục; trả cấu hình tọa độ hoặc lỗi 400.'),
      ('2.2 Kiểm tra cache','Mã địa điểm và thời gian hiện tại','Khóa theo nơi; kiểm tra bộ nhớ và ChiTiet SQL. Còn hạn thì trả snapshot.'),
      ('2.3 Nhận dữ liệu','Tọa độ và tham chiếu tiếng ồn','Gọi nguồn thời tiết, không khí; tổng hợp tiếng ồn; giữ thời điểm nguồn.'),
      ('2.4 Đánh giá','Dictionary DuLieu','Sinh cảnh báo, phân tích AQI và trạng thái RF; RF lỗi không chặn luồng dữ liệu.'),
      ('2.5 Lưu và trả','Dữ liệu cùng kết quả','Ghi các bảng liên quan trong giao dịch; cập nhật JSON; trả snapshot sau commit.')],[1.6,1.5,3.5])
    h('6.4 Use Case tổng thể và quan hệ giữa các ca sử dụng')
    picture('05_usecase.png','Use Case tổng thể theo nhóm nghiệp vụ',maxheight=6.2)
    p('Các UC được gom theo khoảng mã trong sơ đồ để tránh lặp 18 hình bầu dục trên một trang. Đặc tả riêng của từng UC sử dụng cùng hậu tố với FR ở chương 5. Cập nhật dữ liệu có thể dẫn tới phát sinh cảnh báo; việc xem lịch sử cảnh báo là một mục tiêu riêng. Xuất CSV và in chỉ được thực hiện khi đã có báo cáo hiện tại. Giao tiếp xã hội và câu ngoài phạm vi là các nhánh của UC13, không tạo thành chức năng quản lý tài khoản.')
    h('6.5 Luồng tra cứu môi trường theo địa điểm')
    picture('06_activity_location.png','Activity của luồng chọn địa điểm và tra cứu',maxheight=5.8)
    p('Luồng kết thúc khi các phần đang hiển thị đã nhận dữ liệu của nơi mới hoặc thông báo lỗi tương ứng. Nếu GPS không được cấp quyền, người sử dụng quay về danh sách. Nếu API không tải được, giao diện giữ khả năng thử lại. Các kết quả đến muộn được kiểm tra bằng phiên yêu cầu và mã địa điểm trước khi cập nhật màn hình.')
    h('6.6 Các tương tác tuần tự quan trọng')
    picture('07_sequence_update.png','Sequence cập nhật snapshot và ghi dữ liệu',maxheight=5.7)
    p('Nhánh lấy nguồn trong hình chỉ chạy khi kiểm tra cache không trả được kết quả còn hạn. Bộ dữ liệu, cảnh báo và phân tích được ghi trong cùng khối giao dịch. Sau đó giao diện đọc lịch sử và cảnh báo bằng các yêu cầu độc lập để một phần lỗi không che lấp toàn bộ màn hình.')
    picture('08_sequence_chat.png','Sequence điều phối hội thoại và phản hồi SSE',maxheight=5.7)
    p('Bước trả trực tiếp và bước gọi NativeChatbot là hai nhánh thay thế. Quy tắc và tri thức đã xác định được câu trả lời thì không gọi mô hình sinh. Bước Dừng từ widget hủy quá trình nhận phản hồi; bộ xử lý phía máy chủ chuyển tín hiệu hủy tới runtime khi kết nối đóng.')
    picture('09_sequence_report.png','Sequence tạo và lưu báo cáo môi trường',maxheight=5.7)
    p('ReportRepository là lớp chịu trách nhiệm lấy dữ liệu theo kỳ và lưu snapshot báo cáo. build_report thực hiện tính toán trên dữ liệu đã đọc. Mã báo cáo chỉ được trả cùng phản hồi thành công sau khi lệnh lưu được commit; thao tác mở lại sử dụng NoiDung đã lưu, không gọi lại build_report.')
    h('6.7 Đối tượng miền nghiệp vụ')
    table('Đối tượng miền và bất biến dữ liệu',['Đối tượng','Trách nhiệm và thuộc tính chính','Bất biến hoặc vòng đời'],[
      ('Địa điểm','Nhận diện nơi tra cứu; mã, tên, nhóm, hai bộ tọa độ tham chiếu','Mã thuộc danh mục; tọa độ thời tiết và tiếng ồn có thể khác nhau.'),
      ('Snapshot môi trường','Gắn bộ số liệu, nguồn, thời điểm lấy và kết quả với Manguon','Sau commit là bản ghi lịch sử; thiếu trường giữ ý nghĩa chưa có dữ liệu.'),
      ('Cảnh báo','Ghi loại chỉ số, mức và nội dung tại lần cập nhật','Bắt buộc có NguonDL cha; được lưu và tra cứu, không có trạng thái giao việc.'),
      ('Phân tích môi trường','Lưu kết luận và diễn giải được build_analysis tạo','Mỗi lần cập nhật hiện chèn một hàng; schema cho phép nhiều hàng trên một nguồn.'),
      ('Báo cáo','Đóng gói kết quả theo kỳ và địa điểm','Nội dung là snapshot; mở lại không thay đổi theo bản ghi mới.'),
      ('Mẫu lưới AQI','Lưu tọa độ, thời gian lấy, thời gian nguồn và AQI','Mã vị trí là khóa tra cứu logic; mỗi lần lấy có MaMau riêng.'),
      ('Hội thoại đang mở','Giữ các cặp hỏi đáp và địa điểm của widget','Tồn tại trong bộ nhớ trình duyệt; tách theo địa điểm, giới hạn tám cặp gửi lên API.'),
      ('Góp ý và câu hỏi học','Lưu dấu vết tiếp nhận, nguồn liên kết và trạng thái kiểm tra','Câu hỏi learned phụ thuộc hash tri thức; góp ý approved phải qua kiểm tra riêng tư và nội dung.')],[1.3,2.7,2.6])
    h('6.8 Sơ đồ lớp triển khai')
    picture('10_classes.png','Class Diagram các lớp triển khai nghiệp vụ',maxheight=6.4)
    p('LocationStore phụ trách tạo và đồng bộ metadata địa điểm. ReportRepository phụ trách truy vấn và lưu báo cáo; nó nhận ensure_locations dưới dạng hàm phụ thuộc, trong ứng dụng hàm này được cấp từ LocationStore. AirMapRepository giữ cache và các thao tác đọc ghi mẫu lưới. NoiseData quản lý tệp NoiseCapture dùng chung. NativeChatbot sở hữu tiến trình suy luận cục bộ và đóng tiến trình đó khi kết thúc. FeedbackStore đóng gói thao tác SQLite cho góp ý.')
    picture('11_learning_classes.png','Các phụ thuộc của lớp học từ câu hỏi mới',maxheight=4.2)
    p('ConversationLearner sử dụng các hàm của chat_knowledge để tìm nội dung ổn định có nguồn, sau đó lưu câu hỏi và liên kết tài liệu trong SQLite. Việc thay đổi phiên bản tri thức làm mất hiệu lực của liên kết học cũ cho đến khi được kiểm tra lại. Quan hệ trong hình là phụ thuộc xử lý và đọc ghi dữ liệu, không phải quan hệ kế thừa.')
    h('6.9 Trách nhiệm và quan hệ giữa các thành phần')
    p('Các repository có trách nhiệm tập trung đối với một nhóm lưu trữ; hàm build_report không phụ thuộc Flask nên có thể kiểm thử bằng danh sách hàng dữ liệu. Đây là biểu hiện phân tách trách nhiệm trong thiết kế hiện tại. Ngược lại, app.py vẫn giữ điều phối cập nhật, giao dịch và một số quy tắc đánh giá; chatbot.py giữ phần lớn quyết định nhánh hội thoại. Báo cáo không mô tả các module này như một tập microservice hoặc một hệ lớp miền hoàn chỉnh.')
    p('Quan hệ phụ thuộc xuất hiện khi một bộ xử lý gọi hàm hoặc dùng đối tượng khác. Quan hệ sở hữu thể hiện rõ ở NativeChatbot với tiến trình con; vòng đời tiến trình được đối tượng tạo và kết thúc. Các lớp nghiệp vụ nêu trên không có cây kế thừa chung. Số lượng một–nhiều của snapshot và cảnh báo là quan hệ dữ liệu trong ERD, không phải bằng chứng rằng mã Python đã định nghĩa các lớp NguonDL và CanhBao.')
    h('6.10 Vòng đời runtime chatbot')
    picture('12_state_chat.png','State Diagram của runtime chatbot',maxheight=4.7)
    p('Runtime bắt đầu ở cold, chuyển loading khi nạp và ready khi thành công; nạp thất bại chuyển error. Trạng thái trả ra có thể là training khi khóa huấn luyện không cho phép suy luận đồng thời. Với cấu hình cho phép dùng chung tài nguyên, phản hồi giữ trạng thái runtime và thêm background_training. Việc nhận biết ready không kiểm tra khả năng trả lời đúng mọi câu hỏi.')

def ch7():
    chapter(7,'Thiết kế kiến trúc phần mềm')
    h('7.1 Kiến trúc tổng thể')
    p('Ứng dụng là một hệ Flask triển khai tập trung theo module. Giao diện và API được phục vụ từ cùng tiến trình; bản đồ, báo cáo và góp ý được tách thành blueprint. SQL Server giữ dữ liệu nghiệp vụ; các tệp mô hình, tri thức và SQLite nằm trên máy chạy ứng dụng. Cách sử dụng blueprint ở đây là phân nhóm chức năng trong một ứng dụng Flask [T05].')
    picture('13_components.png','Component Diagram của ứng dụng',maxheight=5.8)
    h('7.2 Phân chia thành phần')
    table('Trách nhiệm các thành phần kiến trúc',['Thành phần','Trách nhiệm','Giao tiếp chính'],[
      ('Giao diện','Điều hướng, chọn địa điểm, khóa trạng thái bận, dựng DOM và đồ thị','HTTP JSON, SSE, sự kiện locationchange'),
      ('Routes giám sát','Điều phối nguồn, cache, giao dịch và truy vấn lịch sử','app.py và pyodbc'),
      ('Bản đồ','Tạo lưới, chia sẻ cache mẫu, trả ma trận theo vùng','AirMapRepository; Open-Meteo; SQL'),
      ('Báo cáo','Đọc dữ liệu theo kỳ, tính thống kê và lưu nội dung','build_report; ReportRepository'),
      ('Hội thoại','Giải nghĩa ý định, ngữ cảnh, nguồn dữ liệu, tri thức và đầu ra','chatbot; các module chat_*'),
      ('Suy luận native','Quản lý tiến trình mô hình và nhận token sinh','NativeChatbot; HTTP loopback'),
      ('Dữ liệu học','Ghi góp ý, biến thể câu hỏi và dữ liệu đã duyệt','FeedbackStore; ConversationLearner; SQLite'),
      ('Huấn luyện','Lọc tập học, LoRA, kiểm tra, xuất bản ứng viên','Các script train, evaluate, export và manifest')],[1.4,3.2,2])
    h('7.3 Hợp đồng trao đổi dữ liệu')
    p('Các API dữ liệu trả JSON, trong đó lỗi nghiệp vụ thường có trường loi. Các mã 400, 404, 413, 429, 502 và 503 được dùng tùy tình huống cụ thể. Luồng chat sử dụng cùng endpoint với cờ stream=true và kiểu text/event-stream. Client xử lý từng sự kiện, vì vậy phản hồi sinh dần không được coi như một JSON duy nhất.')
    p('Snapshot giám sát bao gồm định danh nguồn, thời điểm lấy, địa điểm, bộ giá trị nguồn, kết quả RF, danh sách cảnh báo và phân tích. Nội dung này cũng được lưu trong NguonDL.ChiTiet. Các API lịch sử trả hàng dữ liệu dạng danh sách; báo cáo trả cả thống kê và dữ liệu nguồn đã dùng. Chi tiết tham số và giới hạn được trình bày ở phụ lục A.')
    h('7.4 Xử lý đồng thời và tính nhất quán')
    p('Máy chủ dùng khóa riêng cho từng địa điểm khi cập nhật snapshot. Điều này ngăn các yêu cầu cùng nơi chạy đồng thời trong một tiến trình, đồng thời cho phép tách cache giữa các nơi. Bản đồ dùng khóa của AirMapRepository để chia sẻ mẫu; NoiseData dùng một khóa để quản lý tệp chung. Khóa sinh hội thoại hạn chế chồng phiên mô hình. Đây là cơ chế trong bộ nhớ của tiến trình, không phải khóa phân tán giữa nhiều máy chủ.')
    p('Ở giao diện, số phiên yêu cầu và AbortController được dùng khi đổi địa điểm. Báo cáo và hội thoại cũng kiểm tra mã nơi đang chọn trước khi trình bày. Nút thao tác được khóa trong những bước có thể gây lẫn ngữ cảnh, ví dụ đổi địa điểm trong lúc gửi câu hỏi hoặc tạo báo cáo.')
    h('7.5 Mô hình triển khai hiện tại')
    picture('14_deployment.png','Deployment Diagram trên máy chạy dự án',maxheight=5)
    p('Flask được cấu hình lắng nghe 127.0.0.1:5000, debug=False và không dùng reloader. NativeChatbot mở tiến trình llama.cpp trên 127.0.0.1 với cổng động; luồng giao tiếp mô hình không đi qua dịch vụ ChatGPT. SQL Server được kết nối bằng ODBC, mặc định dùng xác thực Windows khi không cấu hình tài khoản SQL. Internet phục vụ nguồn môi trường và nền bản đồ, còn trọng số mô hình nằm cục bộ.')

def ch8():
    chapter(8,'Thiết kế cơ sở dữ liệu')
    h('8.1 Mô hình logic và mô hình vật lý')
    p('Mô hình dữ liệu nghiệp vụ lấy địa điểm và snapshot làm trục. Một địa điểm có nhiều snapshot và nhiều báo cáo; một snapshot có thể sinh nhiều cảnh báo. Phân tích và cảnh báo tham chiếu nguồn đã ghi. Mẫu bản đồ được tổ chức theo tọa độ lưới, có thể dùng chung giữa các địa điểm và vùng nhìn nên không có quan hệ khóa ngoại đến một địa điểm cụ thể.')
    p('Trong lược đồ SQL hiện tại, chỉ hai quan hệ được khai báo bằng FOREIGN KEY: CanhBao.Manguon và PhanTichAI.Manguon cùng tham chiếu NguonDL.Manguon. MaDiaDiem trong NguonDL và BaoCaoMT được dùng để liên kết ở tầng ứng dụng nhưng chưa khai báo FK trong các tệp schema. ERD dưới đây dùng nét đứt cho các liên kết logic đó, tránh thể hiện như ràng buộc vật lý đã tồn tại [T06].')
    picture('15_erd.png','ERD sáu bảng nghiệp vụ và loại liên kết',maxheight=6.7)
    p('Trong phạm vi dữ liệu mới do ứng dụng tạo, MaDiaDiem luôn được lấy từ danh mục hợp lệ. Cột này vẫn cho phép NULL ở NguonDL để tương thích dữ liệu cũ. Phần migration chỉ gắn hanoi cho các hàng cũ nhận diện rõ nguồn Hà Nội; các hàng khác không được gán địa điểm suy đoán. CanhBao và PhanTichAI bắt buộc có Manguon; NguonDL không bắt buộc phải có cảnh báo. Mỗi lượt cập nhật hiện tạo một phân tích, trong khi ràng buộc vật lý cho phép 0 đến nhiều phân tích trên một nguồn.')
    h('8.2 Từ điển bảng DiaDiem')
    table('Cấu trúc bảng DiaDiem',['Cột','Kiểu và ràng buộc','Ý nghĩa'],[
      ('MaDiaDiem','VARCHAR(64), PK','Mã ổn định trong danh mục.'),('Ten','NVARCHAR(200), NOT NULL','Tên hiển thị.'),('Nhom','NVARCHAR(120), NOT NULL','Nhóm lựa chọn địa điểm.'),('ViDo và KinhDo','FLOAT, NOT NULL','Tọa độ lấy dữ liệu thời tiết và không khí.'),('ViDoTiengOn và KinhDoTiengOn','FLOAT, NOT NULL','Tọa độ tham chiếu dữ liệu tiếng ồn.'),('TenKhuVucTiengOn','NVARCHAR(200), NOT NULL','Tên khu vực tiếng ồn theo nguồn.'),('ChiTiet','NVARCHAR(MAX), NULL','Metadata JSON của địa điểm.')],[1.8,2.2,2.6])
    p('locations.json là danh mục cấu hình được ứng dụng đọc khi khởi động. LocationStore.ensure_schema đưa các thuộc tính tương ứng vào DiaDiem theo cơ chế cập nhật hoặc thêm. Bảng này không có màn hình CRUD địa điểm; việc đồng bộ không biến các mục thành trạm cảm biến.')
    h('8.3 Từ điển bảng NguonDL')
    table('Cấu trúc bảng NguonDL',['Cột','Kiểu và ràng buộc','Ý nghĩa'],[
      ('Manguon','INT IDENTITY, PK','Định danh snapshot.'),('TenNguon','NVARCHAR(100), NOT NULL','Tên nguồn gắn với địa điểm.'),('ThoiGian','DATETIME, NOT NULL','Thời điểm ứng dụng lấy và lưu dữ liệu.'),('PM25 và PM10','DECIMAL(6,2), NULL','Nồng độ bụi, µg/m³.'),('NhietDo','DECIMAL(5,2), NULL','Nhiệt độ, °C.'),('DoAm','DECIMAL(5,2), NULL','Độ ẩm tương đối, %.'),('TiengOn','DECIMAL(6,2), NULL','Giá trị tổng hợp tiếng ồn, dBA.'),('MaDiaDiem','VARCHAR(64), NULL','Mã liên kết địa điểm ở tầng ứng dụng.'),('ChiTiet','NVARCHAR(MAX), NULL','Snapshot JSON gồm dữ liệu nguồn và kết quả.')],[1.65,2.25,2.7])
    p('Thời gian nguồn thời tiết, nguồn không khí, thông tin số ô và thời gian đo tiếng ồn, các khí bổ sung cùng US AQI nằm trong ChiTiet. Các giá trị hiển thị thường xuyên cũng được lưu ở cột quan hệ để truy vấn lịch sử và tổng hợp. Việc lưu song song là chủ đích lưu snapshot và phục vụ truy vấn; hai phần được ghi trong cùng giao dịch cập nhật.')
    h('8.4 Từ điển bảng CanhBao và PhanTichAI')
    table('Cấu trúc bảng CanhBao',['Cột','Kiểu và ràng buộc','Ý nghĩa'],[
      ('Macanhbao','INT IDENTITY, PK','Mã cảnh báo.'),('Manguon','INT, NOT NULL, FK','Nguồn snapshot gây cảnh báo.'),('LoaiCanhBao','NVARCHAR(100), NULL','Tên thông số.'),('MucDo','NVARCHAR(50), NULL','Trung bình hoặc Cao theo xử lý ứng dụng.'),('NoiDung','NVARCHAR(255), NULL','Thông tin giá trị và ngưỡng.'),('ThoiGian','DATETIME, NOT NULL','Thời gian tạo cảnh báo.')],[1.5,2.35,2.75])
    table('Cấu trúc bảng PhanTichAI',['Cột','Kiểu và ràng buộc','Ý nghĩa'],[
      ('Maphantich','INT IDENTITY, PK','Mã hàng phân tích.'),('Manguon','INT, NOT NULL, FK','Snapshot được đánh giá.'),('KetQua','NVARCHAR(100), NULL','Mức chất lượng không khí.'),('NhanXet','NVARCHAR(255), NULL','Diễn giải từ quy tắc AQI.'),('KhuyenNghi','NVARCHAR(255), NULL','Nội dung gợi ý do build_analysis chọn.'),('ThoiGian','DATETIME, NOT NULL','Thời gian lưu phân tích.')],[1.5,2.35,2.75])
    p('Lược đồ không có cột người xử lý, thời gian xác nhận hoặc trạng thái đóng cảnh báo. Thao tác hiện tại là ghi nhận và tra cứu sự kiện. Tên bảng PhanTichAI được giữ theo dự án; cơ chế tạo dữ liệu trong bảng là hàm quy tắc, tách khỏi việc chatbot sinh văn bản.')
    h('8.5 Từ điển bảng BaoCaoMT và MauBanDoKhongKhi')
    table('Cấu trúc bảng BaoCaoMT',['Cột','Kiểu và ràng buộc','Ý nghĩa'],[
      ('MaBaoCao','INT IDENTITY, PK','Mã báo cáo.'),('MaDiaDiem','VARCHAR(64), NOT NULL; mặc định hanoi','Mã địa điểm của báo cáo.'),('TieuDe','NVARCHAR(200), NOT NULL','Tên báo cáo.'),('TuNgay và DenNgay','DATETIME2, NOT NULL','Khoảng dữ liệu được tổng hợp.'),('ThoiGianTao','DATETIME2, NOT NULL','Thời điểm tạo snapshot báo cáo.'),('SoNgay','INT, NOT NULL','Kỳ 1, 7 hoặc 30 do API kiểm tra.'),('SoBanGhi và SoCanhBao','INT, NOT NULL','Tổng số bản ghi và cảnh báo trong kỳ.'),('NoiDung','NVARCHAR(MAX), NOT NULL','JSON đầy đủ của báo cáo đã tạo.')],[1.7,2.45,2.45])
    table('Cấu trúc bảng MauBanDoKhongKhi',['Cột','Kiểu và ràng buộc','Ý nghĩa'],[
      ('MaMau','INT IDENTITY, PK','Mã lần lấy mẫu.'),('MaViTri','VARCHAR(64), NOT NULL','Khóa tra cứu điểm tọa độ; không là FK địa điểm.'),('ViDo và KinhDo','FLOAT, NOT NULL','Tọa độ điểm lưới yêu cầu.'),('ThoiGianLay','DATETIME2, NOT NULL','Thời điểm ứng dụng lấy mẫu.'),('ThoiGianNguon','DATETIME2, NULL','Thời điểm do nguồn không khí cung cấp.'),('US_AQI và PM25','FLOAT, NULL','Giá trị mẫu mô hình.'),('ChiTiet','NVARCHAR(MAX), NOT NULL','JSON gắn tọa độ và giá trị nguồn.')],[1.7,2.35,2.55])
    h('8.6 Kho góp ý và kho học câu hỏi trong SQLite')
    p('Hai cơ sở SQLite có phạm vi riêng, không khai báo khóa ngoại sang SQL Server. feedback chứa một hàng cho mỗi payload có fingerprint duy nhất; questions dùng question_key làm khóa chính. document_id trong questions tham chiếu mã tài liệu trong JSON ở cấp ứng dụng, không phải một FK tới bảng SQL.')
    table('Các trường của hai kho SQLite',['Kho','Các trường và vai trò'],[
      ('feedback','id INTEGER PK; fingerprint TEXT UNIQUE NOT NULL; created_at, payload, model và status TEXT NOT NULL; review, reviewed_at TEXT cho phép trống. status mặc định pending; công cụ duyệt dùng approved hoặc rejected.'),
      ('questions','question_key TEXT PK; question và context_user TEXT NOT NULL; status TEXT NOT NULL; document_id, variant TEXT; knowledge_hash và policy TEXT NOT NULL; created_at, last_seen TEXT NOT NULL; seen_count INTEGER NOT NULL.')],[1.25,5.35])
    h('8.7 Chuẩn hóa và lưu snapshot')
    p('Ở phần dữ liệu quan hệ, mỗi bảng có khóa chính đơn và lưu các thuộc tính của chính thực thể đó. Các thuộc tính cảnh báo được tách khỏi snapshot để biểu diễn quan hệ một–nhiều; metadata địa điểm được tách thành DiaDiem. Với các cột quan hệ được liệt kê, không có nhóm thuộc tính lặp và không có khóa ghép làm phát sinh phụ thuộc bộ phận. Việc phân tích dạng chuẩn được giới hạn ở cấu trúc quan hệ, không xem JSON lồng nhau là một tập cột đã chuẩn hóa.')
    p('NguonDL.ChiTiet và BaoCaoMT.NoiDung giữ nội dung snapshot phục vụ khôi phục cache và mở lại báo cáo. Một số thuộc tính được lặp có chủ đích trong cột và JSON, vì vậy không mô tả toàn bộ thiết kế là một lược đồ thuần 3NF không dư thừa. Nội dung JSON được kiểm tra ở mã Python và ghi bằng tham số; các tệp schema không khai báo CHECK ISJSON hay CHECK cho khoảng độ ẩm và kỳ báo cáo.')
    h('8.8 Chỉ mục tính toàn vẹn và chống trùng')
    table('Chỉ mục và cơ chế tra cứu hiện có',['Đối tượng','Cơ chế','Phục vụ'],[
      ('NguonDL','IX_NguonDL_DiaDiem_ThoiGian trên MaDiaDiem, ThoiGian DESC, Manguon DESC','Bản gần nhất và lịch sử theo nơi.'),
      ('BaoCaoMT','IX_BaoCaoMT_ThoiGianTao; IX_BaoCaoMT_DiaDiem','Danh sách báo cáo mới nhất và phân trang theo địa điểm.'),
      ('MauBanDoKhongKhi','IX_MauBanDoKK_ViTri_ThoiGian trên MaViTri, ThoiGianLay DESC, MaMau DESC','Đọc mẫu mới nhất của một điểm trong giờ.'),
      ('Góp ý','fingerprint duy nhất và INSERT OR IGNORE','Không ghi lặp cùng payload và phiên bản mô hình.'),
      ('Câu hỏi học','question_key và hash của câu hỏi cùng ngữ cảnh','Tăng số lần gặp trên hàng đã có.'),
      ('Snapshot và mẫu bản đồ','Khóa trong tiến trình, thời hạn cache và đọc lại SQL','Giảm bản ghi lặp do yêu cầu đồng thời; không là UNIQUE theo thời gian nguồn.')],[1.5,3.1,2])
    p('Khóa ngoại bảo vệ sự tồn tại của snapshot cha đối với cảnh báo và phân tích. Hệ thống không có API xóa snapshot, xóa địa điểm hoặc xóa báo cáo. Các quy tắc nghiệp vụ như kỳ báo cáo hợp lệ, giới hạn lưới và chuẩn dữ liệu đầu vào nằm trong xử lý ứng dụng. Cơ chế cache ngăn phần lớn lần lấy lại trong thời hạn, nhưng schema không cấm hai snapshot khác nhau có cùng thời gian nguồn.')

def ch9():
    chapter(9,'Thiết kế giao diện và tương tác người dùng')
    h('9.1 Cấu trúc điều hướng và luồng màn hình')
    p('Ứng dụng sử dụng một trang HTML và chuyển phần nội dung theo hash. Tổng quan gồm ba khu vực: địa điểm đang giám sát, chỉ số môi trường và bản đồ. Các chức năng còn lại được mở từ menu để giữ trang tổng quan ngắn. Nút chuông và chatbot là hai phần nổi dùng chung trên các màn hình; chúng không tạo thêm mục dài trong trang chính.')
    table('Danh mục màn hình và quan hệ điều hướng',['Mã','Màn hình và đường dẫn','Điều hướng và ca sử dụng'],[
      ('UI01','Tổng quan /#overview','Menu hoặc thương hiệu về tổng quan; UC01–04, UC05–06.'),('UI02','Chỉ số /#air','Menu Chỉ số môi trường; quay lại tổng quan; UC04.'),('UI03','Bản đồ /#environmentMap','Menu Bản đồ chất lượng không khí; UC05–06.'),('UI04','Xu hướng /#trends','Menu Xu hướng dữ liệu; UC07.'),('UI05','Phân tích /#insights','Menu Phân tích và tư vấn; UC09.'),('UI06','Bảng cảnh báo nổi','Nút chuông mở; X hoặc Esc đóng; UC08.'),('UI07','Báo cáo /#reports','Menu Báo cáo môi trường; UC10–12.'),('UI08','Cửa sổ Xanh Non nổi','Bong bóng chat mở; nút đóng thu gọn; UC13–16.')],[.7,2.6,3.3])
    p('Luồng màn hình được giữ bằng URL, nên tải lại, Quay lại và Tiến của trình duyệt khôi phục đúng mục. Mỗi màn hình chức năng hiển thị địa điểm dùng chung và đường về tổng quan. Việc mở menu không thay địa điểm; chọn một địa điểm từ tìm kiếm mới phát sinh locationchange.')
    picture('16_wireframe.png','Wireframe tổng quan theo giao diện đã triển khai',maxheight=5)
    h('9.2 UI01 Tổng quan và lựa chọn địa điểm')
    p('Khu vực đầu có tên địa điểm, trạng thái tải, nguồn, danh sách chọn và nút lấy vị trí. Bên phải là nút Cập nhật dữ liệu, ngay dưới là thời điểm cập nhật gần nhất. Danh sách địa điểm giới hạn chiều rộng trên máy tính và co theo màn hình nhỏ. Chọn nơi mới làm thay đổi toàn bộ phần dữ liệu đang dùng chung, thay vì chỉ đổi tiêu đề.')
    p('Đầu vào gồm mã địa điểm từ danh sách và từ khóa tìm kiếm trên thanh đầu trang. Dữ liệu đến từ /api/diadiem và /api/capnhat. Trạng thái đang tải được thể hiện ở nhãn trạng thái cùng aria-busy; lỗi danh mục có nút thử lại riêng. Khi GPS thành công, thông báo ghi rõ địa điểm gần nhất trong danh sách và khoảng cách theo đường thẳng. UI01 phục vụ UC01–UC04; mã nguồn liên quan là index.html, locations.js, dashboard.js và script.js.')
    picture('home-live-desktop.png','Giao diện tổng quan trên máy tính','Ảnh chạy ứng dụng lưu ngày 27/10/2026. Các giá trị trong ảnh minh họa snapshot tại thời điểm chụp, không phải số liệu cập nhật ở thời điểm đọc báo cáo.',maxheight=4.4)
    h('9.3 UI02 Chỉ số môi trường')
    p('Thẻ US AQI trình bày giá trị, tên mức, màu và nội dung đánh giá. Năm thẻ còn lại trình bày PM2.5, PM10, nhiệt độ, độ ẩm và tiếng ồn. Tên đơn vị gắn với từng giá trị; nhãn theo dõi trên mỗi thẻ lấy từ cảnh báo nội bộ tương ứng. Thẻ không phải nút điều hướng tới hồ sơ trạm. Khi thiếu giá trị, giao diện biểu diễn chưa có dữ liệu thay vì tự tạo một thông số.')
    p('Phần ghi chú tiếng ồn thể hiện khu vực tổng hợp và lần đo gần nhất trong nguồn. Thời gian ở khối Cập nhật gần nhất là lúc ứng dụng lấy snapshot. UI02 dùng dữ liệu đã tải theo FR03 và các hàm renderCurrent, renderAnalysis; không có bộ chọn thông số tùy ý hoặc chỉnh sửa ngưỡng tại màn hình này. UC liên quan là UC04.')
    h('9.4 UI03 Bản đồ chất lượng không khí')
    p('Phía trên bản đồ có tên nơi, tọa độ, nút về địa điểm đã chọn, toàn màn hình và mở bản đồ lớn. Phần lớp phủ có công tắc và thanh độ đậm. Marker cung cấp popup tham chiếu; bản đồ cho phép kéo và thay mức zoom. Lớp màu nhận dữ liệu từ /api/bando/khongkhi, trong khi ảnh nền do Leaflet tải trực tiếp [T07].')
    p('Trong trạng thái đang tải, lớp phủ không được xem là một bộ số liệu mới đã hoàn thành. Khi tải thiếu, vùng không có mẫu giữ trong suốt và thông báo nguồn đi cùng. Lỗi ảnh nền và lỗi nguồn AQI là hai lỗi khác nhau. Những lần pan hoặc đổi nơi tạo yêu cầu cũ không được ghi đè lớp mới. UI03 phục vụ UC05–UC06; file triển khai là map.js và air-overlay.js.')
    h('9.5 UI04 Xu hướng dữ liệu')
    p('Màn hình có tên xu hướng PM2.5, nhận xét tăng giảm, giá trị gần nhất và đồ thị Canvas. Trục tung có số, đơn vị µg/m³ và bước chia tự chọn theo miền dữ liệu; trục hoành có nhãn thời gian. Đồ thị được vẽ lại theo kích thước phần chứa. Phiên bản hiện tại dùng 12 snapshot gần nhất, không có date picker hoặc danh sách chọn tất cả thông số trên màn hình này.')
    p('Nguồn là /api/dulieu/lichsu?limit=12&location=...; UC07. Các trạng thái rỗng, lỗi tải và thiếu điểm có cách hiển thị riêng. Màn hình không kết luận xu hướng dài hạn từ số điểm thưa, không biến các mốc snapshot thành dữ liệu quan trắc liên tục.')
    picture('trends-restored-1600.png','Màn hình xu hướng với trục số','Ảnh từ kiểm thử trình duyệt ngày 27/10/2026, sử dụng dữ liệu kiểm thử có kiểm soát để kiểm tra trục và điều hướng.',maxheight=4.2)
    h('9.6 UI05 Phân tích và tư vấn')
    p('Màn hình trình bày phân tích AQI, nội dung gợi ý theo quy tắc và kết quả Random Forest. Dữ liệu RF có trạng thái riêng, gồm đủ dữ liệu, thiếu dữ liệu và lỗi mô hình. Người sử dụng có thể nhìn đồng thời nhãn AQI và nhãn RF; hai nhãn có thể khác nhau vì dùng cơ chế phân loại khác nhau.')
    p('Phần này đọc kết quả PhanTich và DuDoanRF từ snapshot, không gọi chatbot để dựng toàn bộ nội dung. UC09 được thực hiện bởi renderPrediction và renderAnalysis trong script.js. Không có thao tác cấu hình lại classifier hoặc gửi lệnh huấn luyện từ giao diện này.')
    h('9.7 UI06 Lịch sử cảnh báo trong nút chuông')
    p('Nút chuông luôn nằm trên thanh đầu trang; số đếm gắn với những mục cảnh báo gần nhất đã tải. Khi mở, bảng nổi có tên địa điểm, danh sách, mức, nội dung, thời gian và nút đóng. Đang tải, chưa có cảnh báo và lỗi được trình bày trong chính bảng nổi. Đóng bảng không cập nhật trạng thái đã đọc trong cơ sở dữ liệu vì lược đồ chưa có thuộc tính này.')
    p('Dữ liệu được đọc từ /api/canhbao?limit=8&location=... và liên kết UC08. Khi đổi nơi, tên bảng và danh sách đổi theo. Thành phần điều khiển được đặt tại notificationToggle, notificationClose và warningHistory; hành vi nằm trong dashboard.js cùng script.js.')
    h('9.8 UI07 Báo cáo môi trường')
    p('Màn hình có bộ chọn kỳ 24 giờ, 7 ngày hoặc 30 ngày, nút Tạo và lưu báo cáo, khu vực kết quả và lịch sử. Kết quả gồm thống kê, nhóm xu hướng, cảnh báo theo loại, nội dung quy tắc và bảng dữ liệu. Mở một báo cáo cũ cập nhật bộ chọn kỳ theo báo cáo đó; hành vi này không tạo mới báo cáo.')
    p('Trong lúc tạo hoặc mở báo cáo, các nút liên quan và bộ chọn địa điểm được khóa để giữ ngữ cảnh. Tải CSV chỉ được bật khi có bản ghi; in chỉ được bật khi có báo cáo hiện tại. Lịch sử hỗ trợ Xem thêm theo offset. Lỗi vượt thời gian chờ giữ khả năng tải lại lịch sử để xác định một báo cáo có thể đã được lưu. UI07 phục vụ UC10–UC12; dữ liệu trao đổi với /api/baocao và /api/baocao/<id>.')
    h('9.9 UI08 Chatbot Xanh Non')
    p('Bong bóng ở góc phải mở một cửa sổ có tên Xanh Non, lịch sử tin nhắn, gợi ý hỏi, ô nhập, nút gửi và nút đóng. Người sử dụng nhấn Enter để gửi, Shift+Enter để xuống dòng. Đang trả lời có trạng thái chờ và thao tác dừng. Khi câu trả lời bị cắt do giới hạn sinh, giao diện có thao tác tiếp tục. Bắt đầu lại xóa ngữ cảnh trên widget của nơi đang chọn.')
    p('Thu gọn chỉ ẩn cửa sổ; quá trình nhận phản hồi vẫn tiếp tục và dấu báo phản hồi mới được cập nhật. Các tin nhắn được giữ riêng theo địa điểm trong bộ nhớ của trang. Lời xác nhận hữu ích được gửi như tin nhắn, không dùng bộ nút chấm điểm riêng. UI08 phục vụ UC13–UC16 và các nhánh /api/chat. Widget hiển thị văn bản bằng textContent; đầu ra mô hình không được thực thi như HTML.')
    h('9.10 Đặc tả các thành phần điều khiển dùng chung')
    table('Hành vi thành phần giao diện',['Thành phần','Điều kiện và thao tác','Kết quả hoặc ngoại lệ'],[
      ('Nút menu và X','Nhấn menu khi đang đóng; nhấn X hoặc Esc khi đang mở','Mở hoặc đóng drawer; ẩn nút menu khi mở; trả focus khi đóng.'),
      ('Tìm kiếm đầu trang','Nhập từ khóa, di chuyển bằng phím và Enter','Gợi ý địa điểm hoặc chức năng; không có kết quả thì giữ lựa chọn hiện tại.'),
      ('Danh sách địa điểm','Danh mục sẵn sàng, không có tác vụ khóa','Lưu mã, phát locationchange và tải lại nội dung liên quan.'),
      ('Lấy vị trí hiện tại','Trang an toàn, chưa có yêu cầu định vị đang chạy','Xin quyền; tự chọn mục gần nhất; lỗi vẫn cho chọn thủ công.'),
      ('Cập nhật dữ liệu','Không tải trùng cùng phiên','Đổi trạng thái chờ rồi hiển thị snapshot hoặc thông báo lỗi.'),
      ('Chuông và nút đóng','Nhấn chuông mở; X, Esc đóng','Hiện lịch sử đúng nơi; số đếm không là số chưa đọc có lưu bền.'),
      ('Công tắc và độ đậm AQI','Lớp bản đồ đã khởi tạo','Ẩn hoặc hiện; đổi alpha lớp phủ, không thay giá trị nguồn.'),
      ('Marker bản đồ','Nhấn tại dấu tham chiếu','Mở popup tên, tọa độ và nguồn; không mở CRUD trạm.'),
      ('Tạo báo cáo','Kỳ hợp lệ và không đang bận','POST, lưu SQL, HTTP 201; lỗi hiển thị tại báo cáo.'),
      ('Mở và Xem thêm','Có lịch sử; không đang bận','Đọc nội dung hoặc tăng phân trang; 404 không tự mở nơi khác.'),
      ('CSV và In','Đã có báo cáo; CSV cần có dữ liệu','Tải tệp hoặc mở hộp thoại in; không gọi endpoint xuất PDF.'),
      ('Gửi Dừng Bắt đầu lại','Theo trạng thái của phiên hội thoại','Gửi stream, hủy nhận hoặc xóa ngữ cảnh đang giữ trong trang.')],[1.6,2.4,2.6])
    p('Các trạng thái hiển thị gắn với kết quả từng thành phần. Ứng dụng không có chế độ offline đầy đủ; khi mất kết nối, dữ liệu đã tải trong cùng trang có thể còn được hiển thị cùng lỗi tải mới. Phần thanh cuộn được ẩn về hình thức nhưng thao tác cuộn vẫn được giữ. Kiểm tra giao diện được thực hiện ở cả kích thước máy tính và điện thoại.')

def ch10():
    chapter(10,'Thiết kế xử lý và giám sát môi trường')
    h('10.1 Nguồn và ý nghĩa các thông số')
    table('Thông số và đặc tính nguồn dữ liệu',['Thông số','Nguồn và đơn vị','Ý nghĩa trong ứng dụng'],[
      ('Nhiệt độ','Open-Meteo, °C','temperature_2m tại tọa độ tham chiếu.'),('Độ ẩm','Open-Meteo, %','relative_humidity_2m; dữ liệu nguồn thời tiết.'),('PM2.5 và PM10','Open-Meteo Air Quality, µg/m³','Nồng độ bụi mô hình tại vị trí tham chiếu.'),('US AQI','Open-Meteo Air Quality, chỉ số không thứ nguyên','Chỉ số do nguồn trả về; ứng dụng dùng để chọn mức và diễn giải.'),('CO NO2 SO2 O3','Open-Meteo Air Quality','Các trường bổ sung nằm trong DuLieu và snapshot JSON, không là năm thẻ chính.'),('Tiếng ồn','NoiseCapture, dBA','Tổng hợp theo vùng từ các ô có số lần đo và metadata thời gian.')],[1.4,2.3,2.9])
    p('Tài liệu Open-Meteo xác định các biến thời tiết, biến chất lượng không khí và dữ liệu dự báo. NoiseCapture cung cấp dữ liệu cộng đồng có vị trí; ứng dụng lấy tệp Việt Nam và tự tổng hợp vùng tham chiếu [T01]–[T03]. Quy trình của dự án không tiếp nhận MQTT hoặc gói tin trực tiếp từ thiết bị IoT.')
    h('10.2 Tiếp nhận và kiểm tra dữ liệu')
    p('fetch_environment thực hiện hai yêu cầu HTTP với timeout 15 giây cho thời tiết và không khí. Dữ liệu hiện tại được ghép vào dictionary, giữ riêng ThoiGianNguonThoiTiet và ThoiGianNguonKhongKhi. NoiseData quản lý bản tải quốc gia dùng chung, kiểm tra tệp mới trước khi thay tệp cũ và dùng lại bản có sẵn khi cập nhật nguồn thất bại. Chu kỳ làm mới tệp tiếng ồn là 24 giờ; điều này không thay đổi thời điểm các phép đo bên trong nguồn.')
    p('Mức kiểm tra được thực hiện ở từng nhánh: dữ liệu NoiseCapture phải có tọa độ và giá trị hữu hạn, trọng số dương; RF yêu cầu đủ năm số hữu hạn; thống kê báo cáo loại None, boolean và giá trị không hữu hạn. Nhánh dự báo thời tiết kiểm tra đơn vị, độ dài mảng và UTC+7. Nhánh không khí kiểm tra hình dạng dữ liệu và thời gian nguồn. Bộ thu thập snapshot không phải một cổng chuẩn hóa cảm biến có kiểm định chất lượng đo.')
    h('10.3 Tổng hợp tiếng ồn theo năng lượng')
    p('Với mỗi ô tiếng ồn, hệ thống xác định tâm hình học và khoảng cách đến tọa độ tiếng ồn của địa điểm. Chỉ các ô trong bán kính được cấu hình mới tham gia tổng hợp. Gọi Li là mức của ô và wi là số lần đo, kết quả được tính bằng 10 log10 của tỷ số giữa tổng wi × 10 mũ (Li/10) và tổng wi. Việc tính trên năng lượng tránh dùng trung bình cộng trực tiếp các mức decibel.')
    p('Kết quả đi cùng số ô, số lần đo, bán kính, lần đo đầu và lần đo gần nhất. Nếu không có ô phù hợp thì trả None. Phép tổng hợp này mô tả tập dữ liệu vùng đã có; nó không khẳng định mức ồn tại đúng vị trí thiết bị của người sử dụng hoặc tại thời điểm hiện tại.')
    h('10.4 Quy tắc sinh cảnh báo')
    table('Ngưỡng cảnh báo nội bộ được khai báo trong mã nguồn',['Thông số','Mức Trung bình từ','Mức Cao từ','Đơn vị'],[
      ('PM2.5','35,5','55,5','µg/m³'),('PM10','100','154','µg/m³'),('Nhiệt độ','35','38','°C'),('Độ ẩm','85','95','%'),('Tiếng ồn','70','85','dBA')],[2.3,1.5,1.4,1])
    p('Hàm build_alerts kiểm tra mức cao trước, sau đó mức lưu ý. Một thông số chỉ tạo tối đa một cảnh báo trong một snapshot; giá trị thiếu được bỏ qua. Các ngưỡng trong bảng là ngưỡng vận hành của dự án, không được xác định như giới hạn quy chuẩn pháp luật. Đặc biệt, mức tiếng ồn tổng hợp có thời gian thu thập khác nhau nên không được coi là bằng chứng vượt quy chuẩn tại thời điểm cập nhật ứng dụng.')
    h('10.5 Phân tích US AQI và nhánh giá trị thay thế')
    table('Các mức US AQI được giao diện sử dụng',['Khoảng chỉ số nguyên','Tên trong ứng dụng','Màu'],[
      ('0–50','Tốt','Xanh lá'),('51–100','Trung bình','Vàng'),('101–150','Kém','Cam'),('151–200','Xấu','Đỏ'),('201–300','Rất xấu','Tím'),('Trên 300','Nguy hại','Đỏ sẫm')],[1.6,2.8,1.5])
    p('Sáu khoảng AQI được đối chiếu với tài liệu AirNow; tên tiếng Việt là cách đặt nhãn trong ứng dụng [T08]. US AQI khác nồng độ PM2.5 tại một giờ. Một giá trị bụi đơn lẻ hoặc một màu bản đồ không phải kết luận tuân thủ hay vi phạm quy chuẩn môi trường.')
    p('build_analysis ưu tiên US_AQI của nguồn. Khi trường này thiếu, hàm đang gán các mức AQI đại diện theo khoảng PM2.5 là 25, 75, 125, 175 hoặc 250. Đây là nhánh quy tắc thay thế trong mã, không phải phép tính đầy đủ chỉ số US AQI. Nếu cả PM2.5 cũng trống, biểu thức hiện tại dùng 0 ở bước này; nhãn phân tích khi đó không xác nhận đã có dữ liệu không khí. Trên giao diện và trong hội thoại, trạng thái thiếu của giá trị nguồn vẫn có ý nghĩa riêng.')
    h('10.6 Phân loại Random Forest')
    p('Mô hình nhận năm đặc trưng theo đúng thứ tự: pm25, pm10, temperature_c, humidity_pct và noise_db. Bundle chứa air_quality_model và noise_level_model. Nhãn chất lượng không khí có bốn mức, nhãn tiếng ồn có ba mức. Các nhãn này được tạo theo quy tắc của bộ dữ liệu huấn luyện minh họa nên số mức và ý nghĩa không trùng hoàn toàn với sáu mức US AQI.')
    p('Nếu thiếu tiếng ồn ở một nơi, hệ thống không suy đoán thêm để đủ đầu vào mô hình. predict_environment trả thieu_du_lieu và danh sách trường thiếu. Lỗi model bundle hoặc suy luận được chuyển thành loi_mo_hinh trong snapshot; dữ liệu từ các nguồn vẫn được lưu. Kết quả RF là phân loại một hàng đầu vào, không phải mô hình dự báo diễn biến các ngày tiếp theo.')
    h('10.7 Thống kê và báo cáo theo thời gian')
    p('Báo cáo chuẩn hóa các giá trị hợp lệ, đếm số thiếu và tính min, max, giá trị gần nhất cho từng thông số. Với các thông số ngoài tiếng ồn, hệ thống tính trung bình cộng các snapshot có dữ liệu và độ thay đổi giữa lần đầu với lần cuối. Tiếng ồn không được tính lại trung bình cộng hoặc độ thay đổi vì giá trị đã là tổng hợp vùng. Thống kê này mô tả các snapshot được thu, không phải trung bình có trọng số theo thời gian quan trắc liên tục.')
    p('Kỳ 24 giờ nhóm xu hướng PM2.5 theo giờ; kỳ 7 và 30 ngày nhóm theo ngày. Mỗi nhóm có số bản ghi, số giá trị PM2.5 hợp lệ, trung bình và cực đại. Cảnh báo được lọc lại theo các mã nguồn trong kỳ để tránh ghép sự kiện không thuộc dữ liệu báo cáo. Báo cáo còn giữ số nguồn, số bản ghi có cảnh báo và tỷ lệ, cùng nội dung quy tắc có căn cứ từ chính thống kê này.')

def ch11():
    chapter(11,'Thiết kế chatbot tư vấn Xanh Non')
    h('11.1 Kiến trúc trả lời kết hợp')
    p('Xanh Non kết hợp nhận diện ý định bằng quy tắc, tra cứu tri thức, đọc dữ liệu môi trường và mô hình ngôn ngữ cục bộ. Quy trình không bắt buộc đi qua mô hình sinh ở mọi câu hỏi. Những nội dung đã được xác định chắc chắn, như giao tiếp cơ bản, chức năng ứng dụng, số liệu cần đọc, dự báo theo cửa sổ giờ hoặc một đáp án kiến thức phù hợp, được trả trực tiếp. Nhánh chưa có đáp án trực tiếp mới xây dựng ngữ cảnh và gọi runtime.')
    p('Manifest đang hoạt động xác định XanhNon-Style-v2, với nền Qwen2.5 0.5B và bản GGUF F16 dùng bởi llama.cpp. Bản phát hành có hash để nhận diện tệp; thông tin số bước học trong manifest là thông tin của bản đã phát hành. Một đợt chuẩn bị dữ liệu hoặc kiểm tra token mới không đồng nghĩa bản mô hình đó đã được thay thế. NativeChatbot quản lý tiến trình cục bộ, còn Flask giao tiếp với tiến trình qua HTTP loopback [T09].')
    h('11.2 Chuỗi quyết định của câu trả lời')
    steps(['Kiểm tra cấu trúc yêu cầu và tách câu hỏi khỏi lịch sử giới hạn. Với lời xác nhận hữu ích, ghi nhận theo nhánh góp ý riêng.','Giải nghĩa câu nối tiếp, chủ đề và chi tiết còn thiếu. Nếu cần, hỏi lại trước khi kết luận.','Nhận biết giao tiếp cơ bản, câu giới thiệu chức năng hoặc câu ngoài phạm vi.','Trong phạm vi, ưu tiên các nhánh dữ liệu người dùng nêu, thời tiết, không khí, tư vấn và kiến thức phù hợp.','Khi cần mô hình, tạo thông điệp hệ thống và phần dữ liệu chỉ liên quan đến câu hỏi; không đưa toàn bộ bộ dữ liệu chat thô vào ngữ cảnh.','Nhận nội dung trực tiếp hoặc token sinh, làm sạch đầu ra và trả JSON hoặc SSE thống nhất.'])
    h('11.3 Quản lý ngữ cảnh nhiều lượt')
    p('Ngữ cảnh được giải từ lượt người sử dụng, kết hợp chủ đề, địa điểm và mốc thời gian. Câu hỏi mới có thể thay một phần ngữ cảnh mà vẫn giữ những phần còn liên quan. Ví dụ, sau một câu về thời tiết ngày mai ở Đà Nẵng lúc 18:30, câu “độ ẩm thì sao” giữ Đà Nẵng, ngày mai và khoảng 18:00–19:00. Câu “không khí nữa” đổi lĩnh vực dữ liệu nhưng có thể tiếp tục dùng cùng địa điểm, ngày và giờ.')
    p('Nếu hỏi “19 giờ thì sao”, giờ mới thay cho giờ cũ. Nếu hỏi “hiện tại”, mốc dự báo không còn áp dụng. Khi chỉ nêu một giờ mà chưa có ngày rõ ràng, hệ thống có thể hỏi người sử dụng muốn xem hôm nay hay ngày khác. Các câu cảm ơn được nhận diện riêng; việc chuyển sang một chủ đề không liên quan không tiếp tục kéo nội dung môi trường cũ vào câu trả lời.')
    table('Các biến ngữ cảnh và cách sử dụng',['Biến','Nguồn xác định','Điều kiện giữ hoặc thay'],[
      ('Địa điểm','Danh mục đang chọn hoặc tên được nêu rõ','Giữ khi câu nối tiếp không đổi nơi; tên mới phải được nhận diện từ danh mục.'),('Chủ đề','Câu hỏi hiện tại và lượt user liên quan','Giữ khi câu rút gọn còn liên quan; hỏi lại khi hai chủ đề cùng có thể đúng.'),('Ngày','Hôm nay, mai, ngày kia hoặc ngữ cảnh ngày','Thông tin ngày mới thay ngày cũ; câu hiện tại dùng mốc hiện tại.'),('Giờ và buổi','Giờ cụ thể hoặc buổi được nhận biết','Giữ khi hỏi thêm chỉ số; giờ mới thay giờ cũ; dữ liệu theo giờ nguồn.'),('Chỉ số cần trả','Từ khóa và trường được hỏi','Đổi từ nhiệt độ sang độ ẩm không thêm các chỉ số không được hỏi.'),('Mức chi tiết','Yêu cầu ngắn, kỹ hoặc đầy đủ','Điều chỉnh nội dung và giới hạn sinh trong phạm vi cấu hình.')],[1.1,2.4,3.1])
    h('11.4 Truy xuất dữ liệu và xử lý thiếu')
    p('Số liệu hiện tại lấy từ snapshot hoặc nguồn đọc theo câu hỏi. Dữ liệu dự báo được truy xuất riêng, cache 600 giây theo mã địa điểm, tọa độ và ngày. Thời tiết dự báo hiện dùng nhiệt độ và độ ẩm; không khí dự báo được đọc từ Open-Meteo/CAMS. Các chuỗi dữ liệu giờ phải phù hợp cửa sổ cần trả; thiếu giờ quan trọng không được tự nội suy thành một câu trả lời chắc chắn.')
    p('Câu hỏi về thời tiết chỉ trả trường thời tiết cần thiết. Câu hỏi thiếu dữ liệu được giải thích ở đúng phần cần dùng, không thêm nhận xét về một chỉ số người sử dụng không hỏi. Hỏi riêng độ ẩm không kéo tiếng ồn hoặc AQI vào phản hồi. Các câu dự báo có nhãn dự báo, tên nơi và ngày giờ tương ứng, để tách khỏi số liệu bảng giám sát.')
    h('11.5 Kho tri thức và tư vấn chuyên môn')
    p('knowledge.json chứa 26 tài liệu cùng mã nguồn tham chiếu. Nội dung được tìm bằng câu mẫu, chủ đề, các quy tắc và TF-IDF trên n-gram ký tự từ 3 đến 5. Cơ chế này là tra cứu văn bản có kiểm soát; dự án không vận hành một cơ sở dữ liệu vector độc lập. reference_context đưa các đoạn phù hợp vào phần ngữ cảnh khi cần mô hình sinh.')
    p('Các đáp án tư vấn có thể điều chỉnh theo nội dung người sử dụng vừa nêu, chẳng hạn muốn giảm bụi gần đường lớn nhưng chưa có máy lọc. Việc sử dụng tình huống trong hội thoại không tạo hồ sơ cá nhân hoặc hệ gợi ý theo tài khoản. Nguồn được lưu ở mức tài liệu tri thức; không có định dạng trích dẫn bấm được được bảo đảm trong mọi câu trả lời của widget.')
    h('11.6 Dữ liệu hội thoại và dữ liệu cảm biến dùng cho học')
    table('Nhóm dữ liệu và vai trò trong quy trình học',['Nhóm nguồn','Vai trò có trong dự án','Giới hạn sử dụng'],[
      ('Vietnamese Multi-turn và Vietnamese Chatting đã lọc','Bổ sung cách diễn đạt và nối lượt trong tập hội thoại','Không làm nguồn khẳng định chuyên môn hoặc số liệu hiện tại.'),
      ('Hỏi đáp môi trường của dự án','Dạy cách trả lời AQI, PM2.5, thiếu dữ liệu và nhánh tư vấn','Kiến thức có nguồn; các con số theo thời gian phải là tình huống giả định rõ ràng.'),
      ('iSCAPE Outdoor Sensor Deployment','Nguồn dữ liệu cảm biến ngoài trời trong kho đã khôi phục [T10]','Dữ liệu lịch sử của dự án nghiên cứu; không là số liệu hiện tại tại Việt Nam.'),
      ('iSCAPE Citizen Science Workshops','Dữ liệu các hoạt động cảm biến cộng đồng [T11]','Các kênh có thể khác theo thiết bị; không tự gán trường thiếu.'),
      ('iSCAPE Low Cost Sensor Development','Dữ liệu thử nghiệm và phát triển cảm biến [T12]','Điều kiện thí nghiệm khác môi trường sử dụng thực tế.'),
      ('Beijing Multi-Site Air Quality','Bổ sung dữ liệu bụi và khí tượng trong kho nguồn [T13]','Không có trường tiếng ồn hoặc độ ẩm tương đối trực tiếp như đầu vào năm đặc trưng.')],[2,2.5,2.1])
    p('Các bộ dữ liệu thô được kiểm tra trùng và chuẩn hóa trước khi chuyển thành mẫu. Sự có mặt của một bộ dữ liệu trong kho không xác nhận toàn bộ hàng của nó đã tham gia huấn luyện bản đang hoạt động. Hồ sơ khôi phục ghi nhận 21 phiên bản dữ liệu và 388 tệp nguồn, trong khi tập JSONL mặc định đã chuẩn bị gồm 452 mẫu train và 124 validation. Đây là các đơn vị đếm khác nhau.')
    h('11.7 Học từ chat và quy trình huấn luyện')
    p('ConversationLearner quan sát câu hỏi phù hợp khi cờ learn_from_chat được bật. Câu hỏi có số liệu hiện tại hoặc dự báo được chuyển sang trạng thái cần dữ liệu; nội dung cần nguồn được giữ chờ xử lý. Chỉ câu hỏi có thể gắn với một đáp án kiến thức ổn định có nguồn mới được dùng như biến thể learned. Hash kho tri thức và phiên bản chính sách là điều kiện để tái sử dụng đáp án đó.')
    p('Góp ý có chuỗi trạng thái pending, approved hoặc rejected. Khi duyệt, công cụ yêu cầu kiểm tra nội dung và thông tin riêng tư, nguồn tham chiếu hợp lệ và chính sách cho dữ liệu thời gian. Góp ý đã duyệt có thể được chuyển thành mẫu học. Tinh chỉnh LoRA là bước riêng với dữ liệu, checkpoint và kiểm thử; trọng số không cập nhật tức thời sau mỗi cuộc trò chuyện [T14].')
    picture('17_training.png','Quy trình dữ liệu học và huấn luyện cục bộ',maxheight=5.4)
    h('11.8 Kiểm soát đầu ra và phạm vi an toàn')
    p('Đầu vào được giới hạn kích thước, vai trò lịch sử phải luân phiên đúng cặp và đầu ra được xử lý như văn bản. chat_output làm sạch một số phần lặp, lời dẫn thừa và hướng dẫn nội bộ. Nội dung cần giá trị hiện tại được ưu tiên nhánh đọc dữ liệu để giảm phụ thuộc mô hình nhớ con số. Các biện pháp này là kiểm soát cụ thể trong mã; chúng không tạo bảo đảm rằng mô hình không thể sai hoặc không chịu ảnh hưởng của chỉ dẫn độc hại.')
    p('Ứng dụng không có đăng nhập nên việc kiểm tra Origin ở các nhánh ghi góp ý và câu hỏi không phải cơ chế phân quyền người dùng. CORS được bật ở Flask; phạm vi triển khai hiện tại là máy cục bộ. Kho học lọc một số mẫu thông tin nhạy cảm và tách khỏi tập kiểm tra, nhưng hội thoại không được mô tả như đã có cơ chế ẩn danh hóa toàn diện hoặc chứng nhận bảo mật.')

def ch12():
    from test_catalog import CASES
    chapter(12,'Kiểm thử và truy vết yêu cầu')
    h('12.1 Phạm vi và tổ chức kiểm thử')
    p('Kiểm thử được tổ chức theo bốn lớp: đơn vị xử lý thuần và dữ liệu; tích hợp API với các phụ thuộc được mock; giao diện trình duyệt với dữ liệu kiểm soát; và đối chiếu API, SQL, mô hình thật trong các hồ sơ chạy đã lưu. Cách chia này tách việc kiểm tra quy tắc khỏi sự thay đổi của nguồn ngoài và chi phí nạp mô hình.')
    p('Dữ liệu kiểm thử bao gồm mã địa điểm hợp lệ và sai, giá trị đúng ngưỡng, trường thiếu, mảng dự báo thiếu giờ, phản hồi API lỗi, chuỗi nhiều lượt và các payload không đúng kiểu. Các kịch bản trình duyệt dùng Edge ở kích thước máy tính và điện thoại. Bộ kiểm thử có mock không được tính như một lần đo tốc độ suy luận hoặc một lần xác minh dữ liệu thật của nguồn.')
    h('12.2 Kết quả có bằng chứng')
    verify=BASE/'qa/document-evidence-tests.json'
    fresh=json.loads(verify.read_text(encoding='utf-8')) if verify.is_file() else None
    rows=[('Hồ sơ khôi phục 27/10','209 kiểm thử Python duy nhất; 13 kiểm tra JavaScript đạt','restoration-state.json; ba log kiểm thử và javascript-tests.txt'),('Giao diện 27/10','Kiểm tra 1.600 px và 390 px, menu, chuông, tìm kiếm, đồ thị, chat và không tràn ngang','browser-checks.json'),('Dữ liệu và hội thoại thật 27/10','HTTP giám sát và RF; tám câu chat; đối chiếu JSON/SSE','live-verification.json'),('Tiền kiểm tra dữ liệu học','452 mẫu train, 124 validation đã token hóa; chưa là lần học trọng số mới','preflight.json; restoration-state.json')]
    if fresh:
        rows.insert(1,('Chạy kiểm tra phục vụ lập hồ sơ',f'{fresh["passed"]}/{fresh["tests_run"]} kiểm thử đạt; {fresh["failures"]} thất bại; {fresh["errors"]} lỗi', 'qa/document-evidence-tests.json; qa/document-evidence-tests.txt'))
    table('Tổng hợp các kết quả đã ghi nhận',['Đợt kiểm tra','Kết quả','Bằng chứng'],rows,[1.7,2.7,2.2])
    p('Con số 209 là tổng số ca duy nhất trong hồ sơ khôi phục, không phải tổng cộng trực tiếp 177, 30 và 5 vì có ca trùng giữa các lần chạy. Bộ kiểm tra phục vụ biên soạn được ghi riêng, không cộng vào con số đó như một nhóm ca mới. Các hash của những tệp chính trong hồ sơ đã được đối chiếu với phiên bản đang khảo sát.')
    if fresh and fresh['failures']:
        pp=p('Lần chạy bổ sung có một ca không đạt kỳ vọng trong test_chat_intents.py: câu “Ở Đà Nẵng hôm nay nên làm gì?” mong _grounded_reply trả None khi snapshot đầu vào thuộc nơi khác. Nhánh hiện tại đã đọc được AQI của Đà Nẵng và trả tư vấn, nên không khớp điều kiện khẳng định của bài thử. Kết quả được giữ nguyên là một ca không đạt; không gộp lần chạy này vào kết quả 209 ca của hồ sơ trước.')
        pp.alignment=WD_ALIGN_PARAGRAPH.LEFT
    p('Trong tám câu chat thật được lưu, thời gian hoàn tất nằm từ 0,032 đến 2,218 giây. Các câu này chủ yếu đi qua nhánh quy tắc, tra cứu hoặc nguồn dự báo có cache, nên không đại diện cho tốc độ sinh tự do của mô hình. Kết quả không được sử dụng như chứng nhận độ chính xác chuyên môn hoặc độ trễ cam kết của toàn hệ thống.')
    h('12.3 Danh mục tình huống kiểm thử và nghiệm thu')
    p('Mỗi dòng dưới đây quy định điều kiện trước hoặc dữ liệu, thao tác, kết quả mong đợi và tình trạng bằng chứng. Trạng thái “đặc tả nghiệm thu” có nghĩa hồ sơ chưa chứa kết quả chạy riêng đầy đủ cho tình huống đó. Các bộ đơn vị có mock sử dụng dữ liệu cố định hoặc kho tạm; chúng không sửa cơ sở dữ liệu nghiệp vụ đang chạy.')
    for start,subtitle in [(0,'Địa điểm giám sát và bản đồ'),(10,'Xu hướng cảnh báo và báo cáo'),(17,'Hội thoại dữ liệu học và vận hành')]:
        end={0:10,10:17,17:28}[start]
        table('Tình huống kiểm thử '+subtitle.lower(),['Mã và yêu cầu','Điều kiện trước và đầu vào','Bước thực hiện và kết quả mong đợi','Bằng chứng và trạng thái'],[
          (cid+'\n'+fr,setup,action,status+'.\n'+evidence) for cid,fr,setup,action,evidence,status in CASES[start:end]],[1.05,1.8,2.3,1.85])
    h('12.4 Ma trận tác nhân chức năng và phạm vi quyền')
    table('Tác nhân và nhóm chức năng',['Nhóm chức năng','A01 Người sử dụng','A02 Người vận hành','Hệ thống ngoài'],[
      ('FR01–02 Địa điểm','Sử dụng trên web','Không có quyền web riêng','GPS do trình duyệt cung cấp'),('FR03–09 Giám sát và bản đồ','Tra cứu và yêu cầu cập nhật','Khởi chạy và theo dõi dịch vụ','Open-Meteo, NoiseCapture, OSM'),('FR10–12 Báo cáo','Tạo mở xuất, không cần đăng nhập','Truy cập dữ liệu bằng quyền máy nếu có','Không có vai trò quản trị ngoài'),('FR13–16 Hội thoại và góp ý','Chat và xác nhận hữu ích','Duyệt góp ý bằng công cụ cục bộ','Open-Meteo cho dữ liệu cần đọc'),('FR17–18 Runtime và huấn luyện','Không có màn hình huấn luyện','Chạy lệnh và quản lý dữ liệu mô hình','Nguồn dữ liệu tải về, không có API ChatGPT')],[1.7,1.6,1.8,1.5])
    h('12.5 Ma trận truy vết xuyên suốt')
    p('Ma trận sau đồng thời thể hiện quan hệ chức năng với giao diện, API, lớp hoặc module, dữ liệu và kiểm thử. Các UC dùng cùng hậu tố với FR. Nhóm luồng tham chiếu là L1 tra cứu và cập nhật, L2 bản đồ và xu hướng, L3 báo cáo, L4 hội thoại, L5 dữ liệu học và vận hành. Sequence, Activity và State ở chương 6 giải thích các tương tác tương ứng.')
    table('Truy vết yêu cầu đến thiết kế và kiểm thử',['FR và UC','UI và luồng','API hoặc module xử lý','Kho dữ liệu','Kiểm thử'],[
      ('01–02','UI01; L1','/diadiem; locations.js; LocationStore','D1; localStorage','TC01–03'),('03–04','UI01–02; L1','/capnhat; /dulieu/moinhat; app.py','D1 D2 D3','TC04–07'),('05–06','UI03; L2','/bando/khongkhi; AirMapRepository; map.js','D4; ảnh nền OSM','TC08–10'),('07','UI04; L2','/dulieu/lichsu; drawTrend','D2','TC11'),('08','UI06; L1','/canhbao; renderAlerts','D2 D3','TC12'),('09','UI05; L1','predict_environment; build_analysis','D2 D3 D8','TC06 TC13'),('10','UI07; L3','POST /baocao; ReportRepository.create','Đọc D2 D3; ghi D5','TC14–15'),('11','UI07; L3','GET /baocao và /baocao/<id>','Đọc D5','TC15–16'),('12','UI07; L3','reports.js; Blob; window.print','Snapshot báo cáo trên trình duyệt','TC17'),('13','UI08; L4','POST /chat; NativeChatbot','D2 D6 D8; lịch sử trong trang','TC18–19'),('14–15','UI08; L4','Các module chat_*; Open-Meteo','D2 D6; cache dự báo','TC20–23'),('16','UI08; L5','ConversationLearner; FeedbackStore','Đọc D6; ghi D7','TC24–25'),('17','API; L5','GET /chat/status; runtime_status','Trạng thái trong tiến trình','TC26'),('18','Công cụ; L5','train_xanhnon; export; model_release','Đọc D6 D7 D8; ghi ứng viên D8','TC27–28')],[.7,1.0,2.2,1.7,1.0])
    p('Các đường dẫn API rút gọn trong ma trận đều có tiền tố /api. D1 là danh mục địa điểm; D2 là snapshot; D3 là cảnh báo và phân tích; D4 là mẫu bản đồ; D5 là báo cáo; D6 là tri thức JSON; D7 là hai kho SQLite; D8 là dữ liệu học và mô hình. Mỗi nhóm có thể liên quan nhiều bảng hoặc nhiều API, không giả định quan hệ một–một.')

def ch13():
    chapter(13,'Triển khai và vận hành')
    h('13.1 Môi trường và cấu hình')
    p('Dự án chạy trên Windows với môi trường Python của ứng dụng, SQL Server, ODBC Driver 17 và trình duyệt. requirements.txt ghi các thư viện chạy, bao gồm scikit-learn 1.8.0 để khớp bundle Random Forest, Torch, Transformers, PEFT và các thư viện dữ liệu. Các binary llama.cpp, GGUF, tokenizer và mô hình cần có ở vị trí được cấu hình; Internet được dùng khi đọc các nguồn ngoài.')
    p('Kết nối SQL được điều khiển bằng DB_SERVER, DB_NAME, DB_DRIVER, DB_USER và DB_PASSWORD. Khi không khai báo tài khoản SQL, ứng dụng sử dụng xác thực Windows. Cấu hình chatbot cho phép chọn backend tự động, llama_cpp hoặc transformers; cấu hình GPU mặc định là 0 layer. Phiên bản triển khai hiện tại ưu tiên CPU, số luồng sinh mặc định là 4 và được giới hạn bởi tham số môi trường.')
    h('13.2 Khởi chạy và kiểm tra dịch vụ')
    steps(['Kích hoạt hoặc gọi trực tiếp Python trong .venv đã có các thư viện của dự án.','Xác nhận SQL Server và cơ sở dữ liệu GiamsatMT sẵn sàng; các schema nằm trong Demodatabase.sql, location_schema.sql, report_schema.sql và air_map_schema.sql.','Chạy .venv\\Scripts\\python.exe app.py rồi mở http://127.0.0.1:5000.','Đọc /api/chat/status và kiểm tra một lượt tải địa điểm để phân biệt tình trạng Flask, SQL, nguồn dữ liệu và runtime mô hình.'])
    p('Ứng dụng có nhánh kiểm tra dịch vụ hiện hữu trước khi khởi tạo thêm phiên chạy trực tiếp, nhằm tránh nạp trùng mô hình tại cổng ứng dụng. Các schema bổ sung được kiểm tra và tạo bằng ensure_schema trong quá trình sử dụng. Bản báo cáo chỉ khảo sát cơ chế này; việc biên soạn không thực hiện migration hoặc thay đổi dữ liệu nghiệp vụ.')
    h('13.3 Các trạng thái cần theo dõi')
    table('Dấu hiệu vận hành và ý nghĩa',['Thông tin','Vị trí quan sát','Ý nghĩa'],[
      ('HTTP Flask','127.0.0.1:5000 và log ứng dụng','Xác định dịch vụ web đang trả lời.'),('Runtime chatbot','/api/chat/status','Phân biệt cold, loading, ready, training, error.'),('Nguồn môi trường','ThoiGianNguonThoiTiet và ThoiGianNguonKhongKhi','Xác định thời điểm dữ liệu nguồn, khác thời điểm lấy snapshot.'),('Tiếng ồn','TiengOn_ChiTiet và tệp noise-vietnam.zip','Kiểm tra vùng, số mẫu, ngày đo và bản dữ liệu dùng lại.'),('Huấn luyện','Trạng thái JSON và lịch Windows','Phân biệt đang chạy, chưa có thay đổi dữ liệu, thiếu tài nguyên và kết thúc.'),('Bản mô hình hoạt động','models/xanhnon-active.json','Nhận diện tệp phát hành, hash và lịch sử kích hoạt.')],[1.6,2.5,2.5])
    h('13.4 Lịch tự động và giới hạn tài nguyên')
    p('Lịch Windows XanhNon-Train-Reviewed-Data gọi daily_train_xanhnon.py từ thư mục dự án. Script kiểm tra điều kiện tài nguyên và dấu vết dữ liệu trước khi học; cấu hình lịch hiện có dùng tập pilot giới hạn 128 mẫu train và 24 validation, không mặc định học lại toàn bộ kho ở mỗi lần gọi. Dữ liệu không đổi có thể được bỏ qua theo fingerprint.')
    p('Hồ sơ vận hành ngày 27/10/2026 ghi nhận lịch đã chạy và chuyển waiting_for_memory, model_activated=false. Bản phát hành XanhNon-Style-v2 tiếp tục được dùng. Tiền kiểm tra 576 mẫu đã thành công không được diễn giải thành việc lịch đã thực hiện bước tối ưu trọng số. Công cụ đánh giá, xuất và quản lý release là các bước tách biệt.')
    h('13.5 Lưu trữ sao lưu và phục hồi')
    p('Các nhóm tài sản cần nhận diện trong vận hành gồm dữ liệu SQL Server, hai SQLite, tri thức JSON, danh mục địa điểm, manifest phát hành, GGUF và checkpoint huấn luyện. Repository hiện có hồ sơ phục hồi, kiểm tra hash và các công cụ sao chép hoặc xuất tài sản mô hình; không có màn hình quản trị sao lưu SQL hoặc lịch sao lưu cơ sở dữ liệu được khai báo trong source ứng dụng.')
    p('Đợt phục hồi đã giữ lại một checkpoint trọng số gộp để làm điểm bắt đầu cho LoRA mới. Checkpoint gộp không khôi phục chính xác optimizer, RNG hoặc adapter riêng của lần học cũ. Công cụ training_resume xử lý trạng thái học nếu có đầy đủ tệp cần thiết; thiếu tài sản không được ghi nhận như một lần resume đúng trạng thái. Việc lưu snapshot SQL giúp sử dụng lại cache còn hạn sau khi khởi động lại ứng dụng.')
    h('13.6 Phạm vi bảo mật hiện có')
    p('Flask chỉ công bố thư mục static, không phục vụ toàn bộ thư mục dự án; native server chỉ lắng nghe loopback. Truy vấn nghiệp vụ dùng tham số và lỗi SQL được ghi log, còn người sử dụng nhận thông báo chung. CSV xử lý ký tự có nguy cơ bị hiểu như công thức, nội dung chat dùng textContent. Các thao tác ghi học và góp ý có kiểm tra Origin theo những nhánh được triển khai.')

def ch14():
    chapter(14,'Kết quả phân tích và thiết kế')
    p('Hồ sơ xác định hệ thống demoth1 là ứng dụng giám sát môi trường theo địa điểm, gồm giao diện web, API Flask, lưu trữ SQL Server, bản đồ AQI, báo cáo và trợ lý Xanh Non. Phần nghiệp vụ được phân tích thành 18 chức năng, tám màn hình hoặc phần giao diện, các quy tắc dữ liệu và điều kiện nghiệm thu tương ứng. Các sơ đồ thể hiện thống nhất giữa luồng cập nhật, quan hệ lưu trữ, quá trình tạo báo cáo và điều phối hội thoại.')
    p('Phân tích theo chức năng làm rõ dòng dữ liệu và thứ tự xử lý. Mô hình UML bổ sung trách nhiệm của các lớp triển khai, tương tác giữa thành phần và vòng đời runtime. ERD giữ nguyên sáu bảng SQL Server, phân biệt hai khóa ngoại vật lý với liên kết địa điểm ở tầng ứng dụng; hai kho SQLite được mô tả riêng theo nhiệm vụ góp ý và học câu hỏi.')
    p('Thiết kế giao diện được đối chiếu theo hành vi thực tế của menu, tìm kiếm, định vị, chuông cảnh báo, bản đồ, báo cáo và chat nổi. Phần dữ liệu phân biệt nguồn mô hình, tiếng ồn tổng hợp, snapshot ứng dụng và dự báo; các nhãn RF được tách khỏi US AQI. Phần chatbot phân biệt nhánh quy tắc, truy xuất tri thức, đọc dữ liệu theo ngữ cảnh và suy luận mô hình cục bộ.')
    p('Các kết quả kiểm thử được ghi theo hồ sơ thực tế, kèm điều kiện và phạm vi. Những nội dung như quản trị tài khoản, CRUD trạm, quy trình xử lý cảnh báo hoặc hồ sơ cá nhân không thuộc phiên bản được khảo sát. Báo cáo kết thúc ở cấu trúc và hành vi hiện có của hệ thống, với bảng API và danh mục bằng chứng mã nguồn làm căn cứ tra cứu.')

def appendices():
    para=h('PHỤ LỤC A  DANH MỤC API',1);para.paragraph_format.page_break_before=True
    p('Các hợp đồng dưới đây lấy từ các route Flask và blueprint hiện có. location không truyền dùng hanoi; mã không hợp lệ trả 400. Những giới hạn limit được chặn về miền cho phép ở API; không mô tả chúng như tham số phân trang tùy ý không giới hạn.')
    table('Các hợp đồng API của ứng dụng',['Phương thức và đường dẫn','Đầu vào và kiểm tra','Đầu ra và dữ liệu liên quan'],[
      ('GET /api/diadiem','Không có payload','Danh sách 86 địa điểm; chuẩn bị metadata qua LocationStore.'),
      ('GET hoặc POST /api/capnhat','location trong query; thuộc danh mục','Snapshot hoàn chỉnh; đọc ghi NguonDL, CanhBao, PhanTichAI; cache 600 giây.'),
      ('GET /api/dulieu/moinhat','location','Hàng NguonDL gần nhất hoặc {}; không cùng cấu trúc ngoài cùng với /capnhat.'),
      ('GET /api/dulieu/lichsu','location; limit mặc định 12, trong 1–500','Danh sách NguonDL được trả theo thứ tự cũ tới mới.'),
      ('GET /api/canhbao','location; limit mặc định 20, trong 1–200','Cảnh báo mới nhất theo địa điểm thông qua JOIN NguonDL.'),
      ('GET /api/phantich','location; limit mặc định 1, trong 1–50','Các hàng PhanTichAI mới nhất theo địa điểm.'),
      ('GET /api/bando/khongkhi','location; cả bốn south west north east nếu chỉ định phạm vi','Trục tọa độ, ma trận AQI/PM25, thời gian nguồn và cảnh báo thiếu; tối đa 196 điểm.'),
      ('POST /api/chat','JSON message history location; stream, learn_from_chat tùy chọn','JSON reply, truncated hoặc SSE status/delta/done/error; có giới hạn body, lịch sử và khóa sinh.'),
      ('GET /api/chat/status','Không có payload','state và có thể có background_training; không gọi sinh văn bản.'),
      ('POST /api/chat/feedback','JSON góp ý theo validate_feedback; Origin hợp lệ; tối đa 512 KiB','201 saved=true khi ghi được; kho SQLite, không công khai danh sách góp ý qua API.'),
      ('POST /api/baocao','JSON days là int 1, 7, 30; location','201 cùng MaBaoCao sau khi lưu BaoCaoMT.'),
      ('GET /api/baocao','location; limit mặc định 10, 1–50; offset 0–1.000.000','Danh sách metadata mới nhất; đọc BaoCaoMT.'),
      ('GET /api/baocao/<int:report_id>','Mã trên đường dẫn; location trong query','Nội dung snapshot đã lưu; 404 nếu không cùng nơi hoặc không tồn tại.')],[2.1,2.3,2.6])
    h('A.1 Dữ liệu câu hỏi và lịch sử')
    p('message bắt buộc là chuỗi có nội dung sau khi loại khoảng trắng. history là danh sách có số phần tử chẵn, tối đa 16, bắt đầu bằng user rồi assistant; mỗi content phải có nội dung và không dài quá 32.768 ký tự. Trường stream chỉ kích hoạt đường SSE khi bằng true. Các kiểm tra này chặn cấu trúc yêu cầu sai nhưng không phải xác thực danh tính.')
    h('A.2 Phân biệt dữ liệu trả về')
    p('/api/capnhat trả bộ kết quả điều phối đã ghép; /api/dulieu/moinhat trả hàng dữ liệu NguonDL. Khi cần snapshot đầy đủ từ hàng SQL, xử lý phải đọc và kiểm tra ChiTiet. /api/phantich trả danh sách phân tích lưu theo nguồn, không trực tiếp gọi mô hình ngôn ngữ. /api/baocao/<id> trả nội dung đã lưu để giữ khả năng tái hiện báo cáo.')
    para=h('PHỤ LỤC B  BẰNG CHỨNG MÃ NGUỒN',1);para.paragraph_format.page_break_before=True
    table('Danh mục mã nguồn phục vụ kiểm chứng',['Mã','Tệp và điểm xử lý','Nội dung đối chiếu'],[
      ('S01','app.py: capnhat, update_environment, fetch_environment','Nguồn dữ liệu, cache, giao dịch và snapshot.'),('S02','app.py: build_alerts, build_analysis, các route đọc','Ngưỡng, nhãn phân tích, giới hạn truy vấn và lọc địa điểm.'),('S03','location_catalog.py: get_location, LocationStore; locations.json','Danh mục, địa danh và đồng bộ SQL.'),('S04','noise_data.py: read_cells, aggregate_noise, NoiseData','Lọc vùng, tổng hợp năng lượng và cache tệp tiếng ồn.'),('S05','environment_predictor.py: load_model, predict_environment','Đặc trưng, nhãn, dữ liệu thiếu và bundle RF.'),('S06','air_quality_map.py: make_grid, AirMapRepository','Lưới, nguồn CAMS Global, số điểm và cache theo giờ.'),('S07','environment_reports.py: build_report, ReportRepository','Thống kê, kỳ, snapshot báo cáo và cách ly địa điểm.'),('S08','Demodatabase.sql; location_schema.sql; report_schema.sql; air_map_schema.sql','Sáu bảng, hai FK vật lý và các chỉ mục.'),('S09','static/index.html; dashboard.js; dashboard.css','Bố cục, điều hướng hash, menu, chuông và tìm kiếm.'),('S10','static/locations.js; script.js','Định vị, lựa chọn, cache trên giao diện, trạng thái tải và đồ thị.'),('S11','static/map.js; air-overlay.js; tests/test_air_overlay.cjs','Tương tác bản đồ, nội suy và thang màu.'),('S12','static/reports.js; static/chat.js','Báo cáo, xuất tệp, chat nổi, history và luồng SSE.'),('S13','chatbot.py: validate_chat, _generate_raw, _dialogue_question, stream_reply','Kiểm tra dữ liệu, thứ tự nhánh trả lời và ngữ cảnh.'),('S14','chat_scope.py; chat_clarification.py; chat_time_context.py','Phạm vi, câu hỏi làm rõ và mốc thời gian.'),('S15','chat_air_data.py; chat_weather_data.py','Nguồn hiện tại, dự báo, cache và kiểm tra chuỗi giờ.'),('S16','chat_knowledge.py; chat_output.py; data/xanhnon/knowledge.json','Tra cứu TF-IDF, tài liệu có nguồn và xử lý đầu ra.'),('S17','chat_feedback.py; chat_learning.py; feedback_training_data.py','Góp ý, câu hỏi mới, trạng thái duyệt và dữ liệu học.'),('S18','native_chatbot.py; model_release.py; models/xanhnon-active.json','Tiến trình suy luận, vòng đời và nhận diện bản phát hành.'),('S19','train_xanhnon.py; daily_train_xanhnon.py; export_xanhnon.py','Tinh chỉnh, lịch tự động, kiểm tra tài nguyên và xuất ứng viên.'),('S20','training_state.py; training_resume.py; sensor_training_data.py','Khóa học, điều kiện resume và xử lý nguồn cảm biến.')],[.65,3.2,2.75])
    h('B.1 Hồ sơ kiểm thử được sử dụng')
    p('Thư mục recovery/history-restoration-20261027 chứa restoration-state.json, live-verification.json, browser-checks.json, runtime-tests-final.txt, backend-tests-final.txt, training-seed-export-tests.txt và javascript-tests.txt. Các ảnh home-live-desktop.png, home-live-mobile.png và trends-restored-1600.png được lấy từ cùng hồ sơ. Kết quả bổ sung phục vụ tài liệu được lưu trong docs/system-analysis-design/qa/document-evidence-tests.json và log tương ứng.')
    h('B.2 Phạm vi đối chiếu phiên bản')
    p('Các tệp chính được kiểm tra SHA-256 với danh mục source_sha256 của hồ sơ khôi phục. Kiểm tra tại thời điểm biên soạn không ghi nhận thay đổi ở các tệp có trong danh mục đó. Việc này xác định phạm vi mã đã đối chiếu, không có nghĩa mọi tệp trong toàn bộ repository đều đã được kiểm toán bảo mật.')
    para=h('TÀI LIỆU THAM KHẢO',1);para.paragraph_format.page_break_before=True
    refs=[
      ('T01','Open-Meteo. Weather Forecast API. Tài liệu biến thời tiết và dữ liệu theo giờ.','https://open-meteo.com/en/docs'),
      ('T02','Open-Meteo. Air Quality API. Tài liệu biến chất lượng không khí, AQI và dữ liệu mô hình.','https://open-meteo.com/en/docs/air-quality-api'),
      ('T03','Noise-Planet. NoiseCapture. Giới thiệu dữ liệu cộng đồng và phương pháp thu thập.','https://noise-planet.org/noisecapture.html'),
      ('T04','Object Management Group. Unified Modeling Language version 2.5.1. 2017.','https://www.omg.org/spec/UML/2.5.1'),
      ('T05','Pallets Projects. Modular Applications with Blueprints. Flask Documentation.','https://flask.palletsprojects.com/en/stable/blueprints/'),
      ('T06','Microsoft. Primary and foreign key constraints. SQL Server documentation.','https://learn.microsoft.com/en-us/sql/relational-databases/tables/primary-and-foreign-key-constraints'),
      ('T07','Leaflet. API reference for Leaflet 1.9.4.','https://leafletjs.com/reference.html'),
      ('T08','AirNow. Air Quality Index Basics. Tài liệu về sáu mức US AQI.','https://www.airnow.gov/aqi/aqi-basics/'),
      ('T09','ggml-org. llama.cpp. Mã nguồn và hướng dẫn chạy mô hình cục bộ.','https://github.com/ggml-org/llama.cpp'),
      ('T10','González, Óscar và cộng sự. iSCAPE Outdoor Sensor Deployment Data. Zenodo, 2019.','https://zenodo.org/records/3570700'),
      ('T11','González, Óscar và cộng sự. iSCAPE Citizen Science Workshops Data. Zenodo, 2019.','https://zenodo.org/records/3570680'),
      ('T12','González, Óscar; Barberán, Víctor; Camprodon, Guillem. iSCAPE Low Cost Sensor Development Data. Zenodo, 2019.','https://zenodo.org/records/3570688'),
      ('T13','UCI Machine Learning Repository. Beijing Multi-Site Air Quality. Dataset 501, 2019.','https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data'),
      ('T14','Hugging Face. Low-Rank Adaptation. PEFT documentation.','https://huggingface.co/docs/peft/main/en/conceptual_guides/lora'),
      ('T15','Themesberg. Volt Bootstrap 5 Dashboard. Mã nguồn và giấy phép MIT.','https://github.com/themesberg/volt-bootstrap-5-dashboard')]
    p('Các tài liệu trực tuyến được kiểm tra ngày 27/10/2026. Mã nguồn dự án và các hồ sơ kiểm thử ở phụ lục B là nguồn chính cho các chức năng, cấu hình, số liệu và trạng thái triển khai được mô tả trong báo cáo.')
    for code,title,url in refs:
        pp=p(f'[{code}] {title} ');pp.alignment=WD_ALIGN_PARAGRAPH.LEFT
        hyperlink(pp,'Tài liệu gốc',url)

def source_audit():
    names=['app.py','location_catalog.py','noise_data.py','air_quality_map.py','environment_reports.py','environment_predictor.py','chatbot.py','chat_scope.py','chat_knowledge.py','chat_learning.py','chat_feedback.py','native_chatbot.py','static/index.html','static/dashboard.js','static/locations.js','static/script.js','static/reports.js','static/chat.js','Demodatabase.sql','location_schema.sql','report_schema.sql','air_map_schema.sql','models/xanhnon-active.json']
    audit={}
    for name in names:
        path=PROJECT/name
        row={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
        if path.suffix=='.py':
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            row['definitions']=[{'name':n.name,'line':n.lineno,'kind':type(n).__name__} for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))]
        audit[name]=row
    (BASE/'qa/source-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    source_audit()
    for name in ['home-live-desktop.png','home-live-mobile.png','menu-live-desktop.png','trends-restored-1600.png']:
        shutil.copy2(PROJECT/'recovery/history-restoration-20261027'/name,ASSETS/name)
    cover();ch1();ch2();ch3();ch4();ch5();ch6();ch7();ch8();ch9();ch10();ch11();ch12();ch13();ch14();appendices()
    for st in doc.styles:
        for border in st.element.xpath('.//w:pBdr'):border.getparent().remove(border)
    for para in doc.paragraphs:
        for border in para._p.xpath('.//w:pBdr'):border.getparent().remove(border)
    doc.save(TARGET)
    (BASE/'BAO_CAO_TONG_HOP.md').write_text('\n\n'.join(plain),encoding='utf-8')
    inventory={'output':str(TARGET),'paragraphs':len(doc.paragraphs),'tables':len(tables),'figures':len(figures),'figure_titles':figures,'table_titles':tables,'words':len(' '.join(plain).split())}
    (BASE/'qa/document-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(inventory|{'figure_titles':None,'table_titles':None},ensure_ascii=False))

if __name__=='__main__':main()
