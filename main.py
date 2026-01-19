import streamlit as st
import os

# 👇 Import thêm các hàm cần thiết
from config.settings import PROJECT_NAME, WORKSPACE
from utils.helpers import get_projects 
import views  # Import file tổng hợp __init__.py

# Cấu hình trang (Phải đặt đầu tiên)
st.set_page_config(page_title=PROJECT_NAME, layout="wide")

# --- CẤU HÌNH ĐƯỜNG DẪN PROFILES ---
# Giả sử thư mục profiles nằm cùng cấp với main.py
ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(ROOT_PATH, "profiles")

def get_available_profiles():
    """Hàm helper để quét danh sách các file json profile"""
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR)
        return []
    # Lấy các file .json
    return [f for f in os.listdir(PROFILES_DIR) if f.endswith('.json')]

def main():

    # 1. Lấy danh sách dự án
    project_list = get_projects()
    
    # 2. Tạo options cho Dropdown (Thêm nút Tạo mới lên đầu)
    options = ["➕ Tạo dự án mới..."] + project_list
    
    # 3. Khởi tạo Session State
    if "current_project" not in st.session_state:
        st.session_state.current_project = None
    if "selected_profiles" not in st.session_state:
        st.session_state.selected_profiles = []

    # Xác định index mặc định
    default_index = 0
    if st.session_state.current_project in project_list:
        default_index = options.index(st.session_state.current_project)

    # 4. Hiển thị Dropdown CHỌN DỰ ÁN
    st.sidebar.title("🗂️ Quản lý Dự Án")
    selected_option = st.sidebar.selectbox(
        "Đang làm việc tại:", 
        options, 
        index=default_index,
        label_visibility="collapsed"
    )

    # 5. Xử lý logic khi chọn Dự Án
    if selected_option == "➕ Tạo dự án mới...":
        with st.sidebar.expander("Nhập tên dự án", expanded=True):
            new_proj_name = st.text_input("Tên dự án mới (Không dấu):")
            if st.button("Tạo ngay"):
                if new_proj_name:
                    new_path = os.path.join(WORKSPACE, new_proj_name)
                    try:
                        os.makedirs(new_path, exist_ok=True)
                        # Tạo các sub-folder pipeline
                        sub_folders = ["0_audio_raw", "1_input", "2_prompts", "3_assets", "4_final"]
                        for folder in sub_folders:
                            os.makedirs(os.path.join(new_path, folder), exist_ok=True)
                        
                        st.session_state.current_project = new_proj_name
                        st.success(f"✅ Đã tạo: {new_proj_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
                else:
                    st.warning("Vui lòng nhập tên.")
        st.session_state.current_project = None
    else:
        st.session_state.current_project = selected_option
        st.sidebar.success(f"Project: **{selected_option}**")

    st.sidebar.markdown("---")

    # ==================================================
    # 🤖 SIDEBAR: CHỌN PROFILE (NEW FEATURE)
    # ==================================================
    st.sidebar.title("🤖 Cấu hình Automation")
    
    available_profiles = get_available_profiles()
    
    if not available_profiles:
        st.sidebar.warning("⚠️ Không tìm thấy file JSON nào trong thư mục 'profiles'!")
    else:
        # --- LOGIC CHỌN TOÀN BỘ ---
        # 1. Định nghĩa hàm callback để cập nhật state
        def select_all():
            st.session_state.selected_profiles = available_profiles

        def deselect_all():
            st.session_state.selected_profiles = []

        # 2. Tạo 2 nút bấm nhỏ (chia cột cho đẹp)
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.button("Chọn hết", on_click=select_all, use_container_width=True)
        with col2:
            st.button("X", on_click=deselect_all, use_container_width=True)

        # 3. Multiselect (Quan trọng: dùng tham số 'key' trùng tên với biến trong session_state)
        # Khi dùng 'key', Streamlit sẽ tự động map giá trị của widget vào st.session_state.selected_profiles
        st.sidebar.multiselect(
            "Chọn Profiles chạy:",
            options=available_profiles,
            key="selected_profiles"  # <--- KEY NÀY TỰ ĐỘNG SYNC VỚI SESSION STATE
        )
        
        # Lấy giá trị ra để hiển thị thông tin (nếu cần xử lý logic ngay)
        selected_profiles = st.session_state.selected_profiles
        
        if selected_profiles:
            st.sidebar.caption(f"Đã chọn: {len(selected_profiles)} profiles")
        else:
            st.sidebar.info("Chưa chọn profile nào.")

    st.sidebar.markdown("---")

    # ==================================================
    # 🔵 SIDEBAR: MENU CHỨC NĂNG (PIPELINE)
    # ==================================================
    st.sidebar.title("🛠️ Video Pipeline")
    
    choice = st.sidebar.radio(
        "Quy trình xử lý:",
        ["1. Transcribe (SRT)", 
         "2. AI Prompts (JSON)", 
         "3. Visual Gen (Assets)", 
         "4. Final Merge (Video)"]
    )
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Xóa Workspace"):
        st.sidebar.warning("Tính năng dọn dẹp chưa kích hoạt.")

    # ==================================================
    # 🟠 MAIN CONTENT
    # ==================================================
    
    if not st.session_state.current_project:
        st.title("👋 Video Automation System")
        st.info("👈 Vui lòng **Chọn** hoặc **Tạo mới** một Dự án để bắt đầu.")
        return 

    st.header(f"📂 {st.session_state.current_project}")

    # Render Views
    if "1." in choice:
        views.render_step1()
    elif "2." in choice:
        views.render_step2()
    elif "3." in choice:
        # Truyền danh sách profiles vào step 3 nếu cần thiết
        # Hoặc views.render_step3() tự gọi st.session_state.selected_profiles
        views.render_step3() 
    elif "4." in choice:
        views.render_step4()

if __name__ == "__main__":
    main()