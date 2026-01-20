import os
import json
import zipfile
import threading
import undetected_chromedriver as uc
from config.settings import ORBITA_PATH, DRIVER_PATH, ROOT_PATH

# Khóa an toàn toàn cục (Dùng chung cho cả Step 2 và Step 3 để tránh xung đột file zip)
DRIVER_INIT_LOCK = threading.Lock()

def create_proxy_auth_extension(host, port, user, password, plugin_dir):
    """Tạo Extension đăng nhập Proxy (Vì Chrome không hỗ trợ user:pass trực tiếp)"""
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

def init_driver_from_profile(json_profile_path, log_callback=print, download_dir=None):
    """
    Hàm khởi tạo Driver chuẩn cho Orbita Browser.
    """
    try:
        with open(json_profile_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log_callback(f"❌ Lỗi đọc file JSON profile: {e}")
        return None

    # --- 1. XỬ LÝ PROFILE PATH & GIẢI NÉN ---
    json_dir = os.path.dirname(json_profile_path)
    # Lấy đường dẫn file zip từ JSON (nếu có)
    profile_zip_path = data.get("Path") 
    folder_name = os.path.splitext(os.path.basename(json_profile_path))[0]
    working_profile_dir = os.path.join(json_dir, folder_name)

    # Nếu thư mục profile chưa tồn tại -> Cần giải nén
    if not os.path.exists(working_profile_dir):
        log_callback(f"📦 Đang giải nén Profile {folder_name}...")
        
        # Xử lý đường dẫn tương đối/tuyệt đối
        full_zip_path = profile_zip_path
        if full_zip_path and not os.path.isabs(full_zip_path):
            full_zip_path = os.path.join(ROOT_PATH, profile_zip_path)
        
        if full_zip_path and os.path.exists(full_zip_path):
            try:
                # Dùng Lock để tránh 2 luồng cùng giải nén 1 lúc gây lỗi file
                with DRIVER_INIT_LOCK:
                    if not os.path.exists(working_profile_dir):
                        with zipfile.ZipFile(full_zip_path, 'r') as zip_ref:
                            zip_ref.extractall(working_profile_dir)
                        log_callback(f"✅ Giải nén xong.")
            except Exception as e:
                log_callback(f"❌ Lỗi giải nén: {e}")
                return None
        else:
            log_callback(f"⚠️ Không tìm thấy file Zip. Sẽ tạo Profile trắng mới.")
            os.makedirs(working_profile_dir, exist_ok=True)

    log_callback(f"🚀 Khởi động Orbita cho: {folder_name}")

    # --- 2. CẤU HÌNH ORBITA OPTIONS ---
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={working_profile_dir}")
    options.add_argument(f"--profile-directory=Default")
    
    # Fake User-Agent từ Profile JSON
    try:
        ua = data["Data"]["navigator"]["userAgent"]
        options.add_argument(f"--user-agent={ua}")
    except: pass

    # --- 3. CẤU HÌNH CHỐNG TIMEOUT KHI CHẠY NỀN (QUAN TRỌNG) ---
    # Giúp tool chạy mượt kể cả khi bị che khuất hoặc minimize
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--window-size=1920,1080") # Ép size to để ko bị vỡ giao diện
    options.add_argument("--disable-client-side-phishing-detection")
    
    # Tối ưu hiệu năng
    options.add_argument('--no-first-run')
    options.add_argument('--disable-gpu') # Bật lại nếu máy có GPU xịn
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-popup-blocking')
    options.page_load_strategy = 'eager' # Load trang nhanh, không chờ tất cả ảnh load xong

    # --- 4. CẤU HÌNH PROXY ---
    try:
        proxy_data = data.get("Data", {}).get("proxy", {})
        host = proxy_data.get("host")
        port = proxy_data.get("port")
        user = proxy_data.get("username")
        password = proxy_data.get("password")

        if host and port:
            if user and password:
                plugin_path = os.path.join(working_profile_dir, "proxy_auth_plugin")
                create_proxy_auth_extension(host, port, user, password, plugin_path)
                options.add_argument(f"--load-extension={plugin_path}")
            else:
                options.add_argument(f"--proxy-server=http://{host}:{port}")
    except: pass

    # --- 5. CẤU HÌNH DOWNLOAD (CHO STEP 3) ---
    if download_dir:
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0
        }
        options.add_experimental_option("prefs", prefs)

    # --- 6. KHỞI TẠO DRIVER ---
    with DRIVER_INIT_LOCK:
        try:
            driver = uc.Chrome(
                options=options,
                browser_executable_path=ORBITA_PATH,
                driver_executable_path=DRIVER_PATH,
                # version_main=131, # Tắt dòng này để auto-detect version
                use_subprocess=True,
                headless=False,
            )
            return driver
        except Exception as e:
            log_callback(f"❌ Lỗi khởi tạo Chrome: {e}")
            return None