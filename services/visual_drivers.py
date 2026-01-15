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
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, ElementNotInteractableException



def download_authenticated_file(driver, url, output_path, referer=None):
    """
    Tải file từ URL sử dụng Cookies và User-Agent của Selenium Driver hiện tại.
    Giúp vượt qua cơ chế chặn bot và CORS của server.
    
    Args:
        driver: Selenium webdriver instance (đang chạy và đã login)
        url: Link file cần tải
        output_path: Đường dẫn lưu file
        referer: (Optional) Link trang web gốc để giả mạo header Referer
        
    Returns:
        True nếu tải thành công, False nếu thất bại.
    """
    try:
        print(f"⬇️ Đang tải: {url[:50]}...")

        # 1. Tạo session và nạp Cookies từ Selenium
        session = requests.Session()
        selenium_cookies = driver.get_cookies()
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        # 2. Lấy User-Agent thực tế từ trình duyệt
        user_agent = driver.execute_script("return navigator.userAgent;")
        
        headers = {
            "User-Agent": user_agent
        }
        if referer:
            headers["Referer"] = referer

        # 3. Thực hiện request tải file (Stream mode)
        # timeout=30s để tránh treo tool nếu mạng lag
        response = session.get(url, headers=headers, stream=True, timeout=30)

        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192): # Tăng chunk lên 8KB cho nhanh
                    if chunk:
                        f.write(chunk)
            print(f"✅ Đã lưu: {output_path}")
            return True
        else:
            print(f"⚠️ Lỗi tải file: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Exception khi tải file: {e}")
        return False
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
        timeout = cfg.get("WAIT_TIME", 180) 
        
        # 1. Xử lý Prompt
        prompt_text = str(prompt)
        if isinstance(prompt, dict):
            prompt_text = prompt.get("visual_prompt", prompt.get("prompt", str(prompt)))

        # ==================================================================
        # GIAI ĐOẠN 1: ĐẢM BẢO ĐANG Ở TRONG DỰ ÁN (EDITOR)
        # ==================================================================
        try:
            # Kiểm tra xem đang ở trang dự án chưa (URL chứa "/project/")
            if "/project/" in self.driver.current_url:
                self.log("✅ Đang ở trong dự án, sẵn sàng nhập prompt.")
            else:
                self.log("🏠 Đang ở trang chủ (hoặc trang khác), tiến hành tạo dự án mới...")
                self.driver.get(cfg["URL"])
                time.sleep(5)
                
                # Tắt popup nếu có
                self._close_blocking_popups()
                
                # Bấm nút "Dự án mới"
                try:
                    wait_home = WebDriverWait(self.driver, 10)
                    new_proj_btn = wait_home.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Dự án mới') or contains(., 'New project')]"))
                    )
                    self._human_click(new_proj_btn)
                    
                    # Chờ chuyển hướng sang trang Project (quan trọng)
                    WebDriverWait(self.driver, 15).until(EC.url_contains("/project/"))
                    self.log("🎉 Đã vào giao diện Editor thành công!")
                    time.sleep(4) # Chờ UI ổn định
                except Exception as e:
                    self.log(f"❌ Không bấm được nút tạo dự án: {e}")
                    return False

        except Exception as e:
            self.log(f"❌ Lỗi điều hướng ban đầu: {e}")
            return False

        # ==================================================================
        # GIAI ĐOẠN 2: VÒNG LẶP THỬ TẠO ẢNH (RETRY TẠI CHỖ)
        # ==================================================================
        MAX_RETRIES = 3
        
        for attempt in range(1, MAX_RETRIES + 1):
            self.log(f"🔄 [Lần thử {attempt}/{MAX_RETRIES}] Bắt đầu quy trình...")
            
            try:
                # Nếu là lần thử lại (attempt > 1), Refresh lại trang DỰ ÁN
                if attempt > 1:
                    self.log("   -> ⚠️ Lần trước lỗi. Refresh (F5) lại trang dự án...")
                    self.driver.refresh()
                    time.sleep(5) 
                
                # Tắt popup chắn đường (nếu có sau khi refresh hoặc lỗi)
                self._close_blocking_popups()
                
                wait = WebDriverWait(self.driver, timeout)

                # A. Snapshot Media cũ (Đếm lại sau khi refresh)
                old_media_srcs = self._get_current_media_srcs(cfg["RESULT_ELEMENT"])
                self.log(f"   📸 Media cũ: {len(old_media_srcs)}")

                # B. Tìm & Nhập Prompt
                try:
                    input_box = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
                    
                    # Scroll & Focus
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", input_box)
                    time.sleep(1)
                    
                    # Xóa cũ & Nhập mới
                    self.driver.execute_script("arguments[0].value = '';", input_box)
                    
                    # Click (nếu lỗi click thì dùng JS focus, không thoát)
                    try:
                        input_box.click()
                    except:
                        self.driver.execute_script("arguments[0].focus();", input_box)
                    
                    self.log(f"   ⌨️ Nhập prompt...")
                    input_box.send_keys(prompt_text)
                    time.sleep(1)
                    
                except Exception as e:
                    self.log(f"   ❌ Lỗi nhập liệu: {e}")
                    continue # Thử lại lần sau (sẽ trigger refresh)

                # C. Click Generate
                self.log("   🖱️ Click Generate...")
                try:
                    # Tìm nút Generate (loại trừ nút bị disable)
                    btn = self.driver.find_element(By.XPATH, "//button[contains(., '->') or contains(., 'Generate')]")
                    
                    if btn.get_attribute("disabled"):
                        self.log("   ⚠️ Nút Generate đang disable (chờ 3s)...")
                        time.sleep(3)
                    
                    self._human_click(btn)
                except:
                    # Fallback Enter
                    input_box.send_keys(Keys.CONTROL, Keys.ENTER)

                self.log(f"   ⏳ Đang chờ kết quả...")

                # D. Chờ kết quả
                start_time = time.time()
                success_flag = False
                
                while time.time() - start_time < timeout:
                    # 1. Check lỗi Google (để retry sớm)
                    try:
                        error_toasts = self.driver.find_elements(By.XPATH, "//div[contains(@role, 'alert')]")
                        for err in error_toasts:
                            if "Failed" in err.text or "lỗi" in err.text.lower():
                                self.log(f"   ❌ Google báo lỗi: {err.text}")
                                # Thoát vòng lặp while -> Code sẽ xuống cuối vòng for -> Retry (Refresh trang)
                                start_time = 0 # Force break
                                break 
                    except: pass
                    if start_time == 0: break

                    # 2. Check ảnh mới
                    current_media_srcs = self._get_current_media_srcs(cfg["RESULT_ELEMENT"])
                    new_items = list(current_media_srcs - old_media_srcs)
                    
                    if new_items:
                        for src in new_items:
                            if src and ("blob:" in src or "http" in src):
                                self.log(f"   🎉 Có hàng mới: {src[:50]}...")
                                # Tải luôn
                                if self._download_via_requests(src, output_path):
                                    return True # [THÀNH CÔNG] -> Thoát hẳn hàm
                                else:
                                    self.log("   ⚠️ Tải lỗi, thử quét tiếp...")
                        
                    time.sleep(2)

                # Nếu hết while mà chưa return True -> Timeout hoặc Lỗi
                self.log(f"   ⚠️ Lần {attempt} thất bại. Chuẩn bị thử lại...")

            except Exception as e:
                self.log(f"   ❌ Lỗi Fatal lần {attempt}: {e}")
                time.sleep(2)

        self.log("❌ THẤT BẠI TOÀN TẬP: Đã thử hết số lần cho phép.")
        return False

    # ======================================================
    # CÁC HÀM HỖ TRỢ (GIỮ NGUYÊN)
    # ======================================================
    def _close_blocking_popups(self):
        try:
            xpaths = ["//button[contains(@aria-label, 'Close')]", "//button[contains(., 'Got it')]", "//div[contains(@class, 'toast')]//button"]
            for xp in xpaths:
                els = self.driver.find_elements(By.XPATH, xp)
                for el in els:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
        except: pass

    def _human_click(self, element):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(0.5)
            element.click()
        except:
            self.driver.execute_script("arguments[0].click();", element)

    def _get_current_media_srcs(self, selector_css):
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, f"{selector_css}, video")
            srcs = set()
            for el in elements:
                src = el.get_attribute("src")
                if src: srcs.add(src)
            return srcs
        except:
            return set()

    def _download_via_requests(self, url, output_path):
        try:
            self.log("⬇️ Đang tải...")
            selenium_cookies = self.driver.get_cookies()
            session = requests.Session()
            for cookie in selenium_cookies:
                session.cookies.set(cookie['name'], cookie['value'])
            headers = {"User-Agent": self.driver.execute_script("return navigator.userAgent;"), "Referer": "https://labs.google/"}
            with session.get(url, headers=headers, stream=True, timeout=60) as r:
                if r.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in r.iter_content(8192): f.write(chunk)
                    self.log(f"✅ Đã lưu: {output_path}")
                    return True
            return False
        except: return False
# DRIVER: GOOGLE GEMINI CHAT (FIX TẢI ẢNH)
# ==========================================
class GoogleVeoDriver(BaseVisualDriver):
    def generate(self, prompt, output_path):
        cfg = VISUAL_CONFIGS["google_veo"]
        
        # Cấu hình số lần thử lại
        MAX_RETRIES = 3 
        
        # --- 1. XỬ LÝ PROMPT (Làm 1 lần duy nhất ở ngoài vòng lặp) ---
        if isinstance(prompt, dict):
            core_prompt = prompt.get("visual_prompt", prompt.get("prompt", str(prompt)))
            avoid_terms = "Do not use split screen, diptych, collage, or grid. Create a single unified image."
            structure_terms = "A single centered view of"
            final_prompt_str = f"{structure_terms} {core_prompt}. {avoid_terms}"
            prompt = final_prompt_str
        else:
            prompt = f"A single centered view of {prompt}. Do not use split screen, collage."
        
        prompt = str(prompt)

        # --- 2. BẮT ĐẦU VÒNG LẶP RETRY ---
        for attempt in range(1, MAX_RETRIES + 1):
            self.log(f"🔄 [Lần thử {attempt}/{MAX_RETRIES}] Bắt đầu quy trình tạo ảnh...")
            
            try:
                # A. QUẢN LÝ REFRESH (SMART REFRESH)
                # - Lần 1: Chỉ vào trang nếu chưa đúng URL.
                # - Lần 2 trở đi (Retry): BẮT BUỘC Refresh để sửa lỗi timeout trước đó.
                if attempt > 1:
                    self.log("   -> ⚠️ Lần trước thất bại. Đang Refresh (F5) lại trang...")
                    self.driver.refresh()
                    time.sleep(5) # Chờ load lại DOM
                
                # Đảm bảo đang ở đúng URL
                if "gemini.google.com" not in self.driver.current_url:
                    self.driver.get(cfg["URL"])
                    time.sleep(3)
                
                wait = WebDriverWait(self.driver, 60)

                # B. Đếm số container ảnh cũ (Snapshot)
                try:
                    # Chờ body load xong
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    existing_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.attachment-container")
                    count_before = len(existing_containers)
                except:
                    count_before = 0
                
                self.log(f"   📸 Số ảnh cũ: {count_before}")

                # C. Nhập Prompt
                try:
                    input_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg["INPUT_BOX"])))
                    input_box.click()
                    
                    # QUAN TRỌNG: Clear box bằng JS để đảm bảo sạch sẽ khi Retry
                    self.driver.execute_script("arguments[0].innerText = '';", input_box)
                    self.driver.execute_script("arguments[0].value = '';", input_box)
                    
                    full_prompt = f"Generate an image: {prompt}"
                    self.driver.execute_script(
                        """
                        var elm = arguments[0]; elm.focus();
                        document.execCommand('insertText', false, arguments[1]);
                        elm.dispatchEvent(new Event('input', { bubbles: true }));
                        """, input_box, full_prompt
                    )
                    time.sleep(1)
                    
                    # Click gửi
                    try:
                        btn = self.driver.find_element(By.CSS_SELECTOR, cfg["CREATE_BTN"])
                        btn.click()
                    except:
                        input_box.send_keys(Keys.ENTER)
                        
                except Exception as e:
                    self.log(f"   ❌ Lỗi nhập prompt: {e}")
                    # Nếu lỗi nhập liệu (do chưa load xong input), bỏ qua lần này để refresh thử lại
                    continue 

                self.log(f"   ⏳ Đang chờ ảnh mới...")

                # D. VÒNG LẶP CHỜ ẢNH (Wait Loop)
                start_time = time.time()
                timeout_per_try = 120 # 120s cho mỗi lần thử
                
                while time.time() - start_time < timeout_per_try:
                    try:
                        current_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.attachment-container")
                        
                        if len(current_containers) > count_before:
                            new_container = current_containers[-1]
                            
                            # Scroll tới
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", new_container)
                            time.sleep(1)
                            
                            # Quét ảnh
                            images = new_container.find_elements(By.TAG_NAME, "img")
                            target_src = None
                            
                            for img in images:
                                try:
                                    src = img.get_attribute("src")
                                    w = int(img.get_attribute("naturalWidth") or 0)
                                    
                                    if not src: continue
                                    
                                    # Bộ lọc rác
                                    if "svg" in src: continue
                                    if "data:image/gif" in src: continue 
                                    
                                    # Kích thước > 300px
                                    if w > 300: 
                                        self.log(f"   🔍 Phát hiện ảnh chuẩn: {w}px | Link: {src[:40]}...")
                                        target_src = src
                                        break 
                                        
                                except StaleElementReferenceException:
                                    continue
                            
                            if target_src:
                                # Gọi hàm tải ảnh (dùng requests như đã bàn)
                                success = download_authenticated_file(
                                    driver=self.driver,
                                    url=target_src,
                                    output_path=output_path,
                                    referer="https://gemini.google.com/"
                                )
                                
                                if success:
                                    return True # [EXIT] THÀNH CÔNG -> THOÁT KHỎI HÀM
                                else:
                                    self.log("   ⚠️ Tải lỗi, thử quét lại...")
                    
                    except StaleElementReferenceException:
                        pass
                    except Exception:
                        pass
                    
                    time.sleep(3)

                # Nếu chạy hết vòng while mà code xuống đây -> Nghĩa là Timeout
                self.log(f"   ⚠️ Timeout lần {attempt}: Không thấy ảnh.")
            
            except Exception as e:
                self.log(f"   ❌ Lỗi Fatal lần {attempt}: {e}")
            
            # Nếu vẫn còn lượt thử, nghỉ 1 chút rồi quay lại đầu vòng for
            if attempt < MAX_RETRIES:
                self.log(f"   🔄 Chuẩn bị thử lại lần {attempt + 1}...")
                time.sleep(3)

        # Hết tất cả số lần thử mà vẫn không return True
        self.log("❌ THẤT BẠI TOÀN TẬP: Đã thử hết số lần cho phép.")
        return False