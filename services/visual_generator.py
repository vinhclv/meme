import os
import json
import traceback
import time
from utils.browser_setup import init_driver_from_profile
from services.visual_drivers import FlowDriver, GoogleVeoDriver

class VisualGenerator:
    def __init__(self, engine="flow", status_callback=None):
        self.engine = engine
        self.status_callback = status_callback
        self.driver = None
        self.worker = None
        self.profile_name = "Unknown"

    def _log(self, msg):
        tag = f"[{self.profile_name}]"
        print(f"[VisualGen]{tag} {msg}")
        if self.status_callback: 
            self.status_callback(f"{tag} {msg}")

    def generate_images(self, input_prompts_path, output_folder, profile_json_path):
        self.profile_name = os.path.splitext(os.path.basename(profile_json_path))[0]
        
        # 1. MỞ TRÌNH DUYỆT (Hiện màn hình)
        self.driver = init_driver_from_profile(
            profile_json_path, 
            log_callback=self._log, 
            download_dir=output_folder
        )
        
        if not self.driver: 
            self._log("❌ Không thể khởi tạo Driver.")
            return False

        try:
            # 2. CHỌN WORKER (Logic cũ của bạn)
            self._log(f"🔧 Engine đang chạy: {self.engine}")
            if self.engine == "flow":
                self.worker = FlowDriver(self.driver, self._log)
            elif self.engine == "google_veo":
                self.worker = GoogleVeoDriver(self.driver, self._log)
            else:
                self._log("❌ Engine không hợp lệ")
                return False

            # 3. ĐỌC PROMPTS
            with open(input_prompts_path, 'r', encoding='utf-8') as f:
                prompts_data = json.load(f)

            self._log(f"🖼️ Bắt đầu xử lý {len(prompts_data)} ảnh...")
            success_count = 0
            
            for i, item in enumerate(prompts_data):
                # Logic lấy prompt (đơn giản hóa để không bị lỗi Key)
                prompt = ""
                index = i + 1
                
                if isinstance(item, dict):
                    index = item.get("index", i+1)
                    # Thử lấy visual_prompt, nếu không có thì lấy prompt, text...
                    prompt = item.get("visual_prompt") or item.get("prompt") or item.get("text")
                else:
                    prompt = str(item)

                if not prompt: 
                    self._log(f"⚠️ Cảnh {index} không có nội dung -> Skip")
                    continue

                file_name = f"{index}.png" 
                full_output_path = os.path.join(output_folder, file_name)

                # Skip nếu đã có ảnh
                if os.path.exists(full_output_path):
                    self._log(f"⏩ Cảnh {index} đã xong -> Skip.")
                    success_count += 1
                    continue

                self._log(f"🎨 Đang vẽ cảnh {index}...")
                
                # GỌI HÀM CỦA BẠN ĐỂ VẼ
                is_done = self.worker.generate(prompt, full_output_path)
                
                if is_done:
                    success_count += 1
                else:
                    self._log(f"❌ Thất bại cảnh {index}")
                
                time.sleep(random.randint(2,3))

            self._log(f"🏁 Hoàn tất: {success_count}/{len(prompts_data)} ảnh.")
            return True

        except Exception as e:
            self._log(f"❌ Lỗi Critical: {e}")
            traceback.print_exc()
            return False
        finally:
            # Tắt trình duyệt khi xong việc
            if self.driver:
                try: self.driver.quit()
                except: pass
                self.driver = None