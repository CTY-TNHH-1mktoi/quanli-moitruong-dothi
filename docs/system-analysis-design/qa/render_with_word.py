from pathlib import Path
import importlib.util, sys

BASE=Path(__file__).resolve().parent.parent
CANONICAL=Path('C:/Users/PC/.codex/plugins/cache/openai-primary-runtime/documents/26.1024.11018/skills/documents/render_docx.py')
spec=importlib.util.spec_from_file_location('skill_render_docx',CANONICAL)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
pdf=BASE/'qa/native-word.pdf'
assert pdf.is_file() and pdf.stat().st_size>0
def native_pdf(input_path,user_profile,convert_tmp_dir,stem,verbose=False):
    return str(pdf),'Rendered using native Microsoft Word 16 after LibreOffice was not found.'
module.convert_to_pdf=native_pdf
sys.argv=[str(CANONICAL),str(BASE/'Phan_tich_thiet_ke_he_thong_Quan_ly_moi_truong_do_thi_Xanh_Non.docx'),'--output_dir',str(BASE/'qa/render-final'),'--dpi','96','--emit_pdf']
module.main()
