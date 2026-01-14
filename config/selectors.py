# config/selectors.py

# config/selectors.py

GEMINI_CONFIG = {
    # 1. URL: Link Gem của bạn (OK)
    "URL": "https://gemini.google.com/gem/1uxRmWBKYok16CVaaQWM93NtbAXNhq78u?usp=sharing",

    # 2. Ô NHẬP LIỆU (QUAN TRỌNG)
    # Thay vì tìm theo class, ta tìm thẻ có thuộc tính contenteditable='true'
    # Đây là tiêu chuẩn của mọi ô nhập liệu Rich Text, Google khó đổi cái này.
    "INPUT_BOX": "div[contenteditable='true'], div[role='textbox']",

    # 3. NÚT GỬI
    # Tìm theo aria-label (nhãn hỗ trợ người khiếm thị) -> Google KHÔNG BAO GIỜ đổi cái này.
    # Thêm mat-icon để bao quát trường hợp nút là icon mũi tên.
    "SEND_BUTTON": "button[aria-label*='Send'], button[aria-label*='Gửi'], button[aria-label*='Submit']",

    # 4. CÂU TRẢ LỜI (QUAN TRỌNG NHẤT)
    # Google dùng thẻ custom <model-response> để bao quanh câu trả lời.
    # Đây là cách định danh chắc chắn nhất hiện nay.
    "RESPONSE_TEXT": "model-response" 
}

VISUAL_CONFIGS = {
    # CẤU HÌNH CHO BANANA PRO (Giao diện Web, ví dụ: Gradio/A1111/ComfyUI chạy trên Banana)
    "banapro": {
        "URL": "https://gemini.google.com/app?android-min-version=301356232&ios-min-version=322.0&is_sa=1&campaign_id=gemini_overview_page&utm_source=gemini&utm_medium=web&utm_campaign=gemini_overview_page&pt=9008&mt=8&ct=gemini_overview_page&hl=vi-VN&_gl=1*dipony*_gcl_aw*R0NMLjE3NjgyODc2MzUuQ2owS0NRaUExSkxMQmhDREFSSXNBQVZmeTdoUVRTVHRiTExBZ1V2SUhaV1FUWmQ3TDJQT1BYVjZ4ZFpyYkl6MmxDeUt0Njd3SDZKd0ItZ2FBc1F0RUFMd193Y0I.*_gcl_dc*R0NMLjE3NjgyODc2MzUuQ2owS0NRaUExSkxMQmhDREFSSXNBQVZmeTdoUVRTVHRiTExBZ1V2SUhaV1FUWmQ3TDJQT1BYVjZ4ZFpyYkl6MmxDeUt0Njd3SDZKd0ItZ2FBc1F0RUFMd193Y0I.*_gcl_au*ODIyNTUwNzQ0LjE3NjgxOTIwMTI.*_ga*OTYzNzUwNDE1LjE3NjgxOTIwMTI.*_ga_WC57KJ50ZZ*czE3NjgyOTAyNzIkbzMkZzAkdDE3NjgyOTAyNzIkajYwJGwwJGgw", # <-- THAY LINK WEB CỦA BẠN VÀO ĐÂY
        
        # Selector ví dụ cho giao diện Gradio thường gặp
        "INPUT_BOX": "textarea[data-testid='textbox'], textarea", 
        "CREATE_BTN": "button#generate, button.generate-box",
        
        # Selector ảnh kết quả
        "RESULT_ELEMENT": "img.output-image, .gallery img", 
        "WAIT_TIME": 30
    },

    # CẤU HÌNH CHO FLOW (Ví dụ FlowGPT hoặc Flow riêng của bạn)
    "flow": {
        # Thay URL này bằng link ComfyUI của bạn (Local hoặc Banana)
        "URL": "https://labs.google/fx/vi/tools/flow/project/8e123f27-16cd-4350-ba26-c5eb10b3387e", 
        
        # Ô nhập Prompt: ComfyUI dùng textarea với class đặc thù
        # Lưu ý: Nó sẽ điền vào ô textarea ĐẦU TIÊN tìm thấy (Thường là Positive Prompt)
        "INPUT_BOX": "textarea.comfy-multiline-input", 
        
        # Nút Queue Prompt (Tạo ảnh)
        "CREATE_BTN": "button#queue-button",
        
        # Ảnh kết quả: ComfyUI thường hiện ảnh ở sidebar hoặc trên node
        # Selector này tìm ảnh trong vùng Preview
        "RESULT_ELEMENT": "div.comfy-img-preview img", 
        
        "WAIT_TIME": 45
    },
    "google_veo": {
        # Đây là link Google Gemini (chứa Imagen 3/Veo)
        "URL": "https://gemini.google.com/app?android-min-version=301356232&ios-min-version=322.0&is_sa=1&campaign_id=gemini_overview_page&utm_source=gemini&utm_medium=web&utm_campaign=gemini_overview_page&pt=9008&mt=8&ct=gemini_overview_page&hl=vi-VN&_gl=1*dipony*_gcl_aw*R0NMLjE3NjgyODc2MzUuQ2owS0NRaUExSkxMQmhDREFSSXNBQVZmeTdoUVRTVHRiTExBZ1V2SUhaV1FUWmQ3TDJQT1BYVjZ4ZFpyYkl6MmxDeUt0Njd3SDZKd0ItZ2FBc1F0RUFMd193Y0I.*_gcl_dc*R0NMLjE3NjgyODc2MzUuQ2owS0NRaUExSkxMQmhDREFSSXNBQVZmeTdoUVRTVHRiTExBZ1V2SUhaV1FUWmQ3TDJQT1BYVjZ4ZFpyYkl6MmxDeUt0Njd3SDZKd0ItZ2FBc1F0RUFMd193Y0I.*_gcl_au*ODIyNTUwNzQ0LjE3NjgxOTIwMTI.*_ga*OTYzNzUwNDE1LjE3NjgxOTIwMTI.*_ga_WC57KJ50ZZ*czE3NjgyOTAyNzIkbzMkZzAkdDE3NjgyOTAyNzIkajYwJGwwJGgw", # <-- THAY LINK WEB CỦA BẠN VÀO ĐÂY
        
        # Selector cho khung chat Gemini
        "INPUT_BOX": "div[role='textbox'], div[contenteditable='true']",
        # Nút gửi
        "CREATE_BTN": "button[aria-label*='Send'], button[aria-label*='Gửi']",
        
        # 👇 SELECTOR MỚI (Dựa trên ảnh F12 của bạn)
        # Chỉ lấy thẻ img có class là "image" và "loaded"
        "RESULT_ELEMENT": "img.image.loaded", 
        
        "WAIT_TIME": 20
    },
}