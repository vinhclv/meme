import os

# Tên dự án
PROJECT_NAME = "Meme Video Automation"

# =========================================================
# 1. SỬA LỖI ĐƯỜNG DẪN (QUAN TRỌNG NHẤT)
# =========================================================
# Lấy đường dẫn gốc của file config.py hiện tại
# Giả sử cấu trúc: /MyTool/config/settings.py hoặc /MyTool/config.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 

# Workspace sẽ luôn nằm cố định trong thư mục dự án
WORKSPACE = os.path.join(BASE_DIR, "workspace")

# Profile Chrome cũng cố định theo dự án
PROFILE_DIR = os.path.join(BASE_DIR, "ChromeProfile_Gemini")

# =========================================================
# 2. SỬA LỖI LOGIC CẤU TRÚC (BỎ "VIDEO NAME")
# =========================================================
# Chúng ta không lấy structure theo video nữa, mà lấy theo Project
def get_project_structure(project_name):
    """
    Trả về đường dẫn các folder của 1 Dự án (Cấu trúc phẳng)
    """
    # Đường dẫn đến thư mục Dự án
    # Ví dụ: workspace/Kenh_Kham_Pha
    project_path = os.path.join(WORKSPACE, project_name)
    
    paths = {
        "root": project_path,
        "0_audio_raw": os.path.join(project_path, "0_audio_raw"), # Input Step 1
        "1_input":     os.path.join(project_path, "1_input"),     # Output Step 1 / Input Step 2
        "2_prompts":   os.path.join(project_path, "2_prompts"),   # Output Step 2 / Input Step 3
        "3_assets":    os.path.join(project_path, "3_assets"),    # Output Step 3 / Input Step 4
        "4_final":     os.path.join(project_path, "4_final")      # Output Step 4
    }

    # Tự động tạo nếu chưa có
    for p in paths.values():
        os.makedirs(p, exist_ok=True)
        
    return paths