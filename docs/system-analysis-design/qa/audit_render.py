from pathlib import Path
import json,re
import pdfplumber
from PIL import Image,ImageDraw,ImageFont

QA=Path(__file__).resolve().parent
report=[]
with pdfplumber.open(QA/'native-word.pdf') as pdf:
    for index,page in enumerate(pdf.pages,1):
        text=page.extract_text() or ''
        words=page.extract_words()
        body=[w for w in words if 58<float(w['top'])<730]
        row={'page':index,'text_length':len(text),'images':len(page.images),'words':len(words),
             'body_top':min((w['top'] for w in body),default=None),'body_bottom':max((w['bottom'] for w in body),default=None),
             'out_of_bounds':[w['text'] for w in words if w['x0']<35 or w['x1']>page.width-25],
             'headings':[line for line in text.splitlines() if re.match(r'(CHƯƠNG |PHỤ LỤC |Hình \d+\.|Bảng \d+\.)',line)],
             'errors':[s for s in ['Error!','Bookmark not defined','No table of contents entries','�'] if s in text]}
        report.append(row)
        (QA/'page-text').mkdir(exist_ok=True)
        (QA/'page-text'/f'page-{index}.txt').write_text(text,encoding='utf-8')
(QA/'render-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
pages=sorted((p for p in (QA/'render-final').glob('page-*.png') if int(p.stem.split('-')[-1])<=len(report)),key=lambda p:int(p.stem.split('-')[-1]))
assert len(pages)==len(report),(len(pages),len(report))
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
for i in range(0,len(pages),4):
    images=[Image.open(p).convert('RGB') for p in pages[i:i+4]]
    w=max(im.width for im in images);h=max(im.height for im in images)
    sheet=Image.new('RGB',(w*2+30,h*2+75),'#cccccc');draw=ImageDraw.Draw(sheet)
    for j,im in enumerate(images):
        x=10+(j%2)*(w+10);y=25+(j//2)*(h+30)
        draw.text((x,y-23),pages[i+j].stem,font=font,fill='black');sheet.paste(im,(x,y))
    sheet.save(QA/f'sheet-{i//4+1:02d}.png')
print(json.dumps({'pages':len(report),'rendered_pages':len(pages),'error_pages':[r['page'] for r in report if r['errors']],'out_of_bounds_pages':[r['page'] for r in report if r['out_of_bounds']],'low_text_pages':[r['page'] for r in report if r['text_length']<120],'chapter_pages':[{'page':r['page'],'headings':r['headings']} for r in report if any(s.startswith('CHƯƠNG ') for s in r['headings'])]},ensure_ascii=False))
