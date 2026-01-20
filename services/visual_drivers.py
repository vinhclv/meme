import time
import requests
import base64
import os
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from config.selectors import VISUAL_CONFIGS
# ==========================================
# CLASS CHA (BASE DRIVER)
# ==========================================
class BaseVisualDriver:
    def __init__(self, driver, log_callback=None):
        self.driver = driver
        self.log = log_callback if log_callback else print

    def generate(self, prompt, output_path):
        """Hàm này sẽ được các class con viết lại (Override)"""
        raise NotImplementedError

    def _download(self, url, save_path):
        """
        Hàm tải file đa năng (All-in-One):
        1. Hỗ trợ ảnh Base64 (data:image/...)
        2. Hỗ trợ link HTTP bảo mật (tự động nạp Cookies từ Selenium)
        """
        try:
            # TRƯỜNG HỢP 1: ẢNH BASE64 (Dữ liệu ảnh nằm trực tiếp trong link)
            if url.startswith("data:image"):
                self.log("⬇️ Phát hiện ảnh Base64, đang giải mã...")
                header, encoded = url.split(",", 1)
                data = base64.b64decode(encoded)
                with open(save_path, "wb") as f:
                    f.write(data)
                self.log(f"✅ Đã lưu ảnh Base64: {os.path.basename(save_path)}")
                return True

            # TRƯỜNG HỢP 2: LINK HTTP (Cần Cookie để tải từ Google/Flow)
            else:
                self.log(f"⬇️ Đang tải file từ URL: {url[:50]}...")
                
                # 1. Mượn danh tính (Cookies) từ Selenium
                selenium_cookies = self.driver.get_cookies()
                session = requests.Session()
                for cookie in selenium_cookies:
                    session.cookies.set(cookie['name'], cookie['value'])
                
                # 2. Giả lập trình duyệt (Headers)
                headers = {
                    "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
                    "Referer": self.driver.current_url  # Lấy luôn URL hiện tại làm Referer cho chuẩn
                }

                # 3. Tải file (Stream mode cho file lớn)
                response = session.get(url, headers=headers, stream=True, timeout=60)
                
                if response.status_code == 200:
                    with open(save_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    self.log(f"✅ Đã lưu file: {os.path.basename(save_path)}")
                    return True
                else:
                    self.log(f"⚠️ Lỗi tải HTTP: {response.status_code}")
                    return False

        except Exception as e:
            self.log(f"❌ Lỗi khi lưu file: {e}")
            return False

# ==========================================
# DRIVER 2: FLOW (WEB UI)
# ==========================================
class FlowDriver(BaseVisualDriver):
    def generate(self, prompt, output_path):
        cfg = VISUAL_CONFIGS["flow"]
        timeout = cfg.get("WAIT_TIME", 180)
        
        prompt_text = str(prompt)
        if isinstance(prompt, dict):
            prompt_text = prompt.get("visual_prompt", prompt.get("prompt", str(prompt)))

        # 1. ĐIỀU HƯỚNG & SNAPSHOT BAN ĐẦU
        if not self._navigate_to_project(cfg):
            return False

        # [QUAN TRỌNG] Lấy danh sách ảnh gốc TRƯỚC KHI LÀM BẤT CỨ GÌ
        # Để sau này dù có F5 bao nhiêu lần, ta vẫn so sánh với mốc này
        initial_media_srcs = self._get_current_media_srcs(cfg["RESULT_ELEMENT"])
        self.log(f"📸 Snapshot ban đầu: {len(initial_media_srcs)} media.")

        # 2. VÒNG LẶP THỰC HIỆN
        MAX_RETRIES = 5
        for attempt in range(1, MAX_RETRIES + 1):
            self.log(f"🔄 [Lần {attempt}/{MAX_RETRIES}] Bắt đầu...")
            
            try:
                # --- LOGIC XỬ LÝ KHI RETRY (F5) ---
                if attempt > 1:
                    self.log("   -> ⚠️ Refresh để kiểm tra lại...")
                    self.driver.refresh()
                    time.sleep(random.randint(3, 5)) # Chờ load lại history
                    self._close_blocking_popups()

                    # [CHECK THÔNG MINH] Kiểm tra ngay xem sau khi F5, ảnh của lần trước có hiện ra không?
                    current_srcs = self._get_current_media_srcs(cfg["RESULT_ELEMENT"])
                    ghost_items = list(current_srcs - initial_media_srcs)
                    
                    # Lọc lấy ảnh hợp lệ
                    valid_ghosts = [s for s in ghost_items if s and ("blob:" in s or "http" in s)]
                    
                    if valid_ghosts:
                        target = valid_ghosts[0]
                        self.log(f"   🎉 TÌM THẤY ẢNH CŨ (Do UI lag)! Lấy luôn: {target[:30]}...")
                        if self._download(target, output_path):
                            return True
                    
                    self.log("   ℹ️ Vẫn chưa thấy ảnh, tiến hành tạo lại...")

                # --- QUY TRÌNH TẠO MỚI ---
                self._close_blocking_popups()

                # Nhập & Tạo
                if not self._input_prompt(prompt_text): continue
                if not self._click_generate(): continue

                self.log(f"   ⏳ Đang chờ kết quả...")

                # Chờ kết quả (So sánh với initial_media_srcs)
                target_src = self._wait_for_result(cfg["RESULT_ELEMENT"], initial_media_srcs, timeout)
                
                if target_src:
                    if self._download(target_src, output_path): 
                        return True
                    else:
                        self.log("   ⚠️ Tải lỗi, thử lại...")
                else:
                     self.log(f"   ⚠️ Lần {attempt} thất bại (Timeout/Lỗi).")

            except Exception as e:
                self.log(f"   ❌ Lỗi Fatal: {e}")
                time.sleep(random.randint(2, 4))

        self.log("❌ THẤT BẠI TOÀN TẬP.")
        return False

    # --- CÁC HÀM HỖ TRỢ RIÊNG ---

    def _navigate_to_project(self, cfg):
        try:
            if "/project/" in self.driver.current_url:
                self.log("✅ Đang ở trong dự án.")
                return True
            self.driver.get(cfg["URL"])
            time.sleep(random.randint(2,5))
            self._close_blocking_popups()
            wait = WebDriverWait(self.driver, 10)
            new_proj_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Dự án mới') or contains(., 'New project')]")))
            self._human_click(new_proj_btn)
            WebDriverWait(self.driver, 15).until(EC.url_contains("/project/"))
            time.sleep(random.randint(2,5))
            return True
        except: return False

    def _input_prompt(self, text):
        try:
            wait = WebDriverWait(self.driver, 10)
            # Tìm textarea theo ID (ổn định hơn) hoặc tag
            try:
                input_box = self.driver.find_element(By.ID, "PINHOLE_TEXT_AREA_ELEMENT_ID")
            except:
                input_box = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))

            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", input_box)
            time.sleep(random.randint(2,3))
            
            # Xóa sạch
            try: input_box.clear() 
            except: pass
            self.driver.execute_script("arguments[0].value = '';", input_box)
            
            # Focus & Nhập
            try: input_box.click()
            except: self.driver.execute_script("arguments[0].focus();", input_box)
            
            self.log(f"   ⌨️ Nhập prompt...")
            input_box.send_keys(text)
            time.sleep(random.randint(2,3))
            return True
        except: return False

    def _click_generate(self):
        try:
            # Gửi phím Enter thay vì tìm nút bấm (Ổn định hơn nhiều)
            self.log("   🖱️ Gửi lệnh (Enter)...")
            try:
                input_box = self.driver.find_element(By.ID, "PINHOLE_TEXT_AREA_ELEMENT_ID")
            except:
                input_box = self.driver.find_element(By.TAG_NAME, "textarea")
            
            input_box.send_keys(Keys.ENTER)
            return True
        except: return False

    def _wait_for_result(self, selector, initial_srcs, timeout):
        """
        Chờ kết quả mới dựa trên sự khác biệt với initial_srcs (Snapshot ban đầu)
        """
        start_time = time.time()
        
        # 1. Chờ loading biến mất (Logic C#)
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), '%') or contains(text(), 'Generating')]"))
            )
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), '%') or contains(text(), 'Generating')]"))
            )
            time.sleep(random.randint(2,3))
        except: pass

        # 2. Quét ảnh
        while time.time() - start_time < 30: # Quét thêm 30s sau khi loading xong
            try:
                err = self.driver.find_element(By.XPATH, "//div[contains(@role, 'alert')]")
                if "Failed" in err.text or "lỗi" in err.text.lower(): return None
            except: pass

            current_srcs = self._get_current_media_srcs(selector)
            
            # So sánh với SNAPSHOT BAN ĐẦU (initial_srcs)
            new_items = list(current_srcs - initial_srcs)
            
            for src in new_items:
                if src and ("blob:" in src or "http" in src):
                    self.log(f"   🎉 Có hàng mới: {src[:50]}...")
                    return src
            time.sleep(random.randint(2,4))
        return None

    def _close_blocking_popups(self):
        try:
            xpaths = ["//button[contains(@aria-label, 'Close')]", "//button[contains(., 'Got it')]", "//div[contains(@class, 'toast')]//button"]
            for xp in xpaths:
                els = self.driver.find_elements(By.XPATH, xp)
                for el in els:
                    if el.is_displayed(): self.driver.execute_script("arguments[0].click();", el)
        except: pass

    def _human_click(self, element):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(random.randint(1 ,2))
            element.click()
        except: self.driver.execute_script("arguments[0].click();", element)

    def _get_current_media_srcs(self, selector_css):
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, f"{selector_css}")
            srcs = set()
            for el in elements:
                src = el.get_attribute("src")
                if src: srcs.add(src)
            return srcs
        except: return set()      

# ==========================================
# DRIVER 2: GOOGLE VEO (OPTIMIZED LOGIC)
# ==========================================
class GoogleVeoDriver(BaseVisualDriver):
    
    def _js_click(self, element):
        """Hàm click cưỡng chế bằng JS"""
        self.driver.execute_script("arguments[0].click();", element)

    def _setup_gemini_tools(self, wait):
        """
        Cấu hình Tool & Model.
        Hàm này có sẵn thời gian chờ 5s ở đầu để trang ổn định sau khi F5.
        """
        self.log("   ⏳ Đợi 5s cho trang ổn định...")
        time.sleep(5) 
        
        self.log("   ⚙️ Đang cấu hình Tool & Model...")
        
        # --- 1. CHỌN TOOL TẠO ẢNH ---
        try:
            xpath_tool_menu = "//toolbox-drawer//button" 
            btn_tool_menu = wait.until(EC.presence_of_element_located((By.XPATH, xpath_tool_menu)))
            self._js_click(btn_tool_menu)
            time.sleep(1.5)

            xpath_gen_img = "//*[contains(text(), 'Generate image') or contains(text(), 'Tạo hình ảnh')]"
            btn_gen_img = wait.until(EC.presence_of_element_located((By.XPATH, xpath_gen_img)))
            self._js_click(btn_gen_img)
            self.log("      ✅ Đã chọn Tool: Tạo hình ảnh.")
            time.sleep(2)
        except Exception as e: self.log(f"      ⚠️ Warning Tool: {e}")

        # --- 2. CHỌN CHẾ ĐỘ PRO ---
        try:
            xpath_model_menu = "//bard-mode-switcher//button"
            btn_model_menu = wait.until(EC.presence_of_element_located((By.XPATH, xpath_model_menu)))
            self._js_click(btn_model_menu)
            time.sleep(1.5)

            xpath_pro = "//*[contains(text(), 'Pro') or contains(text(), 'Advanced') or contains(text(), 'Nâng cao')]"
            btn_pro = wait.until(EC.presence_of_element_located((By.XPATH, xpath_pro)))
            self._js_click(btn_pro)
            self.log("      ✅ Đã chọn Model: Pro/Advanced.")
            time.sleep(2)
        except Exception as e: self.log(f"      ⚠️ Warning Model: {e}")

    def generate(self, prompt, output_path):
        cfg = VISUAL_CONFIGS["google_veo"]
        MAX_RETRIES = 3 
        
        # Xử lý Prompt
        prompt_str = str(prompt)
        if isinstance(prompt, dict):
            core = prompt.get("visual_prompt", prompt.get("prompt", prompt_str))
            prompt_str = f"A single centered view of {core}. Do not use split screen, diptych, collage, or grid."
        else:
            prompt_str = f"A single centered view of {prompt_str}. Do not use split screen, collage."

        for attempt in range(1, MAX_RETRIES + 1):
            self.log(f"🔄 [Lần {attempt}/{MAX_RETRIES}] Bắt đầu...")
            
            try:
                wait = WebDriverWait(self.driver, 60)
                
                # 👇 [LOGIC MỚI] Kiểm tra xem có cần Setup lại không
                need_setup = False

                # TRƯỜNG HỢP 1: Retry (Lần 2 trở đi) -> Bắt buộc F5 -> Bắt buộc Setup
                if attempt > 1:
                    self.log("   -> ⚠️ Refresh trang...")
                    self.driver.refresh()
                    # Không cần sleep ở đây nữa vì hàm _setup_gemini_tools đã có sleep(5) ở đầu
                    need_setup = True 
                
                # TRƯỜNG HỢP 2: Chưa vào đúng trang -> Vào trang -> Bắt buộc Setup
                if "gemini.google.com" not in self.driver.current_url:
                    self.driver.get(cfg["URL"])
                    need_setup = True
                
                # 👇 CHỈ CHẠY SETUP KHI CẦN THIẾT
                if need_setup:
                    self._setup_gemini_tools(wait)
                else:
                    self.log("   ⏩ Môi trường ổn định, bỏ qua bước chọn Tool.")

                # ====================================================
                # BƯỚC 1: SNAPSHOT ID CŨ
                # ====================================================
                id_selector = "[id^='model-response-message-content']"
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, id_selector)
                    old_ids = set([e.get_attribute("id") for e in elements if e.get_attribute("id")])
                except: old_ids = set()
                self.log(f"   📸 Đã nhớ {len(old_ids)} tin nhắn cũ.")

                # ====================================================
                # BƯỚC 2: NHẬP PROMPT & GỬI
                # ====================================================
                try:
                    input_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg["INPUT_BOX"])))
                    
                    self.driver.execute_script("arguments[0].click();", input_box)
                    time.sleep(0.5)
                    
                    input_box.send_keys(Keys.CONTROL + "a")
                    input_box.send_keys(Keys.DELETE)
                    time.sleep(0.5)
                    
                    full_prompt = f"Generate an image: {prompt_str}"
                    self.driver.execute_script(
                        """
                        var elm = arguments[0]; elm.focus();
                        document.execCommand('insertText', false, arguments[1]);
                        elm.dispatchEvent(new Event('input', { bubbles: true }));
                        """, input_box, full_prompt
                    )
                    time.sleep(random.randint(1, 2))
                    
                    try:
                        btn = self.driver.find_element(By.CSS_SELECTOR, cfg["CREATE_BTN"])
                        self.driver.execute_script("arguments[0].click();", btn)
                    except: 
                        input_box.send_keys(Keys.ENTER)
                        
                except Exception as e:
                    self.log(f"   ❌ Lỗi nhập liệu: {e}")
                    continue 

                self.log(f"   ⏳ Đang chờ ID mới...")

                # ====================================================
                # BƯỚC 3: SĂN ID MỚI & TẢI ẢNH
                # ====================================================
                start_time = time.time()
                timeout = cfg.get("WAIT_TIME", 120)
                
                while time.time() - start_time < timeout:
                    try:
                        current_elements = self.driver.find_elements(By.CSS_SELECTOR, id_selector)
                        
                        target_id = None
                        for el in reversed(current_elements):
                            eid = el.get_attribute("id")
                            if eid and eid not in old_ids:
                                target_id = eid
                                break 
                        
                        if target_id:
                            target_xpath = f"//*[@id='{target_id}']//generated-image//img"
                            try:
                                img_element = self.driver.find_element(By.XPATH, target_xpath)
                                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", img_element)
                                
                                src = img_element.get_attribute("src")
                                w = self.driver.execute_script("return arguments[0].naturalWidth;", img_element)
                                
                                if src and "http" in src and w and int(w) > 300:
                                    self.log(f"   🔍 Bắt được ảnh: {w}px")
                                    if self._download(src, output_path):
                                        return True
                            except: pass
                                
                    except Exception: pass
                    time.sleep(2)

                self.log(f"   ⚠️ Timeout lần {attempt}.")
            
            except Exception as e:
                self.log(f"   ❌ Lỗi Fatal: {e}")
            
            if attempt < MAX_RETRIES: time.sleep(random.randint(3, 5))

        return False