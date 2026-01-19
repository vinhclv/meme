import time
import re
import os
import json
import threading
import traceback
import zipfile
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# Import cấu hình
from config.selectors import GEMINI_CONFIG
from config.settings import ROOT_PATH 
from utils.helpers import extract_json_from_text, split_srt_blocks

# Khóa an toàn khi khởi tạo driver đa luồng
DRIVER_INIT_LOCK = threading.Lock()

class VisualPromptGenerator:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.driver = None 
        self.current_profile_json = None 
        # 👇 Thêm biến này để lưu tên profile cho log dễ nhìn
        self.profile_name = "Unknown" 

    def _log(self, msg):
        # 👇 Hiển thị tên Profile thay vì [PromptGen] chung chung
        tag = f"[{self.profile_name}]"
        print(f"{tag} {msg}")
        if self.status_callback:
            self.status_callback(f"{tag} {msg}")

    # 1. TẠO EXTENSION LOGIN PROXY
    def _create_proxy_auth_extension(self, host, port, user, password, plugin_dir):
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 3,
            "name": "Chrome Proxy Auth V3",
            "permissions": ["proxy", "webRequest", "webRequestBlocking"],
            "host_permissions": ["<all_urls>"],
            "background": {"service_worker": "background.js"}
        }
        """
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{ scheme: "http", host: "{host}", port: parseInt({port}) }},
                bypassList: ["localhost"]
            }}
        }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        function callbackFn(details) {{
            return {{ authCredentials: {{ username: "{user}", password: "{password}" }} }};
        }}
        chrome.webRequest.onAuthRequired.addListener(
            callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']
        );
        """
        if not os.path.exists(plugin_dir): os.makedirs(plugin_dir)
        with open(os.path.join(plugin_dir, "manifest.json"), "w") as f: f.write(manifest_json)
        with open(os.path.join(plugin_dir, "background.js"), "w") as f: f.write(background_js)

    # 2. KHỞI TẠO DRIVER TỪ FILE JSON
    def _init_driver_from_profile(self, json_profile_path):
        try:
            with open(json_profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self._log(f"❌ Lỗi đọc file JSON profile: {e}")
            return None

        # --- XỬ LÝ ĐƯỜNG DẪN ---
        json_dir = os.path.dirname(json_profile_path)
        profile_zip_path = data.get("Path")
        folder_name = os.path.splitext(os.path.basename(json_profile_path))[0]
        
        # Cập nhật tên profile để log ngay lập tức
        self.profile_name = folder_name
        
        working_profile_dir = os.path.join(json_dir, folder_name)

        # --- LOGIC GIẢI NÉN ---
        if not os.path.exists(working_profile_dir):
            self._log(f"📦 Đang giải nén Profile...")
            full_zip_path = profile_zip_path
            if not os.path.isabs(full_zip_path):
                full_zip_path = os.path.join(ROOT_PATH, profile_zip_path)
            
            if os.path.exists(full_zip_path):
                try:
                    with DRIVER_INIT_LOCK:
                        if not os.path.exists(working_profile_dir):
                            with zipfile.ZipFile(full_zip_path, 'r') as zip_ref:
                                zip_ref.extractall(working_profile_dir)
                            self._log(f"✅ Giải nén xong.")
                except Exception as e:
                    self._log(f"❌ Lỗi giải nén: {e}")
                    return None
            else:
                self._log(f"⚠️ Không tìm thấy Zip. Tạo profile trắng.")
                os.makedirs(working_profile_dir, exist_ok=True)

        self._log(f"🚀 Đang mở Chrome...")

        # --- CẤU HÌNH CHROME ---
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={working_profile_dir}")
        options.add_argument(f"--profile-directory=Default")
        
        try:
            ua = data["Data"]["navigator"]["userAgent"]
            options.add_argument(f"--user-agent={ua}")
        except: pass

        try:
            proxy_data = data.get("Data", {}).get("proxy", {})
            host = proxy_data.get("host")
            port = proxy_data.get("port")
            user = proxy_data.get("username")
            password = proxy_data.get("password")

            if host and port:
                if user and password:
                    plugin_path = os.path.join(working_profile_dir, "proxy_auth_plugin")
                    self._create_proxy_auth_extension(host, port, user, password, plugin_path)
                    options.add_argument(f"--load-extension={plugin_path}")
                else:
                    options.add_argument(f"--proxy-server=http://{host}:{port}")
        except: pass

        options.add_argument('--no-first-run')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-popup-blocking')
        options.page_load_strategy = 'eager'

        ORBITA_PATH = r"C:\Users\CLV_SEO\Documents\orbita-browser-141\chrome.exe"
        DRIVER_PATH = r"C:\Users\CLV_SEO\Documents\orbita-browser-141\chromedriver.exe"

        with DRIVER_INIT_LOCK:
            try:
                driver = uc.Chrome(
                    options=options,
                    browser_executable_path=ORBITA_PATH,
                    driver_executable_path=DRIVER_PATH,
                    version_main=131,
                    use_subprocess=True
                )
                return driver
            except Exception as e:
                self._log(f"❌ Lỗi khởi tạo Chrome: {e}")
                return None

    def _wait_for_gemini_finish(self, timeout=120):
        if not self.driver: return False
        wait = WebDriverWait(self.driver, timeout)
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, GEMINI_CONFIG["SEND_BUTTON"])))
            time.sleep(2) 
            return True
        except Exception:
            return False

    # 3. HÀM CHÍNH
    def generate_via_gemini_web(self, input_srt_path, output_json_path, profile_json_path, chunk_size=15, gemini_url=GEMINI_CONFIG["URL"]):
        
        # 👇 Cập nhật tên Profile ngay từ đầu để log được chuẩn
        self.profile_name = os.path.splitext(os.path.basename(profile_json_path))[0]
        self.current_profile_json = profile_json_path
        
        self._log(f"🎬 Bắt đầu xử lý file: {os.path.basename(input_srt_path)}")

        self.driver = self._init_driver_from_profile(profile_json_path)
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
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        # KIỂM TRA SỰ SỐNG CỦA DRIVER
                        try:
                            _ = self.driver.window_handles
                        except Exception:
                            raise WebDriverException("Chrome died")

                        self.driver.get(gemini_url)
                        time.sleep(2)
                        
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
                        time.sleep(1.5)

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
                        
                        time.sleep(2)
                        self.driver = self._init_driver_from_profile(self.current_profile_json)
                        
                        if not self.driver:
                            self._log("❌ Hồi sinh thất bại.")
                            return False
                        
                        wait = WebDriverWait(self.driver, 40)
                        self._log("✅ Hồi sinh xong. Re-run chunk.")
                        continue 

                    except Exception as e:
                         self._log(f"⚠️ Lỗi logic: {e}")
                         retry_count += 1
                         time.sleep(2)
                    
                    if not chunk_success and self.driver:
                        retry_count += 1
                        time.sleep(2)

                if not chunk_success:
                    self._log(f"❌ Thất bại Chunk {index + 1}. Bỏ qua.")
                
                time.sleep(2)

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