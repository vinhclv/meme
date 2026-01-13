# views/__init__.py

# Import các hàm render từ từng file con
from .step1_transcribe import render as render_step1
from .step2_prompts import render as render_step2
from .step3_visuals import render as render_step3
from .step4_merge import render as render_step4

# (Tùy chọn) Có thể tạo list để dễ quản lý loop nếu muốn
__all__ = ['render_step1', 'render_step2', 'render_step3', 'render_step4']