import os
import json
import zipfile
import threading
import undetected_chromedriver as uc
from config.settings import ORBITA_PATH, DRIVER_PATH, ROOT_PATH

# Khóa an toàn toàn cục (Dùng chung cho cả Step 2 và Step 3)
DRIVER_INIT_LOCK = threading.Lock()

def create_proxy_auth_extension(host, port, user, password, plugin_dir):
    """Tạo Extension đăng nhập Proxy"""
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
    Hàm chung khởi tạo Driver.
    :param json_profile_path: Đường dẫn file JSON cấu hình.
    :param log_callback: Hàm để in log ra ngoài (ví dụ self._log).
    :param download_dir: (Optional) Đường dẫn lưu file tải về (Dùng cho Step 3).
    """
    try:
        with open(json_profile_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log_callback(f"❌ Lỗi đọc file JSON profile: {e}")
        return None

    # --- XỬ LÝ ĐƯỜNG DẪN ---
    json_dir = os.path.dirname(json_profile_path)
    profile_zip_path = data.get("Path")
    folder_name = os.path.splitext(os.path.basename(json_profile_path))[0]
    working_profile_dir = os.path.join(json_dir, folder_name)

    # --- LOGIC GIẢI NÉN ---
    if not os.path.exists(working_profile_dir):
        log_callback(f"📦 Đang giải nén Profile {folder_name}...")
        full_zip_path = profile_zip_path
        if not os.path.isabs(full_zip_path):
            full_zip_path = os.path.join(ROOT_PATH, profile_zip_path)
        
        if os.path.exists(full_zip_path):
            try:
                with DRIVER_INIT_LOCK:
                    if not os.path.exists(working_profile_dir):
                        with zipfile.ZipFile(full_zip_path, 'r') as zip_ref:
                            zip_ref.extractall(working_profile_dir)
                        log_callback(f"✅ Giải nén xong.")
            except Exception as e:
                log_callback(f"❌ Lỗi giải nén: {e}")
                return None
        else:
            log_callback(f"⚠️ Không tìm thấy Zip. Tạo profile trắng.")
            os.makedirs(working_profile_dir, exist_ok=True)

    log_callback(f"🚀 Khởi động Orbita cho: {folder_name}")

    # --- CẤU HÌNH CHROME ---
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={working_profile_dir}")
    options.add_argument(f"--profile-directory=Default") # Hoặc "Profile 1" tùy máy bạn
    
    try:
        ua = data["Data"]["navigator"]["userAgent"]
        options.add_argument(f"--user-agent={ua}")
    except: pass

    # Proxy Config
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

    # Download Config (Cho Step 3)
    if download_dir:
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

    # Optimization
    options.add_argument('--no-first-run')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-popup-blocking')
    options.page_load_strategy = 'eager'



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
            log_callback(f"❌ Lỗi khởi tạo Chrome: {e}")
            return None