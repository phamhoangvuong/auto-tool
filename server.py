import time
import os
import base64
import requests
import random
import re
import threading
import logging  # Thêm để tắt log Flask
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# ==============================================================================
# SERVER SETUP
# ==============================================================================
app = Flask(__name__)
CORS(app)  # Cho phép frontend gọi từ localhost

# Biến toàn cục lưu log real-time để trả về cho web
current_log = ">>> 🌐 NEBULA DTU SNIPER SERVER ĐANG SẴN SÀNG...\n"

def log_print(*args, **kwargs):
    """Thay thế print() để lưu log vào current_log và in ra console"""
    global current_log
    message = " ".join(map(str, args))
    print(message, **kwargs)
    current_log += message + "\n"

# ==============================================================================
# CẤU HÌNH TOOL
# ==============================================================================
API_KEYS_POOL = [
    "AIzaSyAMCSp1B0ZJxvClT8z56JNd5qAytxVkqOM", 
    # Thêm key khác nếu muốn
]

URL_LOGIN = "https://mydtu.duytan.edu.vn/Signin.aspx"
URL_DANGKY_LOP = "https://mydtu.duytan.edu.vn/sites/index.aspx?p=home_registeredall&semesterid=92&yearid=90"

MODELS_LIST = [
    "gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-flash-8b",
    "gemini-2.0-flash-exp", "gemini-exp-1206", "gemini-2.5-flash",
]

ADD_CLICK_JS = "Add_Click('Bạn có muốn Đăng ký Lớp này? ',90,92,29211121549,'1210 ','AMINHAKEYTEM32NYTES1234567891234 ','7061737323313233 ')"

MAX_ROUNDS = 20

# ==============================================================================
# HÀM HỖ TRỢ
# ==============================================================================
def solve_captcha(image_path):
    if not os.path.exists(image_path) or os.path.getsize(image_path) < 500:
        return None
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        payload = {"contents": [{"parts": [{"text": "OUTPUT ONLY TEXT. UPPERCASE. NO SPACES."},
                                          {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}]}
        
        for api_key in API_KEYS_POOL:
            for _ in range(7):
                model = random.choice(MODELS_LIST)
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                try:
                    r = requests.post(url, json=payload, timeout=10)
                    if r.status_code == 200:
                        text = re.sub(r'[^A-Z0-9]', '', r.json()['candidates'][0]['content']['parts'][0]['text'].upper())
                        if 3 <= len(text) <= 8 and "CAPTCHA" not in text:
                            log_print(f"✅ Captcha solved [{model}]: {text}")
                            return text
                except Exception as e:
                    pass
                time.sleep(0.2)
        return None
    except Exception as e:
        log_print(f"❌ Lỗi solve_captcha: {e}")
        return None

def filter_valid_class_codes(codes):
    valid = [c.strip() for c in codes if len(c.strip()) >= 10 and "MÃ_LỚP" not in c.upper()]
    log_print(f">>> 🎯 Danh sách mã lớp hợp lệ ({len(valid)}): {valid}")
    return valid

def capture_element_persistent(driver, element_id, filename, retries=5):
    for i in range(retries):
        try:
            elements = driver.find_elements(By.ID, element_id)
            if not elements:
                log_print(f"   ⚠️ Không tìm thấy element #{element_id} (lần {i+1}/{retries})")
                time.sleep(1)
                continue

            element = elements[0]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(1)

            driver.execute_script(f"""
                var img = document.getElementById('{element_id}');
                if (img) {{
                    img.src = '../Modules/portal/JpegImage.aspx?' + new Date().getTime();
                }}
            """)
            time.sleep(1.5)

            element.screenshot(filename)
            if os.path.exists(filename) and os.path.getsize(filename) > 1000:
                log_print(f"   📸 Đã chụp captcha thành công → {filename} ({os.path.getsize(filename)} bytes)")
                return True
            else:
                log_print(f"   ⚠️ Ảnh captcha quá nhỏ hoặc lỗi ({os.path.getsize(filename) if os.path.exists(filename) else 0} bytes)")
        except Exception as e:
            log_print(f"   ❌ Lỗi chụp captcha: {e}")
        time.sleep(1)
    return False

def wait_for_thongbao_blocking(driver, max_wait=40):
    log_print(">>> ⏳ Đang chờ phản hồi từ server DTU...", end="", flush=True)
    start = time.time()
    while time.time() - start < max_wait:
        try:
            elems = driver.find_elements(By.ID, "displayThongBao")
            if elems and elems[0].text.strip():
                msg = elems[0].text.strip()
                log_print(f"\n>>> 📢 Phản hồi: {msg}")
                return msg.lower()
        except:
            pass
        time.sleep(0.4)
        print(".", end="", flush=True)
    log_print("\n>>> ⏰ Timeout chờ phản hồi")
    return ""

# ==============================================================================
# HÀM CHẠY TOOL CHÍNH
# ==============================================================================
def run_automation_task(username, password, raw_codes):
    timestamp = datetime.now().strftime("%H%M%S")
    thread_id = f"{username}_{timestamp}"

    log_print(f"\n{'='*80}")
    log_print(f"🚀 BẮT ĐẦU TOOL CHO: {username} (Thread: {thread_id})")
    log_print(f"{'='*80}")

    codes = filter_valid_class_codes(raw_codes)
    if not codes:
        log_print(">>> ❌ Không có mã lớp hợp lệ → Dừng tool")
        return

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1024,768")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--mute-audio")

    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 15)

        driver.execute_cdp_cmd('Network.enable', {})
        driver.execute_cdp_cmd('Network.setBlockedURLs', {'urls': ["*.css", "*.jpg", "*.png", "*.gif", "*.woff*", "*font*", "*google-analytics*", "*facebook*"]})

        # === LOGIN ===
        login_success = False
        for attempt in range(1, 11):
            log_print(f">>> 🔄 Đăng nhập lần {attempt}/10...")
            driver.get(URL_LOGIN)
            time.sleep(2)

            try:
                wait.until(EC.presence_of_element_located((By.ID, "txtUser"))).send_keys(username)
                driver.find_element(By.ID, "txtPass").send_keys(password)

                captcha_img = wait.until(EC.visibility_of_element_located((By.XPATH, "//img[contains(@src,'CaptchaImage.axd')]")))
                login_captcha_file = f"captcha_login_{thread_id}.png"
                captcha_img.screenshot(login_captcha_file)

                captcha_text = solve_captcha(login_captcha_file)
                if os.path.exists(login_captcha_file):
                    os.remove(login_captcha_file)

                if not captcha_text:
                    log_print("   ⚠️ Không giải được captcha login → thử lại")
                    continue

                driver.find_element(By.ID, "txtCaptcha").clear()
                driver.find_element(By.ID, "txtCaptcha").send_keys(captcha_text)
                driver.find_element(By.ID, "btnLogin1").click()

                time.sleep(3)
                if "Signin.aspx" not in driver.current_url:
                    log_print("✅ ĐĂNG NHẬP THÀNH CÔNG!")
                    login_success = True
                    break
                else:
                    log_print("   ⚠️ Sai captcha hoặc tài khoản → thử lại")
            except Exception as e:
                log_print(f"   ❌ Lỗi login: {e}")

        if not login_success:
            log_print(">>> ❌ Đăng nhập thất bại sau 10 lần thử → Dừng tool")
            return

        log_print(">>> 🌍 Đang vào trang đăng ký tín chỉ...")
        driver.get(URL_DANGKY_LOP)
        time.sleep(4)

        # === LOOP ĐĂNG KÝ ===
        remaining_codes = codes.copy()
        for round_num in range(1, MAX_ROUNDS + 1):
            if not remaining_codes:
                log_print(">>> 🎉 Đã xử lý hết tất cả lớp!")
                break

            log_print(f"\n--- VÒNG {round_num}/{MAX_ROUNDS} ---")
            failed_this_round = []

            for code in remaining_codes:
                log_print(f"⚡ Đang xử lý: {code}")
                try:
                    inp = wait.until(EC.presence_of_element_located((By.ID, "ctl00_PlaceHolderContentArea_ctl00_ctl01_txt_ClassID")))
                    inp.clear()
                    inp.send_keys(code)
                    time.sleep(0.8)

                    driver.execute_script("var img = document.getElementById('imgCapt'); if(img) img.src += '&' + new Date().getTime();")
                    time.sleep(1.5)

                    reg_captcha_file = f"captcha_reg_{thread_id}.png"
                    if not capture_element_persistent(driver, "imgCapt", reg_captcha_file, retries=5):
                        log_print("   ⚠️ Không chụp được captcha → bỏ qua lớp này")
                        failed_this_round.append(code)
                        continue

                    captcha_text = solve_captcha(reg_captcha_file)
                    if os.path.exists(reg_captcha_file):
                        os.remove(reg_captcha_file)

                    if not captcha_text:
                        log_print("   ⚠️ Không giải được captcha → thử lại lớp này")
                        failed_this_round.append(code)
                        continue

                    captcha_input = driver.find_element(By.ID, "ctl00_PlaceHolderContentArea_ctl00_ctl01_txtCaptchar")
                    captcha_input.clear()
                    captcha_input.send_keys(captcha_text)

                    driver.execute_script("try { document.getElementById('displayThongBao').innerHTML = ''; } catch(e) {}")

                    driver.execute_script(ADD_CLICK_JS)
                    try:
                        WebDriverWait(driver, 3).until(EC.alert_is_present())
                        driver.switch_to.alert.accept()
                    except:
                        pass

                    result = wait_for_thongbao_blocking(driver, max_wait=40)

                    if "thành công" in result or "đã đăng ký" in result:
                        log_print("   🎉 ĐĂNG KÝ THÀNH CÔNG!")
                    elif any(x in result for x in ["tiên quyết", "trùng", "đã học", "không thể", "hoàn tất"]):
                        log_print(f"   ❌ Không thể đăng ký: {result}")
                    else:
                        log_print(f"   ⚠️ Lỗi khác → thử lại: {result}")
                        failed_this_round.append(code)

                except Exception as e:
                    log_print(f"   ❌ Lỗi xử lý lớp {code}: {e}")
                    failed_this_round.append(code)

            remaining_codes = failed_this_round
            if remaining_codes:
                log_print(f">>> Còn lại {len(remaining_codes)} lớp chưa thành công → tiếp tục vòng sau")

        log_print(f">>> 🎉 Đã xử lý hết tất cả lớp!")
        log_print(f">>> 🏁 HOÀN THÀNH TOOL CHO {username}")

    except Exception as e:
        log_print(f">>> 💥 LỖI NGHIÊM TRỌNG: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        log_print(f"{'='*80}\n")

# ==============================================================================
# API ENDPOINTS
# ==============================================================================
@app.route('/run-auto', methods=['POST'])
def run_auto():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Không có dữ liệu JSON"}), 400

        user = data.get('user', '').strip()
        password = data.get('pass', '').strip()
        codes_str = data.get('codes', '').strip()

        if not user or not password or not codes_str:
            return jsonify({"status": "error", "message": "Thiếu user/pass/codes"}), 400

        codes_list = [c.strip() for c in codes_str.replace('\n', ',').split(',') if c.strip()]

        log_print(f"\n>>> 📥 NHẬN ĐƠN HÀNG MỚI TỪ WEB")
        log_print(f"    User: {user}")
        log_print(f"    Số lớp: {len(codes_list)}")

        thread = threading.Thread(target=run_automation_task, args=(user, password, codes_list))
        thread.daemon = True
        thread.start()

        return jsonify({
            "status": "success",
            "message": f"Đã kích hoạt tool cho {user} với {len(codes_list)} lớp"
        })

    except Exception as e:
        log_print(f"Lỗi API: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    global current_log
    return current_log, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/')
def home():
    return "<h1 style='font-family: system-ui; text-align:center; margin-top:100px;'>🌌 NEBULA DTU SNIPER SERVER<br><small>POST /run-auto | GET /status để xem log</small></h1>"

# ==============================================================================
# TẮT LOG TRUY CẬP FLASK (ĐỂ CONSOLE SẠCH, KHÔNG SPAM 200 OK)
# ==============================================================================
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==============================================================================
# KHỞI ĐỘNG
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)