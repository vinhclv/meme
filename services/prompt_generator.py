import traceback
import time
import re
import os
import random
import pyperclip
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI
from config.selectors import GEMINI_CONFIG
from utils.helpers import extract_json_from_text
import json

# 👇 Import cấu hình
from config.settings import PROFILE_DIR
# 👇 Đảm bảo bạn đã có hàm này trong utils (nếu tên file khác thì sửa lại import)
from utils.helpers import split_srt_blocks 

class VisualPromptGenerator:
    """
    Class chuyên trách nhiệm vụ: Đọc file SRT -> Gửi cho AI -> Lấy về JSON Prompt.
    Hỗ trợ: Google Gemini (Web Automation) và LM Studio (Local API).
    """

    def __init__(self, status_callback=None):
        """
        Khởi tạo Generator.
        :param status_callback: Hàm callback(msg) để gửi log ra giao diện Streamlit.
        """
        self.status_callback = status_callback
        self.driver = None # 👈 FIX 1: Giữ driver ở cấp Class để không bị ngắt kết nối

    def _log(self, msg):
        """Hàm nội bộ để in log ra cả Terminal và UI"""
        print(f"[PromptGen] {msg}")
        if self.status_callback:
            self.status_callback(msg)

    # --- CÁC HÀM HELPER (Private) ---

    def _focus_window(self):
        """
        👈 FIX 2: Hàm quan trọng để đưa cửa sổ Chrome lên trên cùng.
        Giúp tránh lỗi 'Browser window not found' khi paste.
        """
        try:
            if not self.driver or not self.driver.window_handles:
                return False
            
            # Lấy handle của tab hiện tại và tab đầu tiên
            current = self.driver.current_window_handle
            first = self.driver.window_handles[0]
            
            # Nếu đang không ở tab chính, chuyển về tab chính
            if current != first:
                self.driver.switch_to.window(first)
            
            return True
        except Exception:
            # Nếu lỗi focus, cứ lờ đi để code chạy tiếp (có thể người dùng đang thao tác khác)
            return False

    def _wait_for_gemini_finish(self, timeout=120):
        wait = WebDriverWait(self.driver, timeout)
        try:
            # 👇 SỬA: Lấy selector từ Config
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, GEMINI_CONFIG["SEND_BUTTON"])))
            time.sleep(2) 
            return True
        except Exception:
            return False

    def _count_valid_json_lines(self, text_content):
        if not text_content: return 0
        return len([l for l in text_content.strip().split('\n') if re.search(r'(\{.*\})', l)])

    # =========================================================================
    # CHỨC NĂNG 1: GENERATE QUA GEMINI WEB (SELENIUM)
    # =========================================================================
    def generate_via_gemini_web(self, input_srt_path, output_json_path, chunk_size=20, gemini_url=GEMINI_CONFIG["URL"]):
        
        # 1. Cấu hình Profile
        if not os.path.exists(PROFILE_DIR): os.makedirs(PROFILE_DIR)
        abs_profile_path = os.path.abspath(PROFILE_DIR)
        
        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir={abs_profile_path}')
        options.add_argument('--profile-directory=Profile 1') # Dùng Profile chính chủ
        
        options.add_argument('--no-first-run')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--start-maximized')

        self._log(f"🚀 Đang khởi động trình duyệt...")
        
        if self.driver:
            try: self.driver.quit()
            except: pass

        try:
            self.driver = uc.Chrome(options=options)
            
            self._log(f"🔗 Truy cập: {gemini_url}")
            self.driver.get(gemini_url)
            wait = WebDriverWait(self.driver, 30)

            # 2. Login Check
            try:
                self._log("🔐 Kiểm tra đăng nhập...")
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, GEMINI_CONFIG["INPUT_BOX"])))
            except:
                self._log("⚠️ Chưa đăng nhập! Vui lòng đăng nhập thủ công trong 60s.")
                time.sleep(60)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, GEMINI_CONFIG["INPUT_BOX"])))

            # 3. Chuẩn bị dữ liệu
            blocks = split_srt_blocks(input_srt_path)
            chunks = [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
            self._log(f"📄 Tổng {len(blocks)} đoạn sub. Chia thành {len(chunks)} lần gửi.")

            # 👇 BIẾN ĐỂ GOM DATA SẠCH
            final_data = [] 

            for index, chunk in enumerate(chunks):
                
                # Check trình duyệt sống
                try:
                    if not self.driver.window_handles: raise Exception("Cửa sổ đóng!")
                except:
                    self._log("❌ Mất kết nối trình duyệt!")
                    return False

                self._log(f"📤 Đang xử lý phần {index + 1}/{len(chunks)}...")

                # Copy Paste
                pyperclip.copy(chunk)
                self._focus_window()
                
                prompt_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, GEMINI_CONFIG["INPUT_BOX"])))
                prompt_box.click()
                time.sleep(0.5)
                prompt_box.send_keys(Keys.CONTROL, 'v')
                time.sleep(0.5)
                prompt_box.send_keys(Keys.ENTER)
                
                # Retry Loop
                retry_count = 0
                max_retries = 3
                chunk_success = False # Cờ đánh dấu thành công
                
                while retry_count < max_retries:
                    self._log(f"⏳ Đợi AI trả lời (Lần {retry_count})...")
                    
                    if self._wait_for_gemini_finish():
                        responses = self.driver.find_elements(By.CSS_SELECTOR, GEMINI_CONFIG["RESPONSE_TEXT"])
                        if responses:
                            latest_response = responses[-1].text
                            
                            # Lọc sạn lấy JSON
                            parsed_objects = extract_json_from_text(latest_response)
                            
                            current_valid = len(parsed_objects)
                            expected_count = len(chunk)
                            
                            self._log(f"📊 Lấy được {current_valid}/{expected_count} object.")

                            # 👇 SỬA 1: CHECK Đủ 100% 
                            if current_valid >= expected_count:
                                final_data.extend(parsed_objects)
                                chunk_success = True # Đánh dấu đã xong đẹp
                                break 
                            else:
                                retry_count += 1
                                if retry_count < max_retries:
                                    self._focus_window()
                                    prompt_box = self.driver.find_element(By.CSS_SELECTOR, GEMINI_CONFIG["INPUT_BOX"])
                                    
                                    # 👇 SỬA 2: PROMPT CHỬI CỤ THỂ HƠN
                                    missing_msg = f"Bạn mới trả về {current_valid} dòng, nhưng tôi gửi {expected_count} dòng. HÃY LÀM LẠI ĐỦ {expected_count} DÒNG JSON."
                                    prompt_box.send_keys(missing_msg)
                                    prompt_box.send_keys(Keys.ENTER)
                                    time.sleep(3)
                        else:
                            break
                    else:
                        break
                
                # 👇 SỬA 3: FALLBACK (Nếu retry mãi vẫn lỗi thì lấy tạm cái cuối cùng)
                if not chunk_success:
                    self._log(f"⚠️ Cảnh báo: Chunk {index+1} không đủ dòng sau {max_retries} lần thử. Chấp nhận lấy thiếu.")
                    # Nếu có dữ liệu (dù thiếu) thì vẫn gom vào, méo mó có hơn không
                    if 'parsed_objects' in locals() and parsed_objects:
                        final_data.extend(parsed_objects)

                time.sleep(random.uniform(2, 4))

            # 👇 LƯU FILE JSON CUỐI CÙNG (DATA ĐẸP 100%)
            self._log(f"💾 Đang lưu {len(final_data)} dòng dữ liệu sạch vào file...")
            # Đảm bảo lưu đúng format JSON
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            
            self._log("🎉 Hoàn tất! Data đã được làm sạch.")
            return True

        except Exception as e:
            self._log(f"❌ Lỗi Critical: {str(e)}")
            traceback.print_exc()
            return False
        finally:
            if self.driver: 
                self.driver.quit()
                self.driver = None
    # =========================================================================
    # CHỨC NĂNG 2: GENERATE QUA LOCAL API (LM STUDIO)
    # =========================================================================
    def generate_via_local_api(self, input_srt_path, output_txt_path, chunk_size, api_base, api_key, model_name, system_prompt):
        """
        Chạy API để lấy prompt từ LM Studio hoặc OpenAI Compatible Server.
        """
        try:
            client = OpenAI(base_url=api_base, api_key=api_key)
            
            self._log(f"🔗 Đang kết nối tới API: {api_base}...")
            try:
                client.models.list()
            except Exception as e:
                self._log(f"❌ Không thể kết nối tới Server. Lỗi: {e}")
                return False

            blocks = split_srt_blocks(input_srt_path)
            chunks = [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
            self._log(f"📄 Tổng {len(blocks)} blocks. Chia thành {len(chunks)} chunks.")

            if os.path.exists(output_txt_path): os.remove(output_txt_path)

            with open(output_txt_path, "a", encoding="utf-8") as f_out:
                for index, chunk in enumerate(chunks):
                    user_content = "\n\n".join(chunk)
                    self._log(f"📤 Đang gửi Chunk {index + 1}/{len(chunks)} qua API...")

                    try:
                        response = client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_content}
                            ],
                            temperature=0.7,
                            stream=False
                        )
                        
                        content = response.choices[0].message.content
                        valid_lines = self._count_valid_json_lines(content)
                        self._log(f"✅ Chunk {index + 1} xong. Nhận được {valid_lines} dòng JSON.")
                        
                        f_out.write(content + "\n\n")
                        f_out.flush() 

                    except Exception as e:
                        error_msg = str(e)
                        self._log(f"❌ Lỗi API ở Chunk {index + 1}: {error_msg}")
                        f_out.write(f"\n[ERROR CHUNK {index+1}]: {error_msg}\n\n")

            self._log("🎉 Hoàn tất xử lý qua API!")
            return True

        except Exception as e:
            self._log(f"❌ Lỗi khởi tạo Client: {str(e)}")
            return False