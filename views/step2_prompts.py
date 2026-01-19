import streamlit as st
import os
import time
import json
import glob
import shutil

# 👇 Import cấu hình & Hàm quản lý thư mục
from config.settings import WORKSPACE, get_project_structure
from config.selectors import GEMINI_CONFIG
from services.prompt_generator import VisualPromptGenerator

def render():
    # =========================================================
    # 0. KHỞI TẠO CONTEXT DỰ ÁN
    # =========================================================
    current_proj = st.session_state.get("current_project")
    
    if not current_proj:
        st.warning("👈 Vui lòng chọn một Dự Án ở thanh bên trái để bắt đầu!")
        return

    # 👇 LẤY ĐƯỜNG DẪN TỪ CONFIG (QUAN TRỌNG)
    paths = get_project_structure(current_proj)
    
    # Định nghĩa Input/Output chuẩn cho Step 2
    DIR_INPUT = paths["1_input"]     # Lấy SRT từ đây
    DIR_OUTPUT = paths["2_prompts"]  # Lưu JSON vào đây

    st.header(f"🤖 Step 2: Tạo Prompts - Dự án: {current_proj}")

    # =========================================================
    # 1. KHU VỰC UPLOAD FILE MỚI (Vào thẳng 1_input)
    # =========================================================
    with st.expander("📂 Tải lên file SRT mới (vào 1_input)"):
        uploaded_file = st.file_uploader("Chọn file .srt:", type=["srt"])
        if uploaded_file is not None:
            # Lưu file vào đúng folder 1_input
            save_path = os.path.join(DIR_INPUT, uploaded_file.name)
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            time.sleep(1)
            st.rerun() 

    # =========================================================
    # 2. QUẢN LÝ FILE ĐẦU VÀO (CHỈ QUÉT TRONG 1_INPUT)
    # =========================================================
    search_pattern = os.path.join(DIR_INPUT, "*.srt")
    all_srt_paths = glob.glob(search_pattern)
    
    if not all_srt_paths:
        st.warning(f"⚠️ Chưa có file SRT nào trong folder `1_input`. Hãy chạy Step 1 hoặc upload file.")
        return

    # Tạo danh sách hiển thị
    display_options = {os.path.basename(p): p for p in all_srt_paths}
    
    col_sel, col_view = st.columns([3, 1])
    with col_sel:
        selected_filename = st.selectbox("Chọn file SRT từ 1_input:", list(display_options.keys()), index=0)
        selected_abs_path = display_options[selected_filename]
    
    with col_view:
        with st.popover("📝 Xem nội dung"):
            with open(selected_abs_path, "r", encoding="utf-8") as f:
                st.text(f.read())

    st.divider()

    # =========================================================
    # 3. CẤU HÌNH AI
    # =========================================================
    col_conf1, col_conf2 = st.columns(2)
    
    with col_conf1:
        st.subheader("⚙️ Cấu hình")
        ai_source = st.radio("Chọn nguồn AI:", ["Gemini Web Automation (Free)", "LM Studio (Local API)"])
        chunk_size = st.number_input("Chunk Size (Số dòng gửi 1 lần):", min_value=1, max_value=50, value=20)

    with col_conf2:
        if "Local API" in ai_source:
            local_api_url = st.text_input("API URL:", "http://localhost:1234/v1")
            local_model = st.text_input("Model Name:", "mistral-7b-instruct")
        else:
            gemini_link = GEMINI_CONFIG["URL"]  # Lấy từ config

    # =========================================================
    # 4. THỰC THI (INPUT -> OUTPUT)
    # =========================================================
    st.write("")
    btn_start = st.button("🚀 BẮT ĐẦU TẠO PROMPT (Output -> 2_prompts)", type="primary", use_container_width=True)

    log_container = st.empty()
    def update_ui_log(msg):
        log_container.info(f"🤖 {msg}")

    # Session state để lưu đường dẫn kết quả
    if "final_json_path" not in st.session_state:
        st.session_state.final_json_path = None

    if btn_start:
        # 1. Xác định tên file Output
        # Input: video.srt -> Output: video_prompts.json
        base_name = os.path.splitext(selected_filename)[0]
        output_filename = f"{base_name}_prompts.json"
        
        # 2. Đường dẫn Output nằm trong 2_prompts
        output_json_path = os.path.join(DIR_OUTPUT, output_filename)
        st.session_state.final_json_path = output_json_path

        st.toast(f"📂 Đang xử lý file: {selected_filename}")

        # 3. Chạy Generator
        generator = VisualPromptGenerator(status_callback=update_ui_log)
        success = False
        
        try:
            if "Gemini Web" in ai_source:
                with st.spinner("Đang chạy Automation..."):
                    success = generator.generate_via_gemini_web(
                        input_srt_path=selected_abs_path,   # Lấy từ 1_input
                        output_json_path=output_json_path,  # Lưu vào 2_prompts
                        chunk_size=chunk_size,
                        gemini_url=gemini_link
                    )
            else:
                # Code cho Local API (chưa implement)
                pass 

            if success:
                st.success(f"✅ Đã tạo xong! File lưu tại: `{output_json_path}`")
            else:
                st.error("❌ Có lỗi xảy ra. Xem log bên trên.")
                
        except Exception as e:
            st.error(f"Lỗi: {e}")

    # =========================================================
    # 5. HIỂN THỊ KẾT QUẢ
    # =========================================================
    st.divider()
    
    current_json_path = st.session_state.final_json_path

    # Kiểm tra file output có tồn tại không
    if current_json_path and os.path.exists(current_json_path):
        st.subheader("📊 Kết quả Prompt JSON (Folder: 2_prompts)")
        
        with open(current_json_path, "r", encoding="utf-8") as f:
            try:
                json_data = json.load(f)
                
                col_dl, col_json = st.columns([1, 4])
                with col_dl:
                    st.download_button(
                        label="⬇️ Tải JSON",
                        data=json.dumps(json_data, indent=4, ensure_ascii=False),
                        file_name=os.path.basename(current_json_path),
                        mime="application/json"
                    )
                
                with col_json:
                    st.json(json_data, expanded=False)
                    with st.expander("Xem dạng bảng"):
                        st.dataframe(json_data, use_container_width=True)

            except json.JSONDecodeError:
                st.error("⚠️ File output lỗi format JSON.")