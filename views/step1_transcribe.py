import streamlit as st
import os
import time
import glob
import shutil

# 👇 Import cấu hình
from config.settings import WORKSPACE,get_project_structure

def render():
    # =========================================================
    # 0. KHỞI TẠO CONTEXT DỰ ÁN
    # =========================================================
    current_proj = st.session_state.get("current_project")
    
    if not current_proj:
        st.warning("👈 Chọn dự án trước!")
        return

    st.header("🎙️ Step 1: Transcribe")

    # =========================================================
    # 👇 THAY THẾ ĐOẠN ĐỊNH NGHĨA PATH CŨ BẰNG ĐOẠN NÀY
    # =========================================================
    # Hàm này trả về dict chứa toàn bộ đường dẫn đã tạo sẵn
    paths = get_project_structure(current_proj)

    # Lấy đường dẫn ra dùng cực gọn:
    DIR_INPUT  = paths["0_audio_raw"]  # Input của Step 1
    DIR_OUTPUT = paths["1_input"]      # Output của Step 1


    # =========================================================
    # 1. CÁCH 2: UPLOAD FILE AUDIO (Kéo thả -> 0_audio_raw)
    # =========================================================
    with st.expander("📂 Upload Audio mới (Đẩy vào folder 0_audio_raw)", expanded=False):
        uploaded_file = st.file_uploader("Kéo thả file Audio (mp3, wav, m4a):", type=['mp3', 'wav', 'm4a'])
        
        if uploaded_file is not None:
            # Lưu file vào folder Input của Step 1
            save_path = os.path.join(DIR_INPUT, uploaded_file.name)
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"✅ Đã thêm audio `{uploaded_file.name}` vào kho.")
            time.sleep(1)
            st.rerun() # Refresh để cập nhật danh sách chọn bên dưới

    # =========================================================
    # 2. CÁCH 1: CHỌN AUDIO ĐỂ THỰC THI (Lấy từ 0_audio_raw)
    # =========================================================
    # Quét các file audio trong folder
    search_pattern = os.path.join(DIR_INPUT, "*.*")
    # Lọc đuôi file audio
    valid_ext = ['.mp3', '.wav', '.m4a']
    all_audio_paths = [f for f in glob.glob(search_pattern) if os.path.splitext(f)[1].lower() in valid_ext]
    
    if not all_audio_paths:
        st.warning(f"⚠️ Chưa có Audio nào trong `0_audio_raw`. Vui lòng upload hoặc copy file vào folder này.")
        return

    # Map tên file -> đường dẫn
    files_map = {os.path.basename(p): p for p in all_audio_paths}
    
    col_sel, col_player = st.columns([3, 1])
    with col_sel:
        selected_filename = st.selectbox("Chọn Audio để xử lý:", list(files_map.keys()))
        selected_audio_path = files_map[selected_filename]

    with col_player:
        # Nghe thử audio đã chọn
        st.audio(selected_audio_path)

    st.divider()

    # =========================================================
    # 3. THỰC THI WHISPER (Input Audio -> Output SRT)
    # =========================================================
    btn_run = st.button("🚀 Chạy Whisper (Output -> 1_input)", type="primary", use_container_width=True)

    if btn_run:
        # Định nghĩa đường dẫn output
        # Ví dụ: file gốc "meeting.mp3" -> output "meeting.srt" trong folder 1_input
        base_name = os.path.splitext(selected_filename)[0]
        output_srt_name = f"{base_name}.srt"
        target_output_path = os.path.join(DIR_OUTPUT, output_srt_name)

        with st.status("Đang xử lý Whisper...", expanded=True) as s:
            st.write("🔹 Đang tải model Whisper...")
            time.sleep(1) # Giả lập load model
            
            st.write(f"🔹 Đang transcribe file: {selected_filename}...")
            # --- LOGIC GỌI WHISPER THỰC TẾ Ở ĐÂY ---
            # Ví dụ giả lập kết quả trả về
            time.sleep(2) 
            
            fake_srt_content = (
                "1\n00:00:01 --> 00:00:05\nChào bạn, đây là nội dung từ file audio " + selected_filename + ".\n\n"
                "2\n00:00:05 --> 00:00:10\nQuy trình này đảm bảo output step 1 vào đúng input step 2."
            )
            
            # Lưu file vào folder 1_input
            with open(target_output_path, "w", encoding="utf-8") as f:
                f.write(fake_srt_content)
            
            s.update(label="✅ Hoàn tất!", state="complete")
            
            st.success(f"Đã lưu SRT vào: `1_input/{output_srt_name}`")
            
            # Lưu path vào session để hiển thị kết quả
            st.session_state["step1_last_output"] = target_output_path

    # =========================================================
    # 4. HIỂN THỊ KẾT QUẢ
    # =========================================================
    last_output = st.session_state.get("step1_last_output")
    
    if last_output and os.path.exists(last_output):
        st.divider()
        st.subheader("📄 Kết quả SRT (Folder: 1_input)")
        with open(last_output, "r", encoding="utf-8") as f:
            st.text_area("Nội dung file:", f.read(), height=200)