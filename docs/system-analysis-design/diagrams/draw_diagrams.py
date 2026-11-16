from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math, json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
OUT.mkdir(exist_ok=True)
FONT = 'C:/Windows/Fonts/arial.ttf'
BOLD = 'C:/Windows/Fonts/arialbd.ttf'
INK = '#20262d'
FILL = '#f1f4f6'

class Canvas:
    def __init__(self, name, height, width=1800):
        self.name=name; self.im=Image.new('RGB',(width,height),'white'); self.d=ImageDraw.Draw(self.im)
    def font(self,size=39,bold=False): return ImageFont.truetype(BOLD if bold else FONT,size)
    def lines(self,text,width,size=39,bold=False):
        font=self.font(size,bold); result=[]
        for para in text.split('\n'):
            row=''
            for word in para.split():
                candidate=(row+' '+word).strip()
                if row and self.d.textlength(candidate,font=font)>width:
                    result.append(row); row=word
                else: row=candidate
            result.append(row)
        return result
    def text(self,box,text,size=39,bold=False,align='center'):
        x,y,w,h=box; lines=self.lines(text,w-24,size,bold); lh=round(size*1.28)
        while len(lines)*lh>h+5 and size>32:
            size-=1;lines=self.lines(text,w-24,size,bold);lh=round(size*1.28)
        assert len(lines)*lh<=h+16, (self.name,text,len(lines)*lh,h)
        yy=y+(h-len(lines)*lh)/2
        for line in lines:
            xx=x+12 if align=='left' else x+(w-self.d.textlength(line,font=self.font(size,bold)))/2
            self.d.text((xx,yy),line,font=self.font(size,bold),fill=INK); yy+=lh
    def box(self,x,y,w,h,text='',size=39,kind='rect',bold=False,fill='white'):
        if kind=='round': self.d.rounded_rectangle((x,y,x+w,y+h),radius=25,fill=fill,outline=INK,width=3)
        elif kind=='ellipse': self.d.ellipse((x,y,x+w,y+h),fill=fill,outline=INK,width=3)
        else: self.d.rectangle((x,y,x+w,y+h),fill=fill,outline=INK,width=3)
        if kind=='store':
            self.d.line((x+30,y,x+30,y+h),fill=INK,width=3)
        self.text((x+8,y+6,w-16,h-12),text,size,bold)
        return (x,y,w,h)
    def line(self,points,dashed=False,width=3):
        if not dashed: self.d.line(points,fill=INK,width=width,joint='curve'); return
        for a,b in zip(points,points[1:]):
            length=math.dist(a,b); n=max(1,int(length/14))
            for i in range(n):
                if i%2==0:
                    self.d.line((a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n,a[0]+(b[0]-a[0])*(i+1)/n,a[1]+(b[1]-a[1])*(i+1)/n),fill=INK,width=width)
    def arrow(self,points,label=None,labelbox=None,dashed=False):
        self.line(points,dashed)
        a,b=points[-2:]; angle=math.atan2(b[1]-a[1],b[0]-a[0]); k=17
        head=[b,(b[0]-k*math.cos(angle-.46),b[1]-k*math.sin(angle-.46)),(b[0]-k*math.cos(angle+.46),b[1]-k*math.sin(angle+.46))]
        self.d.polygon(head,fill=INK)
        if label and labelbox:
            x,y,w,h=labelbox; self.d.rectangle((x,y,x+w,y+h),fill='white'); self.text(labelbox,label,35)
    def entity(self,x,y,w,title,fields,size=39):
        header=75; lh=52; h=header+24+lh*len(fields)
        self.box(x,y,w,h)
        self.d.rectangle((x,y,x+w,y+header),fill=FILL,outline=INK,width=3)
        self.text((x+5,y+5,w-10,header-10),title,size,True)
        for i,field in enumerate(fields):
            primary=field.startswith('*'); field=field.lstrip('*')
            yy=y+header+12+i*lh
            self.d.text((x+22,yy),field,font=self.font(size),fill=INK)
            if primary:
                ww=self.d.textlength(field,font=self.font(size)); self.d.line((x+22,yy+size+5,x+22+ww,yy+size+5),fill=INK,width=2)
        return (x,y,w,h)
    def save(self):
        path=OUT/(self.name+'.png'); self.im.save(path,dpi=(300,300)); return str(path)

def bfd():
    c=Canvas('01_bfd',1430)
    c.box(35,580,365,230,'Hệ thống giám sát\nmôi trường đô thị',44, bold=True)
    groups=[
      ('1 Tra cứu theo địa điểm','FR01 Chọn và tìm kiếm\nFR02 Lấy địa điểm gần nhất\nFR04 Xem chỉ số môi trường'),
      ('2 Tiếp nhận và đánh giá','FR03 Cập nhật dữ liệu\nFR08 Tra cứu cảnh báo\nFR09 Phân loại Random Forest'),
      ('3 Bản đồ và xu hướng','FR05 Tương tác bản đồ\nFR06 Lớp màu AQI\nFR07 Biểu đồ PM2.5'),
      ('4 Báo cáo môi trường','FR10 Tạo và lưu báo cáo\nFR11 Mở báo cáo đã lưu\nFR12 Xuất CSV và in'),
      ('5 Hội thoại Xanh Non','FR13 Gửi và điều khiển hội thoại\nFR14 Hiểu ngữ cảnh và dự báo\nFR15 Kiến thức và tư vấn'),
      ('6 Dữ liệu học và vận hành','FR16 Tiếp nhận góp ý và câu hỏi mới\nFR17 Theo dõi trạng thái mô hình\nFR18 Chuẩn bị và huấn luyện cục bộ')]
    c.line([(400,695),(480,695)]); c.line([(480,110),(480,1310)])
    for i,(title,body) in enumerate(groups):
        y=25+i*235; c.line([(480,y+100),(575,y+100)])
        c.box(575,y,1185,205)
        c.d.rectangle((575,y,1760,y+61),fill=FILL,outline=INK,width=3)
        c.text((595,y+4,1145,54),title,40,True)
        c.text((600,y+67,1135,130),body,37,align='left')
    c.save()

def context():
    c=Canvas('02_context',1370)
    c.box(575,450,650,335,'0\nGiám sát môi trường đô thị\nvà tư vấn Xanh Non',45,'round',True,FILL)
    c.box(25,500,340,180,'Người sử dụng',43)
    c.box(1405,100,350,160,'Open-Meteo',42)
    c.box(1405,520,350,160,'NoiseCapture',42)
    c.box(1405,950,350,160,'OpenStreetMap',41)
    c.box(575,1080,650,160,'Người vận hành trên máy',42)
    c.arrow([(365,540),(575,540)],'Địa điểm, câu hỏi, kỳ báo cáo',(365,385,210,150))
    c.arrow([(575,690),(365,690)],'Chỉ số, bản đồ, cảnh báo, câu trả lời',(360,710,220,185))
    c.arrow([(1225,490),(1320,490),(1320,180),(1405,180)],'Tọa độ và thời gian',(1000,260,310,115))
    c.arrow([(1405,230),(1360,230),(1360,575),(1225,575)],'Số liệu và dự báo',(1370,285,370,140))
    c.arrow([(1225,630),(1405,630)],'Yêu cầu tệp',(1225,550,180,75))
    c.arrow([(1405,680),(1330,680),(1330,745),(1225,745)],'Dữ liệu tiếng ồn',(1325,760,430,85))
    c.arrow([(1210,785),(1270,785),(1270,1020),(1405,1020)],'Ô bản đồ',(1070,880,210,80))
    c.arrow([(1405,1070),(1285,1070),(1285,810),(1190,810)],'Ảnh nền',(1320,1120,330,85))
    c.arrow([(760,1080),(760,785)],'Lệnh vận hành, dữ liệu học',(445,850,315,150))
    c.arrow([(1020,785),(1020,1080)],'Trạng thái và kết quả',(1025,865,285,130))
    c.save()

def dfd0():
    c=Canvas('03_dfd0',2090)
    # Numbered processes and data stores are deliberately separated from external entities.
    ys=[120,510,900,1290,1680]
    titles=['1.0\nTra cứu địa điểm và bản đồ','2.0\nCập nhật và đánh giá môi trường','3.0\nTổng hợp và lưu báo cáo','4.0\nXử lý hội thoại và góp ý','5.0\nChuẩn bị và huấn luyện']
    stores=['D1 Danh mục địa điểm\nD4 Mẫu lưới AQI','D2 Bản ghi môi trường\nD3 Cảnh báo và phân tích','D5 Báo cáo đã lưu','D6 Kiến thức đã kiểm tra\nD7 Góp ý và câu hỏi','D8 Dữ liệu và mô hình']
    for i,y in enumerate(ys):
        c.box(540,y,655,175,titles[i],41,'round',True,FILL)
        c.box(1380,y,385,195,stores[i],37,'store')
        c.arrow([(1195,y+55),(1380,y+55)],'Tra cứu' if i in (0,3) else 'Đọc ghi',(1190,y-25,190,75))
        if i in (0,1,2,3,4): c.arrow([(1380,y+135),(1195,y+135)])
    c.box(20,150,325,170,'Người sử dụng',40)
    c.line([(345,235),(420,235),(420,1470)])
    c.line([(345,300),(365,300),(365,1560)])
    for i in range(4):
        y=ys[i]; c.arrow([(420,y+70),(540,y+70)])
        c.arrow([(540,y+145),(480,y+145),(480,390+i*390),(365,390+i*390)])
        c.text((10,330+i*390,380,110),['Địa điểm và kết quả tra cứu','Yêu cầu và số liệu cập nhật','Kỳ và nội dung báo cáo','Câu hỏi, góp ý và phản hồi'][i],35)
    c.box(20,1750,325,180,'Người vận hành',39)
    c.arrow([(345,1780),(540,1780)],'Lệnh chạy',(340,1685,205,90))
    c.arrow([(540,1850),(345,1850)],'Kết quả',(340,1880,205,80))
    c.arrow([(870,295),(870,510)],'Mã địa điểm',(875,337,290,90))
    c.arrow([(1195,620),(1295,620),(1295,1040),(1195,1040)],'Bản ghi và cảnh báo',(1240,755,520,110))
    c.arrow([(540,590),(360,590),(360,500),(20,500)],'Tọa độ',(30,415,260,75))
    c.box(20,485,315,160,'Open-Meteo\nNoiseCapture',35)
    c.arrow([(335,620),(540,620)])
    c.box(1380,330,385,115,'OpenStreetMap',37)
    c.arrow([(1195,230),(1290,230),(1290,385),(1380,385)],'Ô nền và ảnh',(1205,285,180,85))
    c.arrow([(1195,1380),(1315,1380),(1315,670),(1195,670)],'Dữ liệu hiện tại và dự báo',(1315,1100,470,125))
    c.arrow([(1380,1470),(1300,1470),(1300,1760),(1195,1760)],'Mẫu đã kiểm tra',(1305,1515,460,110))
    c.text((510,1940,1260,120),'D1–D8 là các nhóm kho dữ liệu logic. Mũi tên thể hiện dữ liệu qua tiến trình; không nối tác nhân trực tiếp với kho.',34)
    c.save()

def dfd_clean():
    def panel(c,y,number,title,actor,store,secondary,secondary_store=False,extra_snapshot=False):
        labels={
          '1.0':('Địa điểm và vùng','Danh mục\nvà bản đồ','Khóa nơi\nvà mẫu lưới','Danh mục và mẫu','Tọa độ và vùng','Lưới AQI và ảnh nền'),
          '2.0':('Địa điểm cập nhật','Snapshot\nvà cảnh báo','Snapshot\nvà kết quả','Snapshot đã lưu','Tọa độ','Thời tiết không khí tiếng ồn'),
          '3.0':('Kỳ và mã báo cáo','Báo cáo','Nội dung\nbáo cáo','Báo cáo đã lưu','Kỳ và địa điểm','Snapshot và cảnh báo'),
          '4.0':('Câu hỏi và góp ý','Câu trả lời\nvà xác nhận','Truy vấn\nvà góp ý','Tri thức và câu hỏi','Nơi và thời gian','Dữ liệu hiện tại và dự báo'),
          '5.0':('Lệnh và dữ liệu','Trạng thái\nvà kết quả học','Checkpoint\nvà manifest','Dữ liệu và trọng số','Tiêu chí lọc','Mẫu đã kiểm tra')
        }[number]
        c.box(20,y+150,340,170,actor,36)
        c.box(635,y+150,550,170,number+'\n'+title,37,'round',True,FILL)
        c.box(1450,y+150,330,170,store,34,'store')
        c.box(635,y+470,550,135,secondary,34,'store' if secondary_store else 'rect')
        c.arrow([(360,y+190),(635,y+190)])
        c.text((365,y+60,265,105),labels[0],34)
        c.arrow([(635,y+280),(360,y+280)])
        c.text((365,y+305,265,105),labels[1],34)
        c.arrow([(1185,y+190),(1450,y+190)])
        c.text((1190,y+60,250,105),labels[2],32)
        c.arrow([(1450,y+280),(1185,y+280)])
        c.text((1190,y+305,250,80),labels[3],32)
        c.arrow([(800,y+320),(800,y+470)])
        c.text((350,y+385,410,80),labels[4],32)
        c.arrow([(1040,y+470),(1040,y+320)])
        c.text((1060,y+385,710,80),labels[5],34)
        if extra_snapshot:
            c.box(20,y+475,410,130,'D2 Snapshot môi trường',34,'store')
            c.arrow([(430,y+530),(570,y+530),(570,y+430),(680,y+430),(680,y+320)])
    c=Canvas('03_dfd0',1920)
    panel(c,0,'1.0','Tra cứu địa điểm\nvà bản đồ','A01 Người sử dụng','D1 Danh mục\nD4 Mẫu AQI','E01 Open-Meteo\nE03 OpenStreetMap')
    panel(c,640,'2.0','Cập nhật\nvà đánh giá','A01 Người sử dụng','D2 Snapshot\nD3 Cảnh báo\nvà phân tích','E01 Open-Meteo\nE02 NoiseCapture')
    panel(c,1280,'3.0','Tổng hợp\nvà lưu báo cáo','A01 Người sử dụng','D5 Báo cáo\nđã lưu','D2 Snapshot\nD3 Cảnh báo',True)
    c.save()
    c=Canvas('03b_dfd0_chat',1320)
    panel(c,0,'4.0','Hội thoại\nvà góp ý','A01 Người sử dụng','D6 Tri thức\nD7 Góp ý và\ncâu hỏi','E01 Open-Meteo',False,True)
    panel(c,670,'5.0','Chuẩn bị\nvà huấn luyện','A02 Người vận hành','D8 Dữ liệu học\nvà mô hình','D6 Tri thức\nD7 Mẫu đã duyệt',True)
    c.save()

def context_clean():
    c=Canvas('02_context',1500)
    c.box(570,590,650,280,'0\nGiám sát môi trường đô thị\nvà tư vấn Xanh Non',42,'round',True,FILL)
    c.box(20,620,320,180,'Người sử dụng',39)
    c.arrow([(340,660),(570,660)]);c.text((340,440,230,180),'Địa điểm\ncâu hỏi\nkỳ báo cáo',35)
    c.arrow([(570,790),(340,790)]);c.text((340,810,230,220),'Chỉ số\nbản đồ\ncảnh báo\nphản hồi',35)
    c.box(1440,120,335,170,'Open-Meteo',38)
    c.arrow([(1220,625),(1300,625),(1300,175),(1440,175)])
    c.text((965,220,330,130),'Tọa độ\nvà thời gian',36)
    c.arrow([(1440,250),(1250,250),(1250,685),(1220,685)])
    c.text((1390,315,390,130),'Số liệu\nvà dự báo',36)
    c.box(1440,685,335,170,'NoiseCapture',38)
    c.arrow([(1220,745),(1440,745)]);c.text((1230,675,205,60),'Tải tệp',32)
    c.arrow([(1440,815),(1220,815)]);c.text((1220,865,555,100),'Dữ liệu tiếng ồn',35)
    c.box(1440,1180,335,170,'OpenStreetMap',36)
    c.arrow([(1160,870),(1270,870),(1270,1220),(1440,1220)])
    c.text((1360,1020,410,110),'Yêu cầu ô nền',34)
    c.arrow([(1440,1300),(1330,1300),(1330,855),(1220,855)])
    c.text((1430,1360,340,80),'Ảnh nền',35)
    c.box(540,1200,650,160,'Người vận hành trên máy',38)
    c.arrow([(750,1200),(750,870)]);c.text((70,1090,465,135),'Lệnh vận hành\nvà dữ liệu học',34)
    c.arrow([(1000,870),(1000,1200)]);c.text((1005,960,340,135),'Trạng thái\nvà kết quả',34)
    c.save()

def dfd1():
    c=Canvas('04_dfd1_update',1690)
    nodes=[(500,50,800,135,'2.1 Xác định địa điểm'),(500,320,800,135,'2.2 Kiểm tra cache 600 giây'),(500,600,800,150,'2.3 Nhận và ghép dữ liệu nguồn'),(500,905,800,150,'2.4 Đánh giá ngưỡng và chạy RF'),(500,1210,800,150,'2.5 Lưu snapshot và kết quả')]
    for x,y,w,h,t in nodes:c.box(x,y,w,h,t,40,'round',True,FILL)
    for i in range(4):
        y=nodes[i][1]+nodes[i][3]; nxt=nodes[i+1][1]
        c.arrow([(900,y),(900,nxt)],['Địa điểm hợp lệ','Cache hết hạn','Bộ giá trị và metadata','Bản ghi cùng kết quả'][i],(930,y+20,500,nxt-y-35))
    c.box(30,320,330,160,'D2 Snapshot\nđã lưu',38,'store')
    c.arrow([(500,365),(360,365)])
    c.arrow([(360,430),(440,430),(440,1520),(745,1520)],'Snapshot còn hạn',(20,730,390,120))
    c.box(1400,590,360,180,'Open-Meteo\nNoiseCapture',39)
    c.arrow([(1300,640),(1400,640)])
    c.arrow([(1400,730),(1300,730)])
    c.box(20,910,350,180,'D8 Mô hình\nRandom Forest',38,'store')
    c.arrow([(370,990),(500,990)])
    c.box(1400,1180,360,245,'D2 NguonDL\nD3 CanhBao\nPhanTichAI',38,'store')
    c.arrow([(1300,1290),(1400,1290)])
    c.box(745,1450,650,150,'JSON về giao diện',41)
    c.arrow([(900,1360),(900,1450)])
    c.text((20,1540,660,120),'Nguồn lỗi → 502; SQL lỗi → 503. RF thiếu dữ liệu không chặn lưu số liệu.',35)
    c.save()

def usecase():
    c=Canvas('05_usecase',1650)
    c.d.rectangle((410,25,1460,1610),outline=INK,width=3)
    c.text((460,30,950,80),'Hệ thống giám sát và tư vấn môi trường',41,True)
    c.box(15,540,310,150,'Người sử dụng',40)
    c.box(15,1350,310,160,'Người vận hành',38)
    cases=[('UC01–02 Chọn địa điểm',150),('UC03–04 Cập nhật và xem chỉ số',340),('UC05–07 Bản đồ và xu hướng',530),('UC08–09 Cảnh báo và phân loại',720),('UC10–12 Tạo mở xuất báo cáo',910),('UC13–16 Hội thoại và góp ý',1100),('UC17 Theo dõi mô hình',1290),('UC18 Huấn luyện cục bộ',1480)]
    for text,y in cases:
        c.box(490,y,850,130,text,38,'ellipse')
        c.line([(325,615 if y<1290 else 1430),(400,y+65),(490,y+65)])
    c.box(1500,280,280,160,'Open-Meteo',36)
    c.box(1500,600,280,160,'NoiseCapture',36)
    c.box(1500,970,280,160,'OSM',38)
    c.line([(1340,405),(1500,360)]);c.line([(1340,785),(1475,785),(1475,680),(1500,680)]);c.line([(1340,595),(1450,595),(1450,1050),(1500,1050)])
    c.save()

def sequence(name, labels, messages, height=1550):
    c=Canvas(name,height)
    n=len(labels); xs=[90+i*(1620/(n-1)) for i in range(n)]
    for x,label in zip(xs,labels):
        w=300 if n<5 else 285
        xx=max(10,min(1790-w,x-w/2));c.box(xx,20,w,145,label,37,fill=FILL)
        c.line([(x,165),(x,height-30)],True)
    for index,(a,b,text,reply) in enumerate(messages):
        y=245+index*(height-310)/len(messages)
        x1,x2=xs[a],xs[b]
        if a==b:
            c.arrow([(x1,y),(x1+85,y),(x1+85,y+65),(x1,y+65)],dashed=reply)
            c.text((x1+95,y-15,min(530,1780-x1-95),100),text,34,align='left')
        else:
            c.arrow([(x1,y),(x2,y)],dashed=reply)
            width=abs(x2-x1);c.text((min(x1,x2)+8,y-103,width-16,95),text,35)
    c.save()

def activity():
    c=Canvas('06_activity_location',1450)
    c.d.ellipse((875,20,925,70),fill=INK)
    steps=[('Chọn danh mục hoặc nhấn lấy vị trí',140),('Trình duyệt đối chiếu tọa độ với 86 địa điểm',360),('Cập nhật mã địa điểm và khóa phiên yêu cầu',580),('Lấy snapshot rồi đọc lịch sử và cảnh báo',800),('Đổi chỉ số bản đồ báo cáo và ngữ cảnh chat',1020)]
    prev=70
    for t,y in steps:
        c.arrow([(900,prev),(900,y)]);c.box(440,y,920,135,t,39,'round',fill=FILL);prev=y+135
    c.box(20,350,310,200,'Từ chối quyền\nhoặc lỗi GPS',37)
    c.arrow([(440,420),(330,420)])
    c.arrow([(20,450),(10,450),(10,205),(440,205)],'Chọn thủ công',(15,650,350,110))
    c.box(1430,790,340,215,'Nguồn lỗi\nHiển thị lỗi\nvà thử lại',36)
    c.arrow([(1360,865),(1430,865)])
    c.arrow([(1600,1005),(1600,1080),(1360,1080)])
    c.arrow([(900,1155),(900,1280)])
    c.d.ellipse((863,1280,937,1354),outline=INK,width=4);c.d.ellipse((876,1293,924,1341),fill=INK)
    c.save()

def class_diagram():
    c=Canvas('10_classes',1640)
    c.entity(30,25,780,'LocationStore',['connection_factory','ready và lock','ensure_schema()'],38)
    c.entity(990,25,780,'ReportRepository',['connection_factory và ensure_locations','_schema_ready và _schema_lock','create(days, location_id)','list(limit, offset, location_id)','get(report_id, location_id)'],37)
    c.arrow([(990,180),(810,180)],'phụ thuộc',(805,60,180,100),True)
    c.entity(30,510,780,'AirMapRepository',['connection_factory','cache và lock','get_samples(points)','grid(bounds, location)'],38)
    c.entity(990,590,780,'NoiseData',['path, cells, loaded_mtime','last_attempt và lock','get(location, radius)'],38)
    c.entity(30,1000,780,'NativeChatbot',['process và base_url','max_input_tokens','generate(messages, max_tokens, …)','close()'],37)
    c.entity(990,1030,780,'FeedbackStore',['path','submit(payload, model)','list(status, limit)','review(id, approve, …)'],38)
    c.text((25,1455,1740,140),'Các lớp trên tồn tại trong mã Python. app.py và chatbot.py điều phối bằng hàm; không có quan hệ kế thừa giữa các lớp này.',38)
    c.save()

def learnerclass():
    c=Canvas('11_learning_classes',1010)
    c.entity(70,60,760,'ConversationLearner',['path và base_dir','enabled','observe(message, history)','_candidate(question, context, pack)','_checked_answer(row, pack, version)'],35)
    c.box(1060,60,650,170,'chat_knowledge\nCác hàm tra cứu kiến thức',38,fill=FILL)
    c.box(1060,420,650,170,'knowledge.json\nTài liệu và nguồn tham chiếu',38,'store')
    c.box(70,700,760,160,'questions.sqlite3\nCâu hỏi và trạng thái kiểm tra',38,'store')
    c.arrow([(830,155),(1060,155)],'gọi',(830,55,220,95),True)
    c.arrow([(1380,230),(1380,420)],'đọc',(1410,260,230,100))
    c.arrow([(450,462),(450,700)],'đọc và ghi',(490,530,450,100))
    c.text((960,735,790,170),'Quan hệ phụ thuộc và lưu trữ. Không coi mỗi câu chat là một lần cập nhật trọng số.',38)
    c.save()

def states():
    c=Canvas('12_state_chat',1220)
    states=[(60,90,'cold'),(690,90,'loading'),(1300,90,'ready'),(1300,650,'training'),(690,650,'error')]
    for x,y,t in states:c.box(x,y,420,150,t,43,'round',True,FILL)
    c.arrow([(480,165),(690,165)],'Khởi tạo',(480,60,210,90))
    c.arrow([(1110,165),(1300,165)],'Nạp xong',(1110,60,190,90))
    c.arrow([(900,240),(900,650)],'Nạp thất bại',(920,380,350,110))
    c.arrow([(1510,240),(1510,650)],'Huấn luyện giữ khóa',(1450,365,340,120))
    c.arrow([(1300,735),(1190,735),(1190,340),(1390,340),(1390,240)],'Hết khóa và nạp lại',(900,850,840,95))
    c.arrow([(690,735),(570,735),(570,365),(790,365),(790,240)],'Yêu cầu thử lại',(120,420,430,110))
    c.text((55,1000,1680,140),'training là trạng thái do runtime_status trả về khi có khóa huấn luyện. Cấu hình cho phép chạy đồng thời có thể giữ ready và thêm background_training.',37)
    c.save()

def component():
    c=Canvas('13_components',1470)
    c.box(40,30,1720,200,'Trình duyệt\nindex.html  dashboard.js  locations.js  script.js  map.js  chat.js  reports.js',38,fill=FILL)
    c.box(40,450,1720,200,'Flask app.py\nRoutes giám sát  Blueprint bản đồ  Blueprint báo cáo  Blueprint góp ý',38,fill=FILL)
    c.arrow([(900,230),(900,450)],'HTTP JSON và SSE',(925,290,650,100))
    modules=[('Dữ liệu và phân tích\nlocation_catalog  noise_data\nenvironment_predictor',40),('Hội thoại và kiến thức\nchatbot  chat_scope\nchat_knowledge  chat_time_context',640),('Lưu trữ nghiệp vụ\nReportRepository\nAirMapRepository',1240)]
    for t,x in modules:
        c.box(x,830,520,230,t,35,fill=FILL);c.arrow([(x+260,650),(x+260,830)])
    c.box(40,1220,520,180,'SQL Server\n6 bảng nghiệp vụ',39,'store')
    c.box(640,1220,520,180,'llama.cpp và GGUF\nSQLite và JSON',38,'store')
    c.box(1240,1220,520,180,'API bên ngoài\nOpen-Meteo NoiseCapture',37)
    c.arrow([(300,1060),(300,1220)]);c.arrow([(900,1060),(900,1220)]);c.arrow([(1500,1060),(1500,1220)])
    c.save()

def deployment():
    c=Canvas('14_deployment',1330)
    c.d.rectangle((25,20,1770,1100),outline=INK,width=3)
    c.text((60,25,1680,80),'Máy Windows chạy dự án',44,True)
    c.box(70,170,700,180,'Trình duyệt Edge\nỨng dụng HTML CSS JavaScript',39,fill=FILL)
    c.box(1030,170,650,180,'Python Flask\n127.0.0.1:5000',41,fill=FILL)
    c.arrow([(770,260),(1030,260)],'HTTP',(780,150,235,90))
    c.box(70,600,700,180,'SQL Server GiamsatMT\nODBC Driver 17',40,'store')
    c.box(1030,600,650,180,'llama-server.exe\n127.0.0.1 cổng động',40,fill=FILL)
    c.arrow([(1210,350),(1210,600)],'HTTP nội bộ',(1230,415,470,90))
    c.arrow([(1030,320),(900,320),(900,690),(770,690)],'pyodbc',(780,465,235,90))
    c.box(100,900,1550,150,'Ổ đĩa cục bộ   GGUF   knowledge.json   SQLite   dữ liệu huấn luyện',38,'store')
    c.arrow([(1350,780),(1350,900)])
    c.box(270,1170,1250,130,'Internet  Open-Meteo  NoiseCapture  OpenStreetMap',38)
    c.arrow([(1680,260),(1740,260),(1740,1235),(1520,1235)])
    c.save()

def erd():
    c=Canvas('15_erd',1720)
    # Solid crow's-foot lines: database-declared FK. Dashed lines: logical association only.
    a=c.entity(25,30,710,'DiaDiem',['*MaDiaDiem','Ten, Nhom','ViDo, KinhDo','ViDoTiengOn, KinhDoTiengOn','TenKhuVucTiengOn','ChiTiet'],38)
    b=c.entity(1000,30,775,'NguonDL',['*Manguon','MaDiaDiem  liên kết logic','TenNguon, ThoiGian','PM25, PM10, NhietDo','DoAm, TiengOn','ChiTiet'],38)
    d=c.entity(25,620,710,'BaoCaoMT',['*MaBaoCao','MaDiaDiem  liên kết logic','TieuDe, TuNgay, DenNgay','ThoiGianTao, SoNgay','SoBanGhi, SoCanhBao','NoiDung'],38)
    e=c.entity(1000,620,775,'CanhBao',['*Macanhbao','Manguon  FK','LoaiCanhBao, MucDo','NoiDung, ThoiGian'],38)
    f=c.entity(1000,1080,775,'PhanTichAI',['*Maphantich','Manguon  FK','KetQua, NhanXet','KhuyenNghi, ThoiGian'],38)
    g=c.entity(25,1160,710,'MauBanDoKhongKhi',['*MaMau','MaViTri, ViDo, KinhDo','ThoiGianLay, ThoiGianNguon','US_AQI, PM25, ChiTiet'],37)
    # horizontal logical 1 to 0..many
    c.line([(735,230),(1000,230)],True);c.text((740,135,255,80),'1      0..n',34)
    c.d.line((762,210,762,250),fill=INK,width=3);c.line([(970,230),(1000,210)]);c.line([(970,230),(1000,250)]);c.d.ellipse((943,220,963,240),outline=INK,width=3)
    c.line([(380,442),(380,620)],True);c.text((405,480,280,100),'1 → 0..n',35)
    # snapshot parent to alerts and analyses via right-side bus
    c.line([(1385,442),(1385,620)]);c.text((1410,470,345,90),'1 → 0..n',35)
    c.line([(1385,442),(1790,442),(1790,1050),(1385,1050),(1385,1080)])
    # Keep bus within image and textual legend unambiguous.
    c.d.line((1365,470,1405,470),fill=INK,width=3);c.line([(1385,590),(1365,620)]);c.line([(1385,590),(1405,620)]);c.d.ellipse((1375,560,1395,580),outline=INK,width=3)
    c.text((760,1000,1010,75),'NguonDL 1 → PhanTichAI 0..n',34)
    c.text((25,1580,1745,110),'Gạch chân là khóa chính. Nét liền là FK khai báo trong SQL. Nét đứt là liên kết theo MaDiaDiem ở tầng ứng dụng. Mẫu bản đồ không có FK tới DiaDiem.',33)
    c.save()

def wireframe():
    c=Canvas('16_wireframe',1260)
    c.box(25,25,1750,130,'Menu     Tìm địa điểm hoặc chức năng                         Chuông cảnh báo',39,fill=FILL)
    c.box(25,190,1750,240)
    c.text((60,210,1100,80),'Khu vực đang giám sát và nguồn dữ liệu',40,True,align='left')
    c.box(65,320,600,75,'Danh sách địa điểm',34);c.box(700,320,450,75,'Lấy vị trí hiện tại',33)
    c.box(1300,220,400,80,'Cập nhật dữ liệu',33,fill=FILL);c.text((1280,320,440,80),'Cập nhật gần nhất',33)
    c.box(25,470,425,340,'US AQI\nGiá trị\nMức chất lượng',40,fill=FILL)
    for x,y,t in [(485,470,'PM2.5'),(925,470,'PM10'),(1365,470,'Nhiệt độ'),(485,655,'Độ ẩm'),(925,655,'Tiếng ồn')]:c.box(x,y,410,155,t,37)
    c.box(25,850,1750,375,'Bản đồ chất lượng không khí\nĐiều khiển vị trí và lớp phủ AQI\nBong bóng Xanh Non ở góc phải',43,fill=FILL)
    c.save()

def trainflow():
    c=Canvas('17_training',1390)
    steps=[('Dữ liệu gốc và góp ý đã duyệt',35),('Lọc dữ liệu riêng tư và loại câu trùng',245),('Tách train validation và kiểm tra token',455),('Kiểm tra RAM ổ đĩa và phiên huấn luyện',665),('Huấn luyện LoRA rồi xuất mô hình ứng viên',875),('Đánh giá ứng viên và quản lý bản phát hành',1085)]
    for i,(t,y) in enumerate(steps):
        c.box(350,y,1100,135,t,39,'round',fill=FILL)
        if i:c.arrow([(900,steps[i-1][1]+135),(900,y)])
    c.box(20,670,275,225,'Thiếu RAM\nChờ lần chạy sau',35)
    c.arrow([(350,735),(295,735)])
    c.text((40,1250,1700,100),'Trạng thái kiểm tra ngày 27/10/2026 là waiting_for_memory; không ghi nhận kích hoạt trọng số mới trong đợt khôi phục.',36)
    c.save()

if __name__=='__main__':
    bfd();context_clean();dfd_clean();dfd1();usecase();activity()
    sequence('07_sequence_update',['Giao diện','Flask app.py','Nguồn dữ liệu','SQL Server'],[
        (0,1,'1 Cập nhật location',False),(1,3,'2 Đọc snapshot còn hạn',False),(3,1,'3 Snapshot hoặc rỗng',True),(1,2,'4 Khi hết hạn gọi API',False),(2,1,'5 Giá trị và thời gian nguồn',True),(1,3,'6 Ghi NguonDL CanhBao PhanTichAI',False),(3,1,'7 Commit',True),(1,0,'8 JSON snapshot đúng địa điểm',True)])
    sequence('08_sequence_chat',['Widget chat','Flask và chatbot','Bộ dữ liệu và tri thức','NativeChatbot'],[
        (0,1,'1 message history location',False),(1,2,'2 Giải ngữ cảnh và đọc dữ liệu liên quan',False),(2,1,'3 Dữ liệu có nguồn hoặc thiếu',True),(1,0,'4 Nếu có nhánh chắc chắn trả trực tiếp',True),(1,3,'5 Nếu cần sinh văn bản gửi ngữ cảnh',False),(3,1,'6 Token và cờ kết thúc',True),(1,0,'7 SSE status delta done hoặc error',True),(0,1,'8 Dừng đọc stream khi người dùng nhấn Dừng',False)])
    sequence('09_sequence_report',['Giao diện','Blueprint báo cáo','ReportRepository','SQL Server'],[
        (0,1,'1 POST days location',False),(1,2,'2 create(days location_id)',False),(2,3,'3 Đọc bản ghi và cảnh báo trong kỳ',False),(3,2,'4 Các hàng đúng địa điểm',True),(2,3,'5 INSERT BaoCaoMT và commit',False),(3,2,'6 MaBaoCao',True),(2,1,'7 Nội dung và mã báo cáo',True),(1,0,'8 HTTP 201 sau khi lưu',True)])
    class_diagram();learnerclass();states();component();deployment();erd();wireframe();trainflow()
    print(json.dumps({'diagrams':len(list(OUT.glob('[0-9][0-9]_*.png'))),'folder':str(OUT)},ensure_ascii=False))
