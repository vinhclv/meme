# config/selectors.py

# Cấu hình các Element của Gemini
GEMINI_CONFIG = {
    # Ô nhập liệu (nơi paste prompt)
    "INPUT_BOX": "div[role='textbox'], p[data-placeholder='Enter a prompt here']",
    
    # Nút gửi (hoặc trạng thái icon khi đang gửi)
    "SEND_BUTTON": "button[aria-label*='Send'], button[aria-label*='Gửi'], span[data-testid='send-button']",
    
    # Câu trả lời của AI
    "RESPONSE_TEXT": ".model-response-text, .message-content, app-conversation-message",
    
    # URL gốc (nếu Google đổi domain)
    "URL": "https://gemini.google.com/gem/1uxRmWBKYok16CVaaQWM93NtbAXNhq78u?usp=sharing"
}

# Cấu hình ChatGPT (Nếu sau này bạn muốn mở rộng)
CHATGPT_CONFIG = {
    "INPUT_BOX": "#prompt-textarea",
    "SEND_BUTTON": "button[data-testid='send-button']",
}