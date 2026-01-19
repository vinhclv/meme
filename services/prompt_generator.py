import time
import os
import json
import traceback

# 👇 Giữ lại các thư viện Selenium để thao tác trên trang web
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# Import cấu hình
from config.selectors import GEMINI_CONFIG
from utils.helpers import extract_json_from_text, split_srt_blocks

# 👇 IMPORT HÀM SETUP TRÌNH DUYỆT TỪ MODULE MỚI
from utils.browser_setup import init_driver_from_profile

class VisualPromptGenerator:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.driver = None 
        self.current_profile_json = None 
        self.profile_name = "Unknown" 

    def _log(self, msg):
        tag = f"[{self.profile_name}]"
        print(f"{tag} {msg}")
        if self.status_callback:
            self.status_callback(f"{tag} {msg}")

    def _wait_for_gemini_finish(self, timeout=120):
        if not self.driver: return False
        wait = WebDriverWait(self.driver, timeout)
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, GEMINI_CONFIG["SEND_BUTTON"])))
            time.sleep(random.randint(2,4)) 
            return True
        except Exception:
            return False

    # =========================================================================
    # HÀM CHÍNH: GENERATE PROMPT
    # =========================================================================
    def generate_via_gemini_web(self, input_srt_path, output_json_path, profile_json_path, chunk_size=15, gemini_url=GEMINI_CONFIG["URL"]):
        
        # Cập nhật tên profile để log
        self.profile_name = os.path.splitext(os.path.basename(profile_json_path))[0]
        self.current_profile_json = profile_json_path
        
        self._log(f"🎬 Bắt đầu xử lý file: {os.path.basename(input_srt_path)}")

        # 👇 [THAY ĐỔI 1] GỌI HÀM TỪ utils.browser_setup
        # Truyền self._log vào để nó in log ra UI của class này
        self.driver = init_driver_from_profile(profile_json_path, log_callback=self._log)
        
        if not self.driver: return False

        wait = WebDriverWait(self.driver, 40)
        
        try:
            blocks = split_srt_blocks(input_srt_path)
            chunks = [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
            final_data = []

            BASE_SYSTEM_PROMPT = f"""
            You are an expert Visual Prompt Creator for AI Video generation.
            Task: Read the subtitle (SRT) lines below and generate a visual illustration description (Visual Prompt) for each line.
            MANDATORY REQUIREMENTS:
            1. Return strictly pure JSON format (Array of Objects).
            2. Each object must follow this structure: {{"index": "keep the original index from input", "text": "original srt content", "visual_prompt": "detailed, artistic image description in English"}}
            3. NO explanations, NO Markdown code blocks, return ONLY the raw JSON string.
            DATA TO PROCESS:
            """

            for index, chunk in enumerate(chunks):
                self._log(f"🔄 Chunk {index + 1}/{len(chunks)}...")
                
                chunk_success = False
                retry_count = 0
                max_retries = 7

                while retry_count < max_retries:
                    try:
                        # Kiểm tra driver sống hay chết
                        try:
                            _ = self.driver.window_handles
                        except Exception:
                            raise WebDriverException("Chrome died")

                        self.driver.get(gemini_url)
                        time.sleep(random.randint(2,4))
                        
                        prompt_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, GEMINI_CONFIG["INPUT_BOX"])))
                        
                        chunk_text = "\n".join(chunk)
                        full_message = f"{BASE_SYSTEM_PROMPT}\n\n{chunk_text}"
                        
                        # JS Injection
                        self.driver.execute_script(
                            """
                            var elm = arguments[0];
                            elm.focus();
                            document.execCommand('insertText', false, arguments[1]);
                            elm.dispatchEvent(new Event('input', { bubbles: true }));
                            """, prompt_box, full_message
                        )
                        time.sleep(random.randint(2,4))

                        try:
                            send_btn = self.driver.find_element(By.CSS_SELECTOR, GEMINI_CONFIG["SEND_BUTTON"])
                            send_btn.click()
                        except:
                            prompt_box.send_keys(Keys.ENTER)
                        
                        self._log(f"⏳ Đợi AI (Thử lần {retry_count + 1})...")
                        
                        if self._wait_for_gemini_finish(timeout=90):
                            responses = self.driver.find_elements(By.CSS_SELECTOR, GEMINI_CONFIG["RESPONSE_TEXT"])
                            if responses:
                                latest_response = responses[-1].text
                                parsed_objects = extract_json_from_text(latest_response)
                                
                                if len(parsed_objects) > 0:
                                    self._log(f"✅ Chunk {index + 1} OK: {len(parsed_objects)} items.")
                                    final_data.extend(parsed_objects)
                                    chunk_success = True
                                    break 
                                else:
                                    self._log("⚠️ AI trả về rỗng. Thử lại...")
                            else:
                                self._log("⚠️ Không thấy phản hồi.")
                        else:
                            self._log("⚠️ Timeout.")

                    except (WebDriverException, ConnectionError) as e:
                        self._log(f"🔥 CẢNH BÁO: Chrome Sập! ({str(e)[:50]}...)")
                        self._log("🚑 Đang HỒI SINH trình duyệt...")
                        
                        try:
                            self.driver.quit()
                        except: pass
                        
                        time.sleep(random.randint(2,3))
                        
                        # 👇 [THAY ĐỔI 2] GỌI HÀM TỪ utils.browser_setup ĐỂ HỒI SINH
                        self.driver = init_driver_from_profile(self.current_profile_json, log_callback=self._log)
                        
                        if not self.driver:
                            self._log("❌ Hồi sinh thất bại.")
                            return False
                        
                        wait = WebDriverWait(self.driver, 40)
                        self._log("✅ Hồi sinh xong. Re-run chunk.")
                        continue 

                    except Exception as e:
                         self._log(f"⚠️ Lỗi logic: {e}")
                         retry_count += 1
                         time.sleep(random.randint(2,3))
                    
                    if not chunk_success and self.driver:
                        retry_count += 1
                        time.sleep(random.randint(2,3))

                if not chunk_success:
                    self._log(f"❌ Thất bại Chunk {index + 1}. Bỏ qua.")
                
                time.sleep(random.randint(2,3))

            self._log(f"💾 Đang lưu file...")
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            
            self._log(f"🎉 Hoàn tất!")
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