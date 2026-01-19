import streamlit as st
import os
import glob
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# 👇 1. Import PROFILES_DIR trực tiếp từ settings
from config.settings import get_project_structure, PROFILES_DIR
from config.selectors import GEMINI_CONFIG
from services.prompt_generator import VisualPromptGenerator

def process_single_file(file_info, assigned_profile_json, gemini_url, chunk_size, dir_output):
    """
    Hàm worker xử lý 1 file.
    assigned_profile_json: Đường dẫn tuyệt đối đến file JSON profile.
    """
    input_path = file_info['path']
    file_name = file_info['name']
    
    base_name = os.path.splitext(file_name)[0]
    output_filename = f"{base_name}_prompts.json"
    output_path = os.path.join(dir_output, output_filename)
    
    # Khởi tạo Generator
    local_gen = VisualPromptGenerator() 
    
    result_dict = {
        "file": file_name,
        "path": output_path,
        "status": "failed",
        "msg": "Unknown Error",
        "profile": os.path.basename(assigned_profile_json) # Lưu tên profile để debug
    }

    try:
        # Gọi hàm logic xử lý
        success = local_gen.generate_via_gemini_web(
            input_srt_path=input_path,
            output_json_path=output_path,
            profile_json_path=assigned_profile_json, # 👈 Truyền đường dẫn profile
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
    # 0. Lấy Context Dự Án
    current_proj = st.session_state.get("current_project")
    if not current_proj:
        st.warning("👈 Vui lòng chọn một Dự Án!")
        return

    paths = get_project_structure(current_proj)
    DIR_INPUT = paths["1_input"]
    DIR_OUTPUT = paths["2_prompts"]

    st.header(f"🤖 Step 2: Batch Prompt Generation")

    # =========================================================
    # 1. CHUẨN BỊ DỮ LIỆU INPUT & PROFILE
    # =========================================================
    
    # A. Tìm file SRT Input
    srt_files = glob.glob(os.path.join(DIR_INPUT, "*.srt"))
    if not srt_files:
        st.warning("⚠️ Không tìm thấy file SRT input. Hãy chạy Step 1 trước.")
        return

    # B. Lấy danh sách Profile từ Main Sidebar (QUAN TRỌNG)
    # st.session_state.selected_profiles chứa danh sách TÊN FILE (vd: ['profile1.json'])
    selected_profile_names = st.session_state.get("selected_profiles", [])
    
    if not selected_profile_names:
        st.warning("👈 Bạn chưa chọn Profile nào ở thanh bên trái (Sidebar)!")
        st.info("Vui lòng tích chọn ít nhất 1 Profile trong mục '🤖 Cấu hình Automation'.")
        return

    # Chuyển tên file thành đường dẫn tuyệt đối
    available_profiles_paths = [os.path.join(PROFILES_DIR, name) for name in selected_profile_names]

    # =========================================================
    # 2. GIAO DIỆN CHỌN FILE (Data Editor)
    # =========================================================
    
    # Tạo List hiển thị
    data_list = []
    for f_path in srt_files:
        f_name = os.path.basename(f_path)
        expected_json = os.path.join(DIR_OUTPUT, f"{os.path.splitext(f_name)[0]}_prompts.json")
        status_icon = "✅ Đã xong" if os.path.exists(expected_json) else "⚪ Chưa làm"
        
        data_list.append({
            "Chạy": False, 
            "Tên File": f_name, 
            "Trạng Thái": status_icon, 
            "Đường dẫn": f_path
        })
    
    df = pd.DataFrame(data_list)
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📋 Danh sách Input")
        st.caption(f"Đang dùng **{len(available_profiles_paths)}** Profiles để chạy đa luồng.")
        
        # 👇 Thêm nút chọn nhanh tiện lợi
        c_act1, c_act2 = st.columns(2)
        if c_act1.button("✅ Chọn tất cả files"):
            st.session_state['s2_select_all'] = True
        if c_act2.button("❌ Bỏ chọn files"):
            st.session_state['s2_select_all'] = False
            
        # Logic update dataframe từ nút bấm
        if 's2_select_all' in st.session_state:
            df["Chạy"] = st.session_state['s2_select_all']
            del st.session_state['s2_select_all']

        edited_df = st.data_editor(
            df, 
            column_config={
                "Chạy": st.column_config.CheckboxColumn("Chọn", default=False), 
                "Đường dẫn": None
            }, 
            use_container_width=True, 
            hide_index=True,
            key="editor_step2_main"
        )
    
    # Lấy danh sách file user đã tick
    selected_rows = edited_df[edited_df["Chạy"] == True]
    files_to_process = []
    for _, row in selected_rows.iterrows():
        files_to_process.append({"name": row["Tên File"], "path": row["Đường dẫn"]})

    with col2:
        st.subheader("⚙️ Cấu hình")
        # Số luồng tối đa = Số profile người dùng đã chọn
        max_limit = len(available_profiles_paths)
        
        max_threads = st.slider(
            "Số luồng:", 
            1, max_limit, 
            value=min(2, max_limit), 
            help=f"Bạn đã chọn {max_limit} profile. Tối đa chạy được {max_limit} luồng."
        )
        
        chunk_size = st.number_input("Chunk Size:", 1, 50, 20)
        
        st.write("")
        btn_start = st.button(
            f"🚀 CHẠY ({len(files_to_process)})", 
            type="primary", 
            use_container_width=True, 
            disabled=(len(files_to_process) == 0)
        )

    # =========================================================
    # 3. THỰC THI ĐA LUỒNG
    # =========================================================
    if btn_start:
        st.divider()
        status_container = st.status(f"⏳ Đang khởi chạy {max_threads} luồng...", expanded=True)
        log_area = status_container.empty()
        progress_bar = status_container.progress(0)
        results = []
        
        total_files = len(files_to_process)
        completed_count = 0
        #Phân công Profile cho từng file
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_file = {}
            for i, f_info in enumerate(files_to_process):
                # PHÂN PHỐI PROFILE (Round Robin) dựa trên danh sách user ĐÃ CHỌN
                assigned_profile = available_profiles_paths[i % len(available_profiles_paths)]
                
                future = executor.submit(
                    process_single_file, 
                    f_info, 
                    assigned_profile, 
                    GEMINI_CONFIG["URL"], 
                    chunk_size, 
                    DIR_OUTPUT
                )
                future_to_file[future] = f_info["name"]

            for future in as_completed(future_to_file):
                f_name = future_to_file[future]
                try:
                    data = future.result()
                    results.append(data)
                    
                    # Log kết quả
                    if data["status"] == "success":
                        log_area.write(f"✅ **{f_name}** | 👤 {data['profile']}")
                    else:
                        log_area.write(f"❌ **{f_name}** | 👤 {data['profile']} | Lỗi: {data['msg']}")
                        
                except Exception as e:
                    log_area.write(f"🔥 Crash **{f_name}**: {e}")
                
                # Update progress
                completed_count += 1
                progress_bar.progress(completed_count / total_files)

        status_container.update(label="✅ Hoàn tất!", state="complete", expanded=False)
        
        if results:
            st.dataframe(
                pd.DataFrame(results)[["file", "status", "profile", "msg"]], 
                use_container_width=True
            )