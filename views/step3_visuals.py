import streamlit as st
import os
import time
import json
import glob

# 👇 Import cấu hình & Hàm quản lý thư mục
from config.settings import WORKSPACE, get_project_structure
# 👇 Import Service sinh ảnh thật
from services.visual_generator import VisualGenerator

def render():
    # =========================================================
    # 0. KHỞI TẠO CONTEXT DỰ ÁN
    # =========================================================
    current_proj = st.session_state.get("current_project")
    
    if not current_proj:
        st.warning("👈 Vui lòng chọn một Dự Án ở thanh bên trái để bắt đầu!")
        return

    # Lấy đường dẫn từ Config
    paths = get_project_structure(current_proj)
    DIR_INPUT = paths["2_prompts"]  # Input: Lấy JSON từ đây
    DIR_OUTPUT = paths["3_assets"]  # Output: Lưu Ảnh/Video vào đây

    st.header(f"🎨 Step 3: Tạo Visual (Ảnh/Video) - Dự án: {current_proj}")

    # =========================================================
    # 1. LOAD DỮ LIỆU ĐẦU VÀO
    # =========================================================
    search_pattern = os.path.join(DIR_INPUT, "*.json")
    all_json_paths = glob.glob(search_pattern)
    
    # Biến json_data cần được khởi tạo trước để tránh lỗi nếu không có file
    json_data = []
    selected_filename = ""

    if not all_json_paths:
        st.warning(f"⚠️ Chưa có file JSON nào trong `2_prompts`. Hãy chạy Step 2 trước.")
    else:
        # Map tên file -> đường dẫn
        display_options = {os.path.basename(p): p for p in all_json_paths}
        
        col_sel, col_view = st.columns([3, 1])
        with col_sel:
            selected_filename = st.selectbox("Chọn Kịch bản Prompts:", list(display_options.keys()), index=0)
            selected_json_path = display_options[selected_filename]
        
        # Load nội dung JSON
        try:
            with open(selected_json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception as e:
            st.error(f"Lỗi đọc file JSON: {e}")
                
        if json_data:
            st.caption(f"Tìm thấy {len(json_data)} cảnh (scenes).")
            with st.expander("Xem bảng dữ liệu Prompt"):
                st.dataframe(json_data)

    st.divider()

    # =========================================================
    # 2. CẤU HÌNH GEN AI
    # =========================================================
    col_conf1, col_conf2 = st.columns(2)
    
    with col_conf1:
        st.subheader("⚙️ Cấu hình Engine")
        ai_engine = st.radio("Chọn nền tảng (Selenium):", ["Banana Pro (Web UI)", "Flow (Web UI)",'Gemini (Web UI)', "Giả lập (Test)"])
    
    # =========================================================
    # 3. THỰC THI (JSON -> ASSETS)
    # =========================================================
    btn_start = st.button("🚀 BẮT ĐẦU SINH ẢNH/VIDEO", type="primary", use_container_width=True, disabled=not json_data)
    
    log_container = st.empty()
    progress_bar = st.progress(0)

    if btn_start and json_data:
        st.toast("Đang khởi động quy trình sinh ảnh...")
        
        # Map lựa chọn từ UI sang key config
        if "Banana" in ai_engine:
            engine_key = "banapro"
        elif "Flow" in ai_engine:
            engine_key = "flow"
        elif "Gemini" in ai_engine:
            engine_key = "google_veo"
        else:
            engine_key = "mock"
        
        # Khởi tạo Generator
        generator = VisualGenerator(engine=engine_key, status_callback=log_container.info)
        
        # Logic mở trình duyệt (Chỉ mở nếu không phải giả lập)
        browser_ready = True
        if "Giả lập" not in ai_engine:
            browser_ready = generator.start_browser()

        if browser_ready:
            
            base_name = os.path.splitext(selected_filename)[0].replace("_prompts", "")
            
            # 👇 MẶC ĐỊNH LẤY HẾT DANH SÁCH
            total_items = len(json_data)
            
            for i in range(total_items):
                item = json_data[i]
                index = item.get("scene_id", i+1)
                
                # 👇 QUAN TRỌNG: Lấy đúng key 'visual_prompt' từ Step 2
                # Fallback về 'prompt' hoặc 'text' nếu file json cũ
                prompt = item
                output_filename = f"{base_name}_scene_{index}.png" 
                output_path = os.path.join(DIR_OUTPUT, output_filename)
                
                if "Giả lập" in ai_engine:
                    log_container.info(f"🎨 [Giả lập] Đang vẽ cảnh {index}: {prompt[:30]}...")
                    time.sleep(1)
                    with open(output_path, "w") as f: f.write("DUMMY IMAGE CONTENT")
                    success = True
                else:
                    # Chạy thật (Selenium)
                    success = generator.generate_image(prompt, output_path)
                
                if success:
                    st.toast(f"✅ Xong cảnh {index}")
                else:
                    st.toast(f"❌ Lỗi cảnh {index}")
                
                # Cập nhật tiến độ
                progress_bar.progress((i + 1) / total_items)
                time.sleep(1) 

            # Đóng trình duyệt (nếu đã mở)
            if "Giả lập" not in ai_engine:
                generator.close_browser()
            
            st.success(f"Đã lưu {total_items} files vào folder: `3_assets`")
            time.sleep(2)
            st.rerun()
        else:
            st.error("❌ Không thể khởi động trình duyệt Chrome!")

    # =========================================================
    # 4. HIỂN THỊ KẾT QUẢ (GALLERY)
    # =========================================================
    st.divider()
    st.subheader("🖼️ Thư viện Assets (Folder: 3_assets)")
    
    asset_files = glob.glob(os.path.join(DIR_OUTPUT, "*.*"))
    # Lọc file ảnh và video
    valid_assets = [f for f in asset_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4'))]
    
    if valid_assets:
        valid_assets.sort(key=os.path.getmtime, reverse=True)
        st.write(f"Tìm thấy {len(valid_assets)} files.")
        
        cols = st.columns(4)
        for idx, file_path in enumerate(valid_assets):
            file_name = os.path.basename(file_path)
            col = cols[idx % 4]
            
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    col.image(file_path, caption=file_name)
                except:
                    col.warning(f"Lỗi ảnh: {file_name}")
            elif file_path.lower().endswith('.mp4'):
                col.video(file_path)
                col.caption(file_name)
    else:
        st.info("Chưa có assets nào.")