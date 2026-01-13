# utils.py
import os
import json
import streamlit as st
from config.settings import WORKSPACE
import re

def save_file(content, filename, is_json=False):
    """Lưu file vào WORKSPACE với mã hóa UTF-8"""
    path = os.path.join(WORKSPACE, filename)
    with open(path, "w", encoding="utf-8") as f:
        if is_json:
            json.dump(content, f, ensure_ascii=False, indent=4)
        else:
            f.write(content)
    return path

def split_srt_blocks(file_path):
    """Đọc file SRT và tách thành các block text (nhóm theo 2 dấu xuống dòng)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Tách dựa trên 2 dấu xuống dòng (chuẩn SRT)
    return [b.strip() for b in re.split(r'\n\n+', content) if b.strip()]

def render_artifact_viewer(file_path, title):
    """Hiển thị khung xem trước và nút tải về"""
    if not os.path.exists(file_path):
        st.info(f"✨ Đang chờ tạo file {title}...")
        return

    with st.expander(f"👁️ Xem nhanh: {os.path.basename(file_path)}", expanded=True):
        col_name, col_dl = st.columns([3, 1])
        col_name.write(f"✅ Đã tạo: **{title}**")
        
        with open(file_path, "rb") as f:
            col_dl.download_button(
                label=f"⬇️ Tải {title}",
                data=f,
                file_name=os.path.basename(file_path),
                key=file_path
            )

        # Logic hiển thị nội dung
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext in [".srt", ".txt"]:
                st.code(open(file_path, "r", encoding="utf-8").read(), language="bash")
            elif ext == ".json":
                st.json(json.load(open(file_path, "r", encoding="utf-8")))
            elif ext == ".mp4":
                st.video(file_path)
            elif ext in [".png", ".jpg"]:
                st.image(file_path)
        except Exception as e:
            st.error(f"Không thể xem trước file này: {e}")


def extract_json_from_text(text_content):
    """
    Hàm lọc sạn: Chỉ lấy phần JSON hợp lệ từ lời nói nhảm của AI.
    Trả về: List các object (hoặc list rỗng nếu lỗi)
    """
    try:
        # 1. Nếu AI dùng Markdown code block (```json ... ```), ưu tiên lấy nó trước
        match = re.search(r'```json\s*(.*?)```', text_content, re.DOTALL)
        if match:
            text_content = match.group(1)

        # 2. Tìm điểm bắt đầu '[' và kết thúc ']'
        # (Giả sử AI trả về một list các object)
        start_idx = text_content.find('[')
        end_idx = text_content.rfind(']')
        
        if start_idx != -1 and end_idx != -1:
            json_str = text_content[start_idx : end_idx+1]
            return json.loads(json_str)
            
        # 3. Trường hợp AI trả về nhiều dòng JSON rời rạc (không nằm trong [])
        # Thử ép kiểu từng dòng xem sao
        objects = []
        # Tìm tất cả các đoạn text nằm trong dấu {}
        matches = re.findall(r'(\{.*?\})', text_content, re.DOTALL)
        for m in matches:
            try:
                obj = json.loads(m)
                objects.append(obj)
            except:
                pass
        
        return objects

    except Exception as e:
        print(f"⚠️ Lỗi parse JSON: {e}")
        return []

def get_projects():
    """Trả về danh sách tên các folder dự án trong workspace"""
    if not os.path.exists(WORKSPACE):
        os.makedirs(WORKSPACE)
        return []
    
    # Chỉ lấy các item là thư mục (folder), bỏ qua file lẻ
    projects = [
        d for d in os.listdir(WORKSPACE) 
        if os.path.isdir(os.path.join(WORKSPACE, d))
    ]
    return sorted(projects) # Sắp xếp A-Z