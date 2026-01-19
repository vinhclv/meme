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


ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 

# Giữ biến BASE_DIR để tương thích ngược (nếu code cũ bạn lỡ dùng)
BASE_DIR = ROOT_PATH

# =========================================================
# 2. CẤU HÌNH WORKSPACE & PROFILES (UPDATE ĐA LUỒNG)
# =========================================================


# [UPDATE ĐA LUỒNG]
# Thay vì trỏ vào 1 profile cụ thể (PROFILE_DIR), ta trỏ vào folder chứa TẤT CẢ profile
# Code logic sẽ tự vào đây quét xem có bao nhiêu profile (json) để chia luồng.
PROFILES_DIR = os.path.join(ROOT_PATH, "profiles")

# =========================================================
# 3. CẤU TRÚC DỰ ÁN (Project Structure)
# =========================================================
def get_project_structure(project_name):
    """
    Trả về đường dẫn các folder của 1 Dự án
    """
    # Đường dẫn đến thư mục Dự án: workspace/Ten_Du_An
    project_path = os.path.join(WORKSPACE, project_name)
    
    paths = {
        "root": project_path,
        "0_audio_raw": os.path.join(project_path, "0_audio_raw"), # Input Step 1 (MP3/WAV)
        "1_input":     os.path.join(project_path, "1_input"),     # Output Step 1 (SRT)
        "2_prompts":   os.path.join(project_path, "2_prompts"),   # Output Step 2 (JSON)
        "3_assets":    os.path.join(project_path, "3_assets"),    # Output Step 3 (Images)
        "4_final":     os.path.join(project_path, "4_final")      # Output Step 4 (Video)
    }

    # Tự động tạo folder nếu chưa có
    # (Thêm try-except để an toàn khi nhiều luồng cùng tạo 1 lúc)
    for p in paths.values():
        if not os.path.exists(p):
            try:
                os.makedirs(p, exist_ok=True)
            except OSError:
                pass # Bỏ qua nếu luồng khác đã tạo rồi
        
    return paths