import streamlit as st
import os
import glob
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from config.settings import get_project_structure, PROFILES_DIR
from services.visual_generator import VisualGenerator

def process_visual_task(file_info, assigned_profile_json, engine, dir_output):
    """Worker chạy đa luồng"""
    input_path = file_info['path']
    file_name = file_info['name']
    
    # Tạo folder chứa ảnh riêng cho từng file JSON
    base_name = os.path.splitext(file_name)[0].replace("_prompts", "")
    assets_folder = os.path.join(dir_output, f"{base_name}_assets")
    if not os.path.exists(assets_folder): os.makedirs(assets_folder)

    # Khởi tạo Generator
    local_gen = VisualGenerator(engine=engine) 
    
    result = {"file": file_name, "profile": os.path.basename(assigned_profile_json), "status": "failed", "msg": "Unknown"}

    try:
        success = local_gen.generate_images(
            input_prompts_path=input_path,
            output_folder=assets_folder,
            profile_json_path=assigned_profile_json
        )
        if success:
            result["status"] = "success"
            result["msg"] = f"Lưu tại: {os.path.basename(assets_folder)}"
        else:
            result["msg"] = "Có lỗi xảy ra (Xem log)"
    except Exception as e:
        result["msg"] = str(e)
    
    return result

def render():
    current_proj = st.session_state.get("current_project")
    if not current_proj:
        st.warning("👈 Chọn Dự Án trước!")
        return

    paths = get_project_structure(current_proj)
    DIR_INPUT = paths["2_prompts"]
    DIR_OUTPUT = paths["3_assets"]

    st.header(f"🎨 Step 3: Tạo Ảnh Đa Luồng")

    # =========================================================
    # 1. LIST FILE & PROFILE
    # =========================================================
    json_files = glob.glob(os.path.join(DIR_INPUT, "*_prompts.json"))
    selected_profiles = st.session_state.get("selected_profiles", [])
    
    if not json_files:
        st.warning("⚠️ Không có file JSON.")
        return
    if not selected_profiles:
        st.error("⚠️ Chưa chọn Profile ở Menu trái.")
        return

    profile_paths = [os.path.join(PROFILES_DIR, n) for n in selected_profiles]

    # =========================================================
    # 2. UI CHỌN FILE
    # =========================================================
    df = pd.DataFrame([{"Chạy": False, "File": os.path.basename(f), "Path": f} for f in json_files])
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Danh sách Prompt")
        c_act1, c_act2 = st.columns(2)
        if c_act1.button("✅ Chọn tất cả"):
            st.session_state['s3_all'] = True
        if c_act2.button("❌ Bỏ chọn hết"):
            st.session_state['s3_all'] = False
            
        if 's3_all' in st.session_state:
            df["Chạy"] = st.session_state['s3_all']
            del st.session_state['s3_all']
            
        edited_df = st.data_editor(df, column_config={"Chạy": st.column_config.CheckboxColumn("Chọn"), "Path": None}, use_container_width=True, hide_index=True)

    files_to_run = [{"name": r["File"], "path": r["Path"]} for _, r in edited_df[edited_df["Chạy"]].iterrows()]

    with col2:
        st.subheader("Cấu hình")
        # Chọn Model (Bạn đã bỏ Banana Pro nên tôi cập nhật theo list mới của bạn)
        engine_label = st.radio("Model:", ["Flow (Flux)", "Google Veo"])
        engine_map = {"Flow (Flux)": "flow", "Google Veo": "google_veo"}
        selected_engine = engine_map[engine_label]

        # Fix lỗi Slider
        max_limit = len(profile_paths)
        if max_limit > 1:
            max_threads = st.slider("Số luồng:", 1, max_limit, min(2, max_limit))
        else:
            st.info("ℹ️ Đang chạy 1 luồng (1 Profile)")
            max_threads = 1
            
        st.write("")
        btn_start = st.button(f"🚀 CHẠY ({len(files_to_run)})", type="primary", disabled=not files_to_run)

    # =========================================================
    # 3. THỰC THI
    # =========================================================
    if btn_start:
        st.divider()
        status = st.status(f"⏳ Đang chạy {max_threads} luồng với {selected_engine}...", expanded=True)
        log = status.empty()
        pbar = status.progress(0)
        
        with ThreadPoolExecutor(max_threads) as ex:
            futures = {}
            for i, f in enumerate(files_to_run):
                prof = profile_paths[i % len(profile_paths)]
                futures[ex.submit(process_visual_task, f, prof, selected_engine, DIR_OUTPUT)] = f["name"]
            
            for i, fut in enumerate(as_completed(futures)):
                res = fut.result()
                icon = "✅" if res["status"] == "success" else "❌"
                log.write(f"{icon} **{res['file']}** ({res['profile']}): {res['msg']}")
                pbar.progress((i + 1) / len(files_to_run))
        
        status.update(label="Xong!", state="complete")

    # =========================================================
    # 4. VIEW KẾT QUẢ (GALLERY) - PHẦN BẠN CẦN
    # =========================================================
    st.divider()
    
    # Quét các folder con trong thư mục 3_assets
    # Mỗi folder con tương ứng với 1 video
    subfolders = [f.path for f in os.scandir(DIR_OUTPUT) if f.is_dir()]
    
    if subfolders:
        st.subheader("🖼️ Thư viện Kết quả")
        
        # Tạo Selectbox để chọn folder muốn xem
        # Map tên folder -> đường dẫn full
        folder_map = {os.path.basename(p): p for p in subfolders}
        selected_folder_name = st.selectbox("Chọn bộ ảnh để xem:", list(folder_map.keys()))
        
        if selected_folder_name:
            current_view_path = folder_map[selected_folder_name]
            
            # Lấy tất cả file ảnh/video trong folder đó
            files = sorted(os.listdir(current_view_path))
            media_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4'))]
            
            if media_files:
                st.caption(f"Tìm thấy {len(media_files)} files trong `{selected_folder_name}`")
                
                # Hiển thị dạng lưới 4 cột
                cols = st.columns(4)
                for idx, file_name in enumerate(media_files):
                    file_path = os.path.join(current_view_path, file_name)
                    col = cols[idx % 4]
                    
                    if file_name.lower().endswith('.mp4'):
                        col.video(file_path)
                    else:
                        col.image(file_path, caption=file_name, use_container_width=True)
            else:
                st.info("Folder này trống (chưa có ảnh).")
    else:
        st.info("Chưa có kết quả nào trong folder `3_assets`.")