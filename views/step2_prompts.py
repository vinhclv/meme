import streamlit as st
import os
import glob
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import Settings
from config.settings import get_project_structure, PROFILES_DIR
from config.selectors import GEMINI_CONFIG
from services.prompt_generator import VisualPromptGenerator

def process_single_file(file_info, assigned_profile_json, gemini_url, chunk_size, dir_output):
    """Worker xử lý 1 file SRT -> JSON"""
    input_path = file_info['path']
    file_name = file_info['name']
    
    base_name = os.path.splitext(file_name)[0]
    output_filename = f"{base_name}_prompts.json"
    output_path = os.path.join(dir_output, output_filename)
    
    local_gen = VisualPromptGenerator() 
    
    result_dict = {
        "file": file_name,
        "path": output_path,
        "status": "failed",
        "msg": "Unknown Error",
        "profile": os.path.basename(assigned_profile_json)
    }

    try:
        success = local_gen.generate_via_gemini_web(
            input_srt_path=input_path,
            output_json_path=output_path,
            profile_json_path=assigned_profile_json,
            chunk_size=chunk_size,
            gemini_url=gemini_url
        )
        
        if success:
            result_dict["status"] = "success"
            result_dict["msg"] = "OK"
        else:
            result_dict["msg"] = "Logic returned False"
            
    except Exception as e:
        result_dict["msg"] = str(e)
        
    return result_dict

def render():
    current_proj = st.session_state.get("current_project")
    if not current_proj:
        st.warning("👈 Vui lòng chọn một Dự Án!")
        return

    paths = get_project_structure(current_proj)
    DIR_INPUT = paths["1_input"]
    DIR_OUTPUT = paths["2_prompts"]

    st.header(f"🤖 Step 2: Batch Prompt Generation")

    # =========================================================
    # 1. LOAD FILE SRT (TỰ ĐỘNG + KÉO THẢ)
    # =========================================================
    
    # A. Quét tự động trong folder
    auto_files = glob.glob(os.path.join(DIR_INPUT, "*.srt"))
    file_options = []
    
    for f in auto_files:
        file_options.append({"name": os.path.basename(f), "path": f, "source": "Auto"})

    # B. Kéo thả thủ công (Đã khôi phục lại cho bạn)
    uploaded_files = st.file_uploader("Hoặc kéo thả file SRT vào đây:", type=["srt"], accept_multiple_files=True)
    if uploaded_files:
        for up_file in uploaded_files:
            # Lưu file upload vào folder input để xử lý
            save_path = os.path.join(DIR_INPUT, up_file.name)
            with open(save_path, "wb") as f:
                f.write(up_file.getbuffer())
            
            # Thêm vào danh sách nếu chưa có
            if save_path not in [x['path'] for x in file_options]:
                file_options.append({"name": up_file.name, "path": save_path, "source": "Upload"})
                st.toast(f"Đã lưu file: {up_file.name}")

    if not file_options:
        st.info("Chưa có file SRT nào. Hãy chạy Step 1 hoặc kéo file vào trên.")
        return

    # =========================================================
    # 2. CHỌN PROFILE & CẤU HÌNH
    # =========================================================
    selected_profile_names = st.session_state.get("selected_profiles", [])
    if not selected_profile_names:
        st.error("⚠️ Bạn chưa chọn Profile nào ở thanh bên trái (Sidebar)!")
        return

    available_profiles_paths = [os.path.join(PROFILES_DIR, name) for name in selected_profile_names]

    # =========================================================
    # 3. UI DATA EDITOR
    # =========================================================
    data_list = []
    for item in file_options:
        f_name = item["name"]
        expected_json = os.path.join(DIR_OUTPUT, f"{os.path.splitext(f_name)[0]}_prompts.json")
        status_icon = "✅ Đã xong" if os.path.exists(expected_json) else "⚪ Chưa làm"
        
        data_list.append({
            "Chạy": False, 
            "Tên File": f_name, 
            "Nguồn": item["source"],
            "Trạng Thái": status_icon, 
            "Đường dẫn": item["path"]
        })
    
    df = pd.DataFrame(data_list)
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("📋 Danh sách Input")
        c1, c2 = st.columns(2)
        if c1.button("✅ Chọn tất cả"): st.session_state['s2_all'] = True
        if c2.button("❌ Bỏ chọn"): st.session_state['s2_all'] = False
        
        if 's2_all' in st.session_state:
            df["Chạy"] = st.session_state['s2_all']
            del st.session_state['s2_all']

        edited_df = st.data_editor(
            df, 
            column_config={
                "Chạy": st.column_config.CheckboxColumn("Chọn", default=False), 
                "Đường dẫn": None
            }, 
            use_container_width=True, 
            hide_index=True
        )
    
    files_to_process = [{"name": r["Tên File"], "path": r["Đường dẫn"]} for _, r in edited_df[edited_df["Chạy"]].iterrows()]

    with col2:
        st.subheader("⚙️ Cấu hình")
        
        # 👇 [FIX SLIDER CRASH]
        max_limit = len(available_profiles_paths)
        if max_limit > 1:
            max_threads = st.slider("Số luồng:", 1, max_limit, min(2, max_limit))
        else:
            st.info("ℹ️ Đang chạy 1 Profile")
            max_threads = 1
            
        chunk_size = st.number_input("Chunk Size:", 1, 50, 20)
        st.write("")
        btn_start = st.button(f"🚀 CHẠY ({len(files_to_process)})", type="primary", disabled=not files_to_process, use_container_width=True)

    # =========================================================
    # 4. THỰC THI
    # =========================================================
    if btn_start:
        st.divider()
        status_box = st.status(f"⏳ Đang xử lý {len(files_to_process)} files...", expanded=True)
        log = status_box.empty()
        pbar = status_box.progress(0)
        results = []
        
        count = 0
        with ThreadPoolExecutor(max_threads) as executor:
            futures = {}
            for i, f_info in enumerate(files_to_process):
                # Round Robin Profile
                prof = available_profiles_paths[i % len(available_profiles_paths)]
                
                futures[executor.submit(
                    process_single_file, 
                    f_info, prof, 
                    GEMINI_CONFIG["URL"], 
                    chunk_size, DIR_OUTPUT
                )] = f_info["name"]

            for future in as_completed(futures):
                fname = futures[future]
                try:
                    data = future.result()
                    results.append(data)
                    icon = "✅" if data["status"] == "success" else "❌"
                    log.write(f"{icon} **{fname}** ({data['profile']})")
                except Exception as e:
                    log.write(f"🔥 Lỗi {fname}: {e}")
                
                count += 1
                pbar.progress(count / len(files_to_process))

        status_box.update(label="Hoàn tất!", state="complete", expanded=False)
        if results:
            st.dataframe(pd.DataFrame(results)[["file", "status", "profile", "msg"]], use_container_width=True)