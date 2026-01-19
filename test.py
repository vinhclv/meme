import os
import threading
import time
from xlyobt import setup_orbita  # File này chứa hàm setup_orbita bạn đã gửi

def check_ip_task(json_path, root_path, download_dir):
    """Mở trình duyệt và lấy thông tin IP hiện tại"""
    driver = setup_orbita(json_path, root_path, download_dir)
    profile_name = os.path.basename(json_path)
    
    if driver:
        try:
            print(f"🔍 Profile {profile_name} đang kiểm tra IP...")

            # 1. Truy cập trang lấy IP dạng JSON để dễ đọc
            driver.get("https://api.ipify.org?format=json")
            time.sleep(2) # Đợi trang tải

            # Lấy nội dung trang (chứa IP)
            ip_info = driver.find_element("tag name", "body").text
            print(f"✅ Kết quả {profile_name}: {ip_info}")
            
            # 2. Hoặc truy cập trang check chi tiết để bạn xem bằng mắt (nếu muốn)
            # driver.get("https://whoer.net")
            
            # Giữ trình duyệt mở trong 10 giây để bạn quan sát
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ Lỗi khi check IP profile {profile_name}: {e}")
        finally:
            driver.quit()
            print(f"关闭 Profile: {profile_name}")

if __name__ == "__main__":
    import os
    # os.system("taskkill /f /im chrome.exe /t >nul 2>&1")
    # os.system("taskkill /f /im chromedriver.exe /t >nul 2>&1")
    
    # Thiết lập đường dẫn gốc
    ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
    PROFILES_DIR = os.path.join(ROOT_PATH, "profiles")
    DOWNLOAD_DIR = os.path.join(ROOT_PATH, "downloads")
    
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    # Lấy danh sách tối đa 3 file JSON từ folder profiles
    list_json = [f for f in os.listdir(PROFILES_DIR) if f.endswith('.json')][:3]

    if not list_json:
        print("❌ Không tìm thấy file JSON nào!")
    else:
        threads = []
        for file_name in list_json:
            json_path = os.path.join(PROFILES_DIR, file_name)
            
            # Tạo luồng (thread) chạy đa luồng
            t = threading.Thread(
                target=check_ip_task, 
                args=(json_path, ROOT_PATH, DOWNLOAD_DIR)
            )
            threads.append(t)
            t.start()
            
            # Đợi một chút để tránh xung đột tài nguyên
            time.sleep(2)

        for t in threads:
            t.join()

    print("✅ Hoàn thành kiểm tra IP cho 3 profile.")