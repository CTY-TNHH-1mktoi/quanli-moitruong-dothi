from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import importlib.util,os

BASE=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('diagrams',BASE/'diagrams/draw_diagrams.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.activity()
target=BASE/'Phan_tich_thiet_ke_he_thong_Quan_ly_moi_truong_do_thi_Xanh_Non.docx'
temp=target.with_suffix('.temp.docx')
ns={'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
with ZipFile(target) as z:
    tree=etree.fromstring(z.read('word/document.xml'))
    prop=next(p for p in tree.xpath('//wp:docPr',namespaces=ns) if p.get('descr','').startswith('Activity của luồng'))
    rid=prop.getparent().xpath('.//a:blip',namespaces=ns)[0].get('{'+ns['r']+'}embed')
    rels=etree.fromstring(z.read('word/_rels/document.xml.rels'))
    rel=next(p for p in rels if p.get('Id')==rid)
    member='word/'+rel.get('Target')
    with ZipFile(temp,'w') as out:
        for info in z.infolist():out.writestr(info,(BASE/'assets/06_activity_location.png').read_bytes() if info.filename==member else z.read(info.filename))
os.replace(temp,target)
print('Updated',member)
