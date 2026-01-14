import os
import undetected_chromedriver as uc
from selenium import webdriver # Vẫn cần import cái này để dùng DesiredCapabilities nếu cần
from config.settings import PROFILE_DIR
from services.visual_drivers import BananaProDriver, FlowDriver, GoogleVeoDriver

class VisualGenerator:
    def __init__(self, engine="banapro", status_callback=None):
        self.engine = engine
        self.status_callback = status_callback
        self.driver = None
        self.worker = None

    def _log(self, msg):
        print(f"[VisualGen] {msg}")
        if self.status_callback: self.status_callback(msg)

    def start_browser(self):
        """Luôn luôn mở Chrome vì user yêu cầu dùng Selenium"""
        
        # 1. Dùng Options của Undetected Chromedriver (QUAN TRỌNG)
        options = uc.ChromeOptions()
        
        # 2. Cấu hình Profile (Để giữ trạng thái đăng nhập)
        # Lưu ý: PROFILE_DIR phải là đường dẫn tuyệt đối
        options.add_argument(f'--user-data-dir={os.path.abspath(PROFILE_DIR)}')
        options.add_argument('--profile-directory=Profile 1') # Hoặc 'Default' tùy máy bạn
        options.add_argument('--no-first-run')
        options.add_argument('--password-store=basic') # Giúp đỡ bị hỏi password keyring trên Linux/Mac



        try:
            self._log(f"🚀 Mở Chrome để chạy Selenium ({self.engine})...")
            
            # 4. Khởi tạo Driver bằng Undetected Chromedriver
            # Lưu ý: headless=False để debug, sau này chạy ngầm thì sửa thành True
            self.driver = uc.Chrome(options=options, headless=False, use_subprocess=False)

            # 👇 CHỌN DRIVER TƯƠNG ỨNG
            if self.engine == "banapro":
                self.worker = BananaProDriver(self.driver, self._log)
            elif self.engine == "flow":
                self.worker = FlowDriver(self.driver, self._log)
            elif self.engine == "google_veo":
                self.worker = GoogleVeoDriver(self.driver, self._log)
            else:
                self._log("❌ Engine không hợp lệ!")
                return False
                
            return True

        except Exception as e:
            self._log(f"❌ Lỗi mở Chrome: {e}")
            # Nếu lỗi, thử in ra chi tiết để debug
            import traceback
            traceback.print_exc()
            return False

    def close_browser(self):
        if self.driver:
            self.driver.quit()

    def generate_image(self, prompt, output_path):
        if not self.worker:
            self._log("⚠️ Worker chưa sẵn sàng!")
            return False
        return self.worker.generate(prompt, output_path)