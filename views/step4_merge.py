# views/step4_merge.py
import streamlit as st
import time
import os
from config.settings import WORKSPACE
from utils.helpers import save_file, render_artifact_viewer

def render():
    st.header("🏁 Bước 4: Hợp nhất Video cuối cùng")
    
    if st.button("🚀 Render Final Video", type="primary"):
        with st.spinner("Đang chạy FFmpeg..."):
            time.sleep(2)
            # Giả lập tạo video
            save_file("fake_video_content", "final_video.mp4")
            st.balloons()
            st.success("Render thành công!")

    render_artifact_viewer(os.path.join(WORKSPACE, "final_video.mp4"), "Video Thành Phẩm")