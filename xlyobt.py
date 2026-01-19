import json
import random
import os
import zipfile
import shutil
import undetected_chromedriver as uc
import time

def create_proxy_auth_extension(host, port, user, password, plugin_dir):
    """Tạo Extension Manifest V3 để đăng nhập Proxy"""
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
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir)
    with open(os.path.join(plugin_dir, "manifest.json"), "w") as f:
        f.write(manifest_json)
    with open(os.path.join(plugin_dir, "background.js"), "w") as f:
        f.write(background_js)

def setup_orbita(json_path, root_path, download_dir):
    """
    Hàm khởi tạo trình duyệt Orbita.
    Trả về: đối tượng driver (hoặc None nếu lỗi)
    """
    # Cấu hình đường dẫn dựa trên root_path truyền vào
    ORBITA_PATH = r"C:\Users\CLV_SEO\Documents\orbita-browser-141\chrome.exe"
    DRIVER_PATH = r"C:\Users\CLV_SEO\Documents\orbita-browser-141\chromedriver.exe"
    
    if not os.path.exists(json_path):
        print(f"❌ Lỗi: Không tìm thấy file JSON tại: {json_path}")
        return None

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Xử lý đường dẫn file Zip
    profile_zip_path = data.get("Path")
    # Nếu trong json là đường dẫn tương đối, ghép với root_path
    if not os.path.isabs(profile_zip_path):
        full_zip_path = os.path.join(root_path, profile_zip_path)
    else:
        full_zip_path = profile_zip_path

    # 2. Tạo thư mục làm việc (Working Dir)
    zip_parent_dir = os.path.dirname(full_zip_path)
    zip_filename_no_ext = os.path.splitext(os.path.basename(full_zip_path))[0]
    working_profile_dir = os.path.join(zip_parent_dir, zip_filename_no_ext)

    print(f"📂 Working Profile: {working_profile_dir}")

    # 3. Giải nén (nếu chưa có)
    if not os.path.exists(working_profile_dir):
        print(f"📦 Đang giải nén profile...")
        try:
            os.makedirs(working_profile_dir, exist_ok=True)
            with zipfile.ZipFile(full_zip_path, 'r') as zip_ref:
                zip_ref.extractall(working_profile_dir)
        except Exception as e:
            print(f"❌ Lỗi giải nén: {e}")
            return None

    # Lấy User Agent & Proxy
    user_agent = data["Data"]["navigator"]["userAgent"]
    proxy_data = data.get("Data", {}).get("proxy", {})
    
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={working_profile_dir}")
    options.add_argument(f"--user-agent={user_agent}")

    # 3. Cấu hình preferences
    prefs = {
        "download.default_directory": download_dir, # Thay đổi đường dẫn tải xuống
        "download.prompt_for_download": False,      # Tắt hộp thoại hỏi nơi lưu (tự động lưu)
        "download.directory_upgrade": True,         # Cho phép ghi đè thư mục nếu cần
        "safebrowsing.enabled": True                # Tắt cảnh báo an toàn (tùy chọn)
    }

    # 4. Thêm prefs vào options
    options.add_experimental_option("prefs", prefs)

    # # Giá trị Resolution từ JSON, ví dụ: "1360x768"
    # res_str = data.get("Resolution") 
    #width = "1280"; height = "720"
    # options.add_argument(f"--window-size={width},{height}")
    

    # Xử lý Proxy
    proxy_host = proxy_data.get("host")
    proxy_port = proxy_data.get("port")
    proxy_user = proxy_data.get("username")
    proxy_pass = proxy_data.get("password")

    # Fallback nếu proxy nằm ở string "Proxy" thay vì object
    if not proxy_host: 
        proxy_str = data.get("Proxy", "")
        if proxy_str:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                proxy_host, proxy_port, proxy_user, proxy_pass = parts
            elif len(parts) == 2:
                proxy_host, proxy_port = parts

    if proxy_host and proxy_port:
        if proxy_user and proxy_pass:
            print(f"🔒 Proxy Auth: {proxy_host}:{proxy_port}")
            plugin_path = os.path.join(working_profile_dir, "proxy_auth_plugin")
            create_proxy_auth_extension(proxy_host, proxy_port, proxy_user, proxy_pass, plugin_path)
            options.add_argument(f"--load-extension={plugin_path}")
        else:
            print(f"🌐 Proxy No-Auth: {proxy_host}:{proxy_port}")
            options.add_argument(f"--proxy-server=http://{proxy_host}:{proxy_port}")

    options.add_argument("--disable-encryption")
    options.add_argument("--font-masking-mode=2")
    options.add_argument(f"--lang=en-US")

    print("🚀 Đang khởi động Orbita...")
    
    try:
        driver = uc.Chrome(
            options=options,
            browser_executable_path=ORBITA_PATH,
            driver_executable_path=DRIVER_PATH,
            version_main=141,
            headless=False,
            use_subprocess=True
        )
        
        # Cấu hình Fingerprint
        try:
            tz_id = data["Data"]["timezone"]["timezone"]
            driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": tz_id})
        except: pass

        try:
            geo_data = data["Data"]["geoLocation"]
            if geo_data["mode"] == "allow":
                driver.execute_cdp_cmd("Emulation.setGeolocationOverride", {
                    "latitude": geo_data["latitude"],
                    "longitude": geo_data["longitude"],
                    "accuracy": 100
                })
        except: pass
        
        time.sleep(2)
        width = random.randint(1200, 1450)
        height = random.randint(700, 900)
        driver.set_window_size(int(width), int(height))

        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        })
        """
        })

        return driver  # <--- QUAN TRỌNG: Trả về driver để main.py dùng

    except Exception as e:
        print(f"❌ Lỗi khởi tạo Driver: {e}")
        return None