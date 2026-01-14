import time
import requests
import base64
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.selectors import VISUAL_CONFIGS
import shutil
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException

# ==========================================
# CLASS CHA (BASE DRIVER)
# ==========================================
class BaseVisualDriver:
    def __init__(self, driver, log_callback=None):
        self.driver = driver
        self.log = log_callback if log_callback else print

    def generate(self, prompt, output_path):
        raise NotImplementedError

    def _download(self, url, save_path):
        """Hàm tải ảnh hỗ trợ cả URL thường và Base64"""
        try:
            # Nếu ảnh là Base64 (Thường gặp ở Web UI)
            if "data:image" in url:
                header, encoded = url.split(",", 1)
                data = base64.b64decode(encoded)
                with open(save_path, "wb") as f: f.write(data)
            
            # Nếu ảnh là Link http
            else:
                response = requests.get(url, stream=True)
                if response.status_code == 200:
                    with open(save_path, "wb") as f:
                        for chunk in response.iter_content(1024): f.write(chunk)
            
            self.log(f"✅ Đã lưu ảnh: {os.path.basename(save_path)}")
            return True
        except Exception as e:
            self.log(f"❌ Lỗi tải ảnh: {e}")
            return False

# ==========================================
# DRIVER 1: BANANA PRO (WEB UI)
# ==========================================
class BananaProDriver(BaseVisualDriver):
    def generate(self, prompt, output_path):
        cfg = VISUAL_CONFIGS["banapro"]
        wait = WebDriverWait(self.driver, 60)

        prompt = prompt.replace("\n", " ")
        try:
            self.driver.get(cfg["URL"])
            
            # 1. Nhập Prompt
            self.log(f"🍌 [Banana Web] Nhập prompt: {prompt[:30]}...")
            print(prompt)
            try:
                inp = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg["INPUT_BOX"])))
                # Xóa kỹ bằng JS để tránh sót chữ
                self.driver.execute_script("arguments[0].value = '';", inp)
                inp.send_keys(prompt)
            except Exception as e:
                self.log(f"❌ Không tìm thấy ô nhập liệu: {cfg['INPUT_BOX']}")
                return False

            time.sleep(1)
            
            # 2. Bấm nút Generate
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, cfg["CREATE_BTN"])
                btn.click()
            except:
                self.log("⚠️ Không click được nút, thử Enter...")
                inp.send_keys(Keys.ENTER)
            
            self.log(f"⏳ Đang render trên Banana ({cfg['WAIT_TIME']}s)...")
            
            # 3. Đợi ảnh xuất hiện
            # Logic: Đợi cho đến khi thẻ IMG xuất hiện và src của nó thay đổi hoặc load xong
            time.sleep(cfg["WAIT_TIME"]) 
            
            img_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, cfg["RESULT_ELEMENT"])))
            img_url = img_el.get_attribute("src")
            
            if not img_url:
                self.log("❌ Tìm thấy thẻ ảnh nhưng không có link (src).")
                return False

            return self._download(img_url, output_path)

        except Exception as e:
            self.log(f"❌ Lỗi BananaPro Driver: {e}")
            return False
# ==========================================
# DRIVER 2: FLOW (WEB UI)
# ==========================================
class FlowDriver(BaseVisualDriver):
    def generate(self, prompt, output_path):
        cfg = VISUAL_CONFIGS["flow"]
        wait = WebDriverWait(self.driver, 60)

        # 1. [QUAN TRỌNG] Xử lý đầu vào nếu là Dict (Tránh lỗi unhashable slice)
        if isinstance(prompt, dict):
            prompt = prompt.get("visual_prompt", prompt.get("prompt", str(prompt)))
        prompt = str(prompt)

        try:
            # 2. Vào trang
            # ComfyUI là Single Page App, không cần load lại nếu đang ở đó
            if cfg["URL"] not in self.driver.current_url:
                self.driver.get(cfg["URL"])
                time.sleep(3)

            # --- KỸ THUẬT SNAPSHOT ẢNH CŨ ---
            # Đếm số lượng ảnh đang hiển thị để biết khi nào có cái mới
            existing_imgs = self.driver.find_elements(By.CSS_SELECTOR, cfg["RESULT_ELEMENT"])
            count_before = len(existing_imgs)
            self.log(f"🌊 [Flow] Ảnh cũ hiện có: {count_before}")

            # 3. Nhập Prompt
            self.log(f"🌊 [Flow] Nhập prompt: {prompt[:30]}...")
            
            # ComfyUI có thể có nhiều ô input (Positive/Negative). 
            # Code này mặc định lấy ô ĐẦU TIÊN (Positive).
            inputs = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, cfg["INPUT_BOX"])))
            
            if not inputs:
                self.log("❌ Không tìm thấy ô nhập liệu ComfyUI!")
                return False
                
            input_box = inputs[0] # Lấy ô đầu tiên
            
            # Xóa text cũ (ComfyUI đôi khi dùng JS để bind dữ liệu, nên cần xóa kỹ)
            input_box.clear()
            self.driver.execute_script("arguments[0].value = '';", input_box)
            input_box.send_keys(prompt)
            time.sleep(0.5)

            # 4. Bấm nút Queue Prompt
            self.log("🖱️ Click Queue Prompt...")
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, cfg["CREATE_BTN"])
                btn.click()
            except:
                self.log("⚠️ Không click được nút Queue, thử Enter...")
                # ComfyUI thường dùng Ctrl+Enter để chạy
                input_box.send_keys(Keys.CONTROL, Keys.ENTER)

            self.log(f"⏳ Đang render Flow...")

            # 5. VÒNG LẶP CHỜ ẢNH MỚI
            start_time = time.time()
            target_src = None
            
            while time.time() - start_time < cfg["WAIT_TIME"]:
                # Tìm lại danh sách ảnh
                current_imgs = self.driver.find_elements(By.CSS_SELECTOR, cfg["RESULT_ELEMENT"])
                
                # Nếu số lượng tăng lên -> Có hàng mới
                if len(current_imgs) > count_before:
                    new_img = current_imgs[-1]
                    src = new_img.get_attribute("src")
                    
                    if src:
                        target_src = src
                        self.log(f"🎉 Flow trả về ảnh: {src[:30]}...")
                        # ComfyUI load ảnh local đôi khi cần chút thời gian để render xong hẳn
                        time.sleep(1) 
                        break
                
                time.sleep(2)

            if not target_src:
                self.log("❌ Timeout: Flow chạy xong nhưng không thấy ảnh mới (hoặc chưa chạy xong).")
                # Fallback: Chụp màn hình
                self.driver.save_screenshot(output_path)
                return True # Vẫn coi là xong để chạy tiếp

            # 6. Tải về
            return self._download(target_src, output_path)

        except Exception as e:
            self.log(f"❌ Lỗi FlowDriver: {e}")
            return False

# ==========================================
# DRIVER: GOOGLE GEMINI CHAT (FIX TẢI ẢNH)
# ==========================================
class GoogleVeoDriver(BaseVisualDriver):
    def generate(self, prompt, output_path):
        cfg = VISUAL_CONFIGS["google_veo"]
        wait = WebDriverWait(self.driver, 60)

        # Xử lý Prompt
        if isinstance(prompt, dict):
            prompt = prompt.get("visual_prompt", prompt.get("prompt", str(prompt)))
        prompt = str(prompt)

        try:
            # 1. Vào trang (Chỉ load lại nếu chưa ở đúng trang)
            if "gemini.google.com" not in self.driver.current_url:
                self.driver.get(cfg["URL"])
                time.sleep(3)

            # --- ĐẾM SỐ CONTAINER ẢNH CŨ ---
            # Để biết khi nào ảnh mới xuất hiện
            try:
                existing_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.attachment-container")
                count_before = len(existing_containers)
            except:
                count_before = 0
            
            self.log(f"📸 Số ảnh cũ: {count_before}")

            # 2. Nhập Prompt
            try:
                input_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg["INPUT_BOX"])))
                input_box.click()
                full_prompt = f"Generate an image: {prompt}"
                
                # Dùng JS nhập liệu cho nhanh và chuẩn
                self.driver.execute_script(
                    """
                    var elm = arguments[0]; elm.focus();
                    document.execCommand('insertText', false, arguments[1]);
                    elm.dispatchEvent(new Event('input', { bubbles: true }));
                    """, input_box, full_prompt
                )
                time.sleep(1)
                
                # Thử click nút gửi, fallback là phím Enter
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, cfg["CREATE_BTN"])
                    btn.click()
                except:
                    input_box.send_keys(Keys.ENTER)
            except Exception as e:
                self.log(f"❌ Lỗi nhập prompt: {e}")
                return False

            self.log(f"⏳ Đang chờ ảnh mới...")

            # 3. VÒNG LẶP CHỜ VÀ QUÉT DOM (THÔNG MINH)
            start_time = time.time()
            
            # Tăng timeout lên 120s vì đôi khi server Google lag
            while time.time() - start_time < 120:
                try:
                    # Tìm container
                    current_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.attachment-container")
                    
                    if len(current_containers) > count_before:
                        new_container = current_containers[-1]
                        
                        # Scroll để ảnh render
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", new_container)
                        time.sleep(1) # Chờ 1 chút cho src load xong
                        
                        # Quét thẻ IMG
                        images = new_container.find_elements(By.TAG_NAME, "img")
                        target_src = None
                        
                        for img in images:
                            try:
                                src = img.get_attribute("src")
                                w = int(img.get_attribute("naturalWidth") or 0)
                                
                                if not src: continue
                                
                                # --- BỘ LỌC ---
                                # Lưu ý: Mình đã COMMENT dòng dưới để chấp nhận link profile/picture theo ý bạn
                                # if "profile/picture" in src: continue 
                                
                                if "svg" in src: continue
                                if "data:image/gif" in src: continue 
                                
                                # Kích thước lớn > 300px
                                if w > 300: 
                                    self.log(f"🔍 Phát hiện ảnh chuẩn: {w}px | Link: {src[:40]}...")
                                    target_src = src
                                    break 
                                    
                            except StaleElementReferenceException:
                                continue
                        
                        if target_src:
                            # --- TẢI BẰNG PYTHON REQUESTS (QUAN TRỌNG) ---
                            # Đây là đoạn code sửa lỗi "Failed to fetch"
                            self.log("⬇️ Đang tải ảnh bằng Python Requests...")
                            
                            # 1. Lấy Cookies từ Selenium
                            selenium_cookies = self.driver.get_cookies()
                            session = requests.Session()
                            # Nạp cookie vào session
                            for cookie in selenium_cookies:
                                session.cookies.set(cookie['name'], cookie['value'])
                            
                            # 2. Lấy User-Agent
                            headers = {
                                "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
                                "Referer": "https://gemini.google.com/"
                            }

                            # 3. Tải file (Stream mode để tải file lớn)
                            try:
                                response = session.get(target_src, headers=headers, stream=True, timeout=30)
                                if response.status_code == 200:
                                    with open(output_path, 'wb') as f:
                                        for chunk in response.iter_content(1024):
                                            f.write(chunk)
                                    self.log(f"✅ Đã lưu ảnh thành công: {output_path}")
                                    return True
                                else:
                                    self.log(f"⚠️ Lỗi HTTP {response.status_code}. Thử lại...")
                            except Exception as dl_err:
                                self.log(f"⚠️ Lỗi mạng khi tải requests: {dl_err}")

                except StaleElementReferenceException:
                    pass
                except Exception as e:
                    pass
                
                time.sleep(3)

            self.log("❌ Timeout: Không lấy được ảnh sau 120s.")
            return False
            
        except Exception as e:
            self.log(f"❌ Lỗi Fatal: {e}")
            return False