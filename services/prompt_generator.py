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
from selenium.common.exceptions import WebDriverException
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
            time.sleep(4) 
            return True
        except Exception:
            return False

    def _count_valid_json_lines(self, text_content):
        if not text_content: return 0
        return len([l for l in text_content.strip().split('\n') if re.search(r'(\{.*\})', l)])

    # 👇 HÀM KHỞI TẠO DRIVER RIÊNG (ĐỂ DỄ RESET)
    def _init_driver(self):
        if not os.path.exists(PROFILE_DIR): os.makedirs(PROFILE_DIR)
        abs_profile_path = os.path.abspath(PROFILE_DIR)
        
        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir={abs_profile_path}')
        options.add_argument('--profile-directory=Profile 1')
        options.add_argument('--no-first-run')
        options.add_argument('--start-maximized')
        
        # 👇 THÊM CÁC DÒNG NÀY ĐỂ TRÁNH CRASH (QUAN TRỌNG)
        options.add_argument('--disable-gpu') # Tắt GPU để tránh xung đột đồ họa
        options.add_argument('--no-sandbox')  # Giảm lỗi renderer crash
        options.add_argument('--disable-dev-shm-usage') # Tránh lỗi bộ nhớ share
        options.page_load_strategy = 'normal'

        try:
            driver = uc.Chrome(options=options)
            return driver
        except Exception as e:
            self._log(f"❌ Không thể mở Chrome: {e}")
            return None
    # =========================================================================
    # CHỨC NĂNG 1: GENERATE QUA GEMINI WEB (FULL OPTIMIZED: JS INJECTION + CONTEXT)
    # =========================================================================
    def generate_via_gemini_web(self, input_srt_path, output_json_path, context_summary="", chunk_size=15, gemini_url=GEMINI_CONFIG["URL"]):
        
        self._log(f"🚀 Khởi động Chrome (Chế độ An toàn)...")
        
        # Đóng driver cũ nếu còn treo
        if self.driver:
            try: self.driver.quit()
            except: pass
        
        # Khởi tạo driver mới
        self.driver = self._init_driver()
        if not self.driver: return False

        wait = WebDriverWait(self.driver, 40)
        
        try:
            # 2. CHUẨN BỊ DATA
            blocks = split_srt_blocks(input_srt_path)
            chunks = [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
            self._log(f"📄 Tổng {len(blocks)} dòng. Chia thành {len(chunks)} chunks (Size={chunk_size}).")
            
            final_data = []

            # 3. PROMPT HỆ THỐNG
            BASE_SYSTEM_PROMPT = f"""
            You are an expert Visual Prompt Creator for AI Video generation.
            Task: Read the subtitle (SRT) lines below and generate a visual illustration description (Visual Prompt) for each line.
            MANDATORY REQUIREMENTS:
            1. Return strictly pure JSON format (Array of Objects).
            2. Each object must follow this structure: {{"index": "keep the original index from input", "text": "original srt content", "visual_prompt": "detailed, artistic image description in English"}}
            3. NO explanations, NO Markdown code blocks, return ONLY the raw JSON string.
            4. ABSOLUTELY DO NOT invent new indices; you must use the exact indices provided in the text.
            DATA TO PROCESS:
            """

            # =================================================
            # VÒNG LẶP CHUNK
            # =================================================
            for index, chunk in enumerate(chunks):
                self._log(f"🔄 Đang xử lý Chunk {index + 1}/{len(chunks)}...")
                
                chunk_success = False
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        # KIỂM TRA SỰ SỐNG CỦA DRIVER TRƯỚC KHI LÀM GÌ
                        try:
                            # Thử gọi một lệnh nhẹ để xem Chrome còn sống không
                            _ = self.driver.window_handles
                        except Exception:
                            raise WebDriverException("Chrome died")

                        # [BƯỚC 1] F5 TRANG WEB
                        self.driver.get(gemini_url)
                        
                        # [BƯỚC 2] ĐỢI Ô NHẬP LIỆU
                        time.sleep(3) # Tăng delay để ổn định
                        prompt_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, GEMINI_CONFIG["INPUT_BOX"])))
                        
                        # [BƯỚC 3] JS INJECTION
                        chunk_text = "\n".join(chunk)
                        full_message = f"{BASE_SYSTEM_PROMPT}\n\n{chunk_text}"
                        
                        self._log(f"📝 Đang gửi dữ liệu (JS Injection)...")
                        prompt_box.click()
                        time.sleep(1)

                        self.driver.execute_script(
                            """
                            var elm = arguments[0];
                            elm.focus();
                            document.execCommand('insertText', false, arguments[1]);
                            elm.dispatchEvent(new Event('input', { bubbles: true }));
                            """, 
                            prompt_box, 
                            full_message
                        )
                        time.sleep(1.5)

                        # [BƯỚC 4] GỬI
                        try:
                            send_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, GEMINI_CONFIG["SEND_BUTTON"])))
                            send_btn.click()
                        except:
                            self._log("⚠️ Không thấy nút Gửi, dùng Enter...")
                            prompt_box.send_keys(Keys.ENTER)
                        
                        self._log(f"⏳ Đang đợi AI trả lời (Lần thử {retry_count + 1})...")
                        
                        # [BƯỚC 5] LẤY KẾT QUẢ
                        if self._wait_for_gemini_finish(timeout=90):
                            responses = self.driver.find_elements(By.CSS_SELECTOR, GEMINI_CONFIG["RESPONSE_TEXT"])
                            if responses:
                                latest_response = responses[-1].text
                                parsed_objects = extract_json_from_text(latest_response)
                                
                                expected_count = len(chunk)
                                current_valid = len(parsed_objects)

                                if current_valid >= expected_count:
                                    self._log(f"✅ Chunk {index + 1} thành công: {current_valid}/{expected_count} items.")
                                    final_data.extend(parsed_objects)
                                    chunk_success = True
                                    break 
                                else:
                                    # Logic đợi thêm nếu AI gõ chưa xong (tránh lỗi 0/15)
                                    if current_valid == 0:
                                        self._log("⚠️ Chưa có JSON, đợi thêm 5s...")
                                        time.sleep(5)
                                        # Lấy lại lần nữa
                                        responses = self.driver.find_elements(By.CSS_SELECTOR, GEMINI_CONFIG["RESPONSE_TEXT"])
                                        latest_response = responses[-1].text
                                        parsed_objects = extract_json_from_text(latest_response)
                                        current_valid = len(parsed_objects)
                                        if current_valid >= expected_count:
                                            self._log(f"✅ Đã lấy được đủ JSON: {current_valid}.")
                                            final_data.extend(parsed_objects)
                                            chunk_success = True
                                            break

                                    self._log(f"⚠️ Thiếu data ({current_valid}/{expected_count}). Thử lại...")
                            else:
                                self._log("⚠️ Không tìm thấy phản hồi.")
                        else:
                            self._log("⚠️ Timeout.")

                    except (WebDriverException, ConnectionError) as e:
                        # 👇 CƠ CHẾ HỒI SINH TRÌNH DUYỆT TẠI ĐÂY
                        self._log(f"🔥 CẢNH BÁO: Trình duyệt bị Sập/Ngắt kết nối! ({str(e)[:50]}...)")
                        self._log("🚑 Đang HỒI SINH trình duyệt mới...")
                        
                        try:
                            self.driver.quit()
                        except: pass
                        
                        time.sleep(2)
                        self.driver = self._init_driver() # Mở lại cái mới
                        wait = WebDriverWait(self.driver, 40)
                        
                        if not self.driver:
                            self._log("❌ Không thể hồi sinh driver. Dừng tool.")
                            return False
                        
                        self._log("✅ Đã hồi sinh xong. Sẽ thử lại chunk này ngay.")
                        # Không tăng retry_count để nó thử lại chunk này với trình duyệt mới

                    except Exception as e:
                         self._log(f"⚠️ Lỗi logic thường: {e}")
                         retry_count += 1
                         time.sleep(2)
                    
                    if not chunk_success and isinstance(self.driver, type(None)) == False:
                        retry_count += 1
                        time.sleep(3)

                if not chunk_success:
                    self._log(f"❌ Thất bại Chunk {index + 1}. Dữ liệu phần này sẽ bị thiếu.")
                
                time.sleep(2)

            # 4. LƯU FILE
            self._log(f"💾 Đang lưu {len(final_data)} dòng dữ liệu vào file...")
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            
            self._log(f"🎉 Hoàn tất! File lưu tại: {output_json_path}")
            return True

        except Exception as e:
            self._log(f"❌ Lỗi Critical: {str(e)}")
            traceback.print_exc()
            return False
        finally:
            if self.driver:
                try: self.driver.quit()
                except: pass
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