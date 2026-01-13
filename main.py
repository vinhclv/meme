# main.py
import streamlit as st
import os

# 👇 Import thêm các hàm cần thiết
from config.settings import PROJECT_NAME, WORKSPACE
from utils.helpers import get_projects 
import views  # Import file tổng hợp __init__.py

# Cấu hình trang (Phải đặt đầu tiên)
st.set_page_config(page_title=PROJECT_NAME, layout="wide")

def main():

    
    # 1. Lấy danh sách dự án
    project_list = get_projects()
    
    # 2. Tạo options cho Dropdown (Thêm nút Tạo mới lên đầu)
    options = ["➕ Tạo dự án mới..."] + project_list
    
    # 3. Khởi tạo Session State nếu chưa có
    if "current_project" not in st.session_state:
        st.session_state.current_project = None

    # Xác định index mặc định (để giữ lựa chọn khi reload)
    default_index = 0
    if st.session_state.current_project in project_list:
        default_index = options.index(st.session_state.current_project)

    # 4. Hiển thị Dropdown
    selected_option = st.sidebar.selectbox(
        "Chọn Dự Án đang làm:", 
        options, 
        index=default_index
    )

    # 5. Xử lý logic khi chọn
    if selected_option == "➕ Tạo dự án mới...":
        # Form tạo nhanh
        with st.sidebar.expander("Nhập tên dự án", expanded=True):
            new_proj_name = st.text_input("Tên dự án mới (Không dấu):")
            if st.button("Tạo ngay"):
                if new_proj_name:
                    # Tạo folder vật lý
                    new_path = os.path.join(WORKSPACE, new_proj_name)
                    try:
                        os.makedirs(new_path, exist_ok=True)
                        # Tạo sẵn thư mục con luôn cho tiện
                        os.makedirs(os.path.join(new_path, "0_audio_raw"), exist_ok=True)
                        os.makedirs(os.path.join(new_path, "1_input"), exist_ok=True)
                        os.makedirs(os.path.join(new_path, "2_prompts"), exist_ok=True)
                        os.makedirs(os.path.join(new_path, "3_assets"), exist_ok=True)
                        os.makedirs(os.path.join(new_path, "4_final"), exist_ok=True)
                        
                        st.session_state.current_project = new_proj_name
                        st.success(f"✅ Đã tạo: {new_proj_name}")
                        st.rerun() # Reload lại để cập nhật list
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
                else:
                    st.warning("Vui lòng nhập tên.")
        
        # Khi đang ở chế độ tạo, set project = None để chặn các bước sau
        st.session_state.current_project = None
        
    else:
        # Người dùng chọn 1 dự án có sẵn
        st.session_state.current_project = selected_option
        st.sidebar.success(f"Đang làm việc tại: **{selected_option}**")

    st.sidebar.markdown("---")

    # ==================================================
    # 🔵 SIDEBAR: MENU CHỨC NĂNG (PIPELINE)
    # ==================================================
    st.sidebar.title("🛠️ Video Pipeline")
    
    # Menu chọn bước
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
    # 🟠 MAIN CONTENT: HIỂN THỊ VIEW THEO DỰ ÁN
    # ==================================================
    
    # Kiểm tra xem đã chọn dự án chưa
    if not st.session_state.current_project:
        st.title("👋 Chào mừng đến với Video Automation")
        st.info("👈 Vui lòng **Chọn** hoặc **Tạo mới** một Dự án ở thanh bên trái để bắt đầu.")
        return # Dừng lại, không load các view bên dưới

    # Nếu đã chọn dự án, hiển thị tiêu đề và View tương ứng
    st.header(f"📂 Project: {st.session_state.current_project}")

    if "1." in choice:
        views.render_step1()
    elif "2." in choice:
        views.render_step2()
    elif "3." in choice:
        views.render_step3()
    elif "4." in choice:
        views.render_step4()

if __name__ == "__main__":
    main()