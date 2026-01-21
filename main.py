import streamlit as st
import os
import time

# 👇 Import cấu hình & Service mới tách
from config.settings import PROJECT_NAME, WORKSPACE
from utils.helpers import get_projects 
from utils.profiles_setup import (
    get_available_profiles, 
    save_uploaded_profile, 
    delete_profiles_data
)
import views 

st.set_page_config(page_title=PROJECT_NAME, layout="wide")

# ==========================================
# 1. UI CALLBACKS (Chỉ xử lý State & Gọi Service)
# ==========================================

def delete_profile_callback():
    """Callback xử lý sự kiện bấm nút Xóa"""
    selected = st.session_state.get('selected_profiles', [])
    if not selected: return

    # Gọi Service để xóa dữ liệu trên ổ cứng
    count = delete_profiles_data(selected)

    if count > 0:
        st.toast(f"🗑️ Đã xóa {count} profile thành công!", icon="✅")
        # Reset state UI
        st.session_state.selected_profiles = []

def select_all_callback():
    st.session_state.selected_profiles = get_available_profiles()

def deselect_all_callback():
    st.session_state.selected_profiles = []

# ==========================================
# 2. MAIN APP
# ==========================================

def main():
    if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
    if "current_project" not in st.session_state: st.session_state.current_project = None
    if "selected_profiles" not in st.session_state: st.session_state.selected_profiles = []

    # --- SIDEBAR: DỰ ÁN ---
    st.sidebar.title("🗂️ Dự Án")
    project_list = get_projects()
    options = ["➕ Tạo mới..."] + project_list
    
    idx = 0
    if st.session_state.current_project in project_list:
        idx = options.index(st.session_state.current_project)
        
    sel_proj = st.sidebar.selectbox("Chọn dự án:", options, index=idx, label_visibility="collapsed")

    if sel_proj == "➕ Tạo mới...":
        with st.sidebar.form("create_proj_form"):
            new_name = st.text_input("Tên dự án:")
            if st.form_submit_button("Tạo"):
                if new_name:
                    p = os.path.join(WORKSPACE, new_name)
                    try:
                        os.makedirs(p, exist_ok=True)
                        for f in ["0_audio_raw", "1_input", "2_prompts", "3_assets", "4_final"]:
                            os.makedirs(os.path.join(p, f), exist_ok=True)
                        st.session_state.current_project = new_name
                        st.rerun()
                    except: st.error("Lỗi tạo folder")
    else:
        st.session_state.current_project = sel_proj

    st.sidebar.markdown("---")

    # --- SIDEBAR: QUẢN LÝ PROFILE ---
    st.sidebar.subheader("🤖 Profiles")
    
    # 1. Upload
    with st.sidebar.expander("⬆️ Upload Profile", expanded=False):
        uploaded = st.file_uploader(
            "JSON + ZIP:", 
            type=["json", "zip"], 
            accept_multiple_files=True,
            key=f"up_{st.session_state.uploader_key}"
        )
        if uploaded:
            # Gọi Service xử lý upload
            if save_uploaded_profile(uploaded):
                st.toast("✅ Upload thành công!")
                st.session_state.uploader_key += 1
                time.sleep(0.5)
                st.rerun()

    # 2. List & Actions
    available = get_available_profiles() # Gọi Service lấy list
    
    if available:
        c1, c2, c3 = st.sidebar.columns([1, 1, 1])
        c1.button("☑️ All", on_click=select_all_callback, help="Chọn tất cả", use_container_width=True)
        c2.button("⬜ None", on_click=deselect_all_callback, help="Bỏ chọn", use_container_width=True)
        # Nút xóa gọi callback
        c3.button("🗑️ Xóa", on_click=delete_profile_callback, type="primary", help="Xóa mục đã chọn", use_container_width=True)

        st.sidebar.multiselect(
            "Danh sách Profile:",
            options=available,
            key="selected_profiles", 
            label_visibility="collapsed"
        )
        
        count = len(st.session_state.selected_profiles)
        st.sidebar.caption(f"Đang chọn: **{count}** / {len(available)}")
        
    else:
        st.sidebar.info("Chưa có profile nào.")

    st.sidebar.markdown("---")

    # --- CONTENT ---
    if not st.session_state.current_project:
        st.title("👋 Video Automation")
        st.info("👈 Chọn dự án để bắt đầu.")
        return

    st.sidebar.title("🛠️ Menu")
    menu = st.sidebar.radio("Bước:", ["1. Transcribe", "2. Prompts", "3. Visuals", "4. Merge"], label_visibility="collapsed")
    
    st.header(f"📂 {st.session_state.current_project}")
    
    if "1." in menu: views.render_step1()
    elif "2." in menu: views.render_step2()
    elif "3." in menu: views.render_step3()
    elif "4." in menu: views.render_step4()

if __name__ == "__main__":
    main()