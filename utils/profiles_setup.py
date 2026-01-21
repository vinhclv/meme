
import os
import shutil
import zipfile
import time
import streamlit as st # Cần import st để dùng progress bar và toast

from config.settings import PROFILES_DIR

# ==========================================
# 1. HÀM CỐT LÕI (CORE LOGIC)
# ==========================================

def force_delete_folder(path):
    """Xóa folder/file mạnh (Retry nếu bị Windows lock)"""
    if not os.path.exists(path): return True
    for i in range(3):
        try:
            if os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
            else: os.remove(path)
            if not os.path.exists(path): return True
        except: time.sleep(0.5)
    return False

def get_available_profiles():
    """Lấy danh sách profile hiện có"""
    if not os.path.exists(PROFILES_DIR):
        try: os.makedirs(PROFILES_DIR)
        except: pass
        return []
    return [f for f in os.listdir(PROFILES_DIR) if f.endswith('.json')]

def delete_profiles_data(selected_list):
    """
    Xóa danh sách profile từ ổ cứng.
    Trả về số lượng đã xóa thành công.
    """
    count = 0
    for profile_json in selected_list:
        try:
            # Xóa file JSON
            json_path = os.path.join(PROFILES_DIR, profile_json)
            force_delete_folder(json_path)
            
            # Xóa folder Data
            folder_name = os.path.splitext(profile_json)[0]
            folder_path = os.path.join(PROFILES_DIR, folder_name)
            force_delete_folder(folder_path)
            
            count += 1
        except Exception as e:
            print(f"Lỗi xóa {profile_json}: {e}")
            
    return count

def save_uploaded_profile(uploaded_files):
    """
    Xử lý file upload (JSON/ZIP).
    Trả về True nếu có ít nhất 1 file thành công.
    """
    if not os.path.exists(PROFILES_DIR): os.makedirs(PROFILES_DIR)
    saved_count = 0
    
    # UI Progress (Vẫn để ở đây cho tiện hiển thị tiến trình xử lý logic)
    status_text = st.sidebar.empty()
    my_bar = st.sidebar.progress(0)
    
    total = len(uploaded_files)
    for i, file in enumerate(uploaded_files):
        status_text.text(f"Đang xử lý: {file.name}")
        try:
            # 1. JSON
            if file.name.endswith(".json"):
                with open(os.path.join(PROFILES_DIR, file.name), "wb") as f: f.write(file.getbuffer())
                saved_count += 1
            
            # 2. ZIP
            elif file.name.endswith(".zip"):
                p_name = os.path.splitext(file.name)[0]
                final_path = os.path.join(PROFILES_DIR, p_name)
                tmp_dir = os.path.join(PROFILES_DIR, f"tmp_{int(time.time())}_{i}")
                os.makedirs(tmp_dir, exist_ok=True)
                
                z_path = os.path.join(tmp_dir, file.name)
                with open(z_path,"wb") as f: f.write(file.getbuffer())
                
                with zipfile.ZipFile(z_path,'r') as z: z.extractall(tmp_dir)
                try: os.remove(z_path)
                except: pass
                
                items = [x for x in os.listdir(tmp_dir) if not x.startswith('.')]
                src = tmp_dir
                if len(items)==1 and os.path.isdir(os.path.join(tmp_dir, items[0])):
                    src = os.path.join(tmp_dir, items[0])
                
                force_delete_folder(final_path)
                time.sleep(0.1)
                shutil.move(src, final_path)
                force_delete_folder(tmp_dir)
                saved_count += 1
                
        except Exception as e: st.sidebar.error(f"Err: {e}")
        my_bar.progress((i+1)/total)

    status_text.empty()
    my_bar.empty()
    return saved_count > 0