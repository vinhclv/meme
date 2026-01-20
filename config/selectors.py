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
    "RESPONSE_TEXT": "model-response",
    "WAIT_TIME": 120
}

VISUAL_CONFIGS = {
    "flow": {
        "URL": "https://labs.google/fx/vi/tools/flow",
        # Các selector bên dưới class đã tự xử lý bằng XPath rồi, 
        # nhưng cứ để RESULT_ELEMENT để quét ảnh/video
        "RESULT_ELEMENT": "img", 
        "WAIT_TIME": 120
    },
    "google_veo": {
        # Đây là link Google Gemini (chứa Imagen 3/Veo)
        "URL": "https://gemini.google.com/app?hl=vi", # <-- THAY LINK WEB CỦA BẠN VÀO ĐÂY
        
        # Selector cho khung chat Gemini
        "INPUT_BOX": "div[role='textbox'], div[contenteditable='true']",
        # Nút gửi
        "CREATE_BTN": "button[aria-label*='Send'], button[aria-label*='Gửi']",
        
        # 👇 SELECTOR MỚI (Dựa trên ảnh F12 của bạn)
        # Chỉ lấy thẻ img có class là "image" và "loaded"
        "RESULT_ELEMENT": "img.image.loaded", 
        
        "WAIT_TIME": 120
    },
}