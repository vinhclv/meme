import re

def split_srt_blocks(file_path):
    """Đọc file SRT và tách thành các block text"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Tách dựa trên 2 dấu xuống dòng (chuẩn SRT)
    return [b.strip() for b in re.split(r'\n\n+', content) if b.strip()]

def update_live_preview(filepath, placeholder):
    """Hàm giả lập update UI, trong Streamlit mình xử lý ở View rồi nên có thể bỏ qua hoặc để pass"""
    pass