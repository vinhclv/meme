# views/step3_visuals.py
import streamlit as st
import os
from config.settings import WORKSPACE

def render():
    st.header("🎬 Bước 3: Tạo hình ảnh/Video ngắn")
    st.info("Module Selenium Automation (Google Veo/Imagen).")
    
    if st.button("🚀 Mở Trình Duyệt & Chạy", type="primary"):
        st.warning("🔄 Đang kết nối Selenium...")
        # Gọi hàm automation ở đây
    
    st.divider()
    st.subheader("🖼️ Thư viện Assets đã tạo")
    
    files = [f for f in os.listdir(WORKSPACE) if f.endswith(('.png', '.mp4'))]
    if files:
        cols = st.columns(3)
        for i, f in enumerate(files):
            path = os.path.join(WORKSPACE, f)
            if f.endswith('.png'):
                cols[i % 3].image(path, caption=f)
            else:
                cols[i % 3].video(path)
    else:
        st.caption("Chưa có file nào trong thư mục visual_assets.")