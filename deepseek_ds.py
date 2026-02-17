import time
import random
import threading
import traceback
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options

# ─────────────────────────────────────────────────────────────
#  ACCOUNT DICTIONARY  –  add / remove accounts freely
# ─────────────────────────────────────────────────────────────
# ACCOUNTS = {
#     "account1@gmail.com":  "Password3Here",
#     "account2@gmail.com":  "Password2Here",
# }
ACCOUNTS = {
    "roadlyft+a@gmail.com": "werze2-durqyh-xYszif",
    "roadlyft+b@gmail.com": "werze2-durqyh-xYszif",
    "roadlyft+c@gmail.com": "werze2-durqyh-xYszif",
    "roadlyft+d@gmail.com": "werze2-durqyh-xYszif",
    "roadlyft+e@gmail.com": "werze2-durqyh-xYszif",
    # "roadlyft+f@gmail.com": "werze2-durqyh-xYszif",
}

app = Flask(__name__)
pool_lock = threading.Lock()
account_pool: dict = {}


# ── Driver / login ─────────────────────────────────────────────

def make_driver():
    opts = Options()
    # opts.add_argument("--headless=new")   # uncomment for headless mode
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=opts)


def login_account(email: str, password: str):
    print(f"[POOL] Spawning: {email}")
    driver = make_driver()
    wait   = WebDriverWait(driver, 30)
    try:
        driver.get("https://chat.deepseek.com")

        email_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Phone number / email address']")
        ))
        email_input.send_keys(email)
        driver.find_element(By.XPATH, "//input[@placeholder='Password']").send_keys(password)
        driver.find_element(By.XPATH, "//button[.//span[normalize-space()='Log in']]").click()

        print(f"[POOL]   Logging in {email} …")
        time.sleep(5)

        # Toggle 1 – DeepThink: MUST be selected
        t1 = wait.until(EC.presence_of_element_located(
            (By.XPATH, "(//div[@role='button' and contains(@class,'ds-toggle-button') and contains(@class,'ds-toggle-button--md')])[1]")
        ))
        if "ds-toggle-button--selected" not in t1.get_attribute("class"):
            driver.execute_script("arguments[0].click();", t1)

        # Toggle 2 – Search: must NOT be selected
        t2 = wait.until(EC.presence_of_element_located(
            (By.XPATH, "(//div[@role='button' and contains(@class,'ds-toggle-button') and contains(@class,'ds-toggle-button--md')])[2]")
        ))
        if "ds-toggle-button--selected" in t2.get_attribute("class"):
            driver.execute_script("arguments[0].click();", t2)

        print(f"[POOL]   {email} ready ✅")
        return {"driver": driver, "status": "idle", "wait": WebDriverWait(driver, 30), "lock": threading.Lock()}

    except Exception:
        print(f"[POOL]   FAILED {email}:\n{traceback.format_exc()}")
        try: driver.quit()
        except: pass
        return None


def spawn_all_accounts():
    threads = []
    def _spawn(email, password):
        slot = login_account(email, password)
        with pool_lock:
            account_pool[email] = slot if slot else {
                "driver": None, "status": "error", "wait": None, "lock": threading.Lock()
            }
    for email, password in ACCOUNTS.items():
        t = threading.Thread(target=_spawn, args=(email, password), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


# ── Pool helpers ───────────────────────────────────────────────

def pick_idle_account():
    with pool_lock:
        idle = [e for e, s in account_pool.items() if s["status"] == "idle"]
    return random.choice(idle) if idle else None

def mark_busy(email):
    with pool_lock: account_pool[email]["status"] = "busy"

def mark_idle(email):
    with pool_lock: account_pool[email]["status"] = "idle"

def reset_to_new_chat(slot):
    try:
        btn = slot["wait"].until(EC.element_to_be_clickable(
            (By.XPATH, "//div[@tabindex='0' and .//span[normalize-space()='New chat']]")
        ))
        slot["driver"].execute_script("arguments[0].click();", btn)
        time.sleep(1)
    except: pass


# ── Core task ──────────────────────────────────────────────────

def send_prompt_and_get_response(email: str, prompt: str) -> str:
    slot        = account_pool[email]
    driver      = slot["driver"]
    wait        = slot["wait"]
    prompt_wait = WebDriverWait(driver, 1000)
    actions     = ActionChains(driver)
    chunk_size = 500
    textarea = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//textarea[@placeholder='Message DeepSeek']")
    ))
    textarea.clear()
    textarea.send_keys(" ")
    time.sleep(1)
    driver.execute_script("arguments[0].value = arguments[1];", textarea, prompt)
    time.sleep(1)
    textarea.send_keys(" ")


    submit_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//div[@role='button' and contains(@class,'_7436101') and contains(@class,'ds-icon-button--l') and @aria-disabled='false']")
    ))
    driver.execute_script("arguments[0].click();", submit_btn)
    print(f"[{email}] Prompt submitted ✅")
    time.sleep(1)
    try:
        icon = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class,'ds-icon') and contains(@class,'_970ac5e')]")
            )
        )

        # Optional: verify it is visible & clickable
        if icon.is_displayed() and icon.is_enabled():
            driver.execute_script("arguments[0].click();", icon)
            print("Icon clicked ✅")

    except TimeoutException:
        print("Icon did not appear ❌")


    while True:
        try:
            prompt_wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class,'ds-flex') and contains(@class,'_965abe9')]")
            ))
            time.sleep(1)
            continue_buttons = driver.find_elements(
                By.XPATH,
                "//button[.//span[normalize-space()='Continue'] and @aria-disabled='false']"
            )
            if continue_buttons:
                btn = continue_buttons[0]
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                actions.move_to_element(btn).pause(0.2).click().perform()
                wait.until(EC.staleness_of(btn))
                continue
            else:
                print(f"[{email}] Response complete ✅")
                break
        except TimeoutException:
            break
        except StaleElementReferenceException:
            continue

    paras = driver.find_elements(
        By.XPATH,
        "(//div[contains(@class,'_4f9bf79')]//div[contains(@class,'ds-markdown')])[last()]//p"
    )
    response_text = "\n".join(p.text for p in paras if p.text.strip())
    reset_to_new_chat(slot)
    return response_text


# ── Flask routes ───────────────────────────────────────────────

@app.route("/prompt", methods=["POST"])
def handle_prompt():
    data   = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Missing or empty 'prompt' field"}), 400

    email = pick_idle_account()
    if email is None:
        return jsonify({"error": "All accounts are currently busy. Please retry later.", "code": 503}), 503

    slot     = account_pool[email]
    acquired = slot["lock"].acquire(blocking=False)
    if not acquired:
        return jsonify({"error": "All accounts are currently busy. Please retry later.", "code": 503}), 503

    mark_busy(email)
    print(f"[SERVER] Assigned to: {email}")
    try:
        text = send_prompt_and_get_response(email, prompt)
        return jsonify({"account": email, "response": text}), 200
    except Exception:
        print(f"[SERVER] Error on {email}:\n{traceback.format_exc()}")
        with pool_lock: account_pool[email]["status"] = "error"
        return jsonify({"error": "Driver error. Try again.", "code": 500}), 500
    finally:
        mark_idle(email)
        slot["lock"].release()


@app.route("/status", methods=["GET"])
def pool_status():
    with pool_lock:
        statuses = {e: s["status"] for e, s in account_pool.items()}
    return jsonify(statuses), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ── Entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  DeepSeek Account-Pool Flask Server")
    print("=" * 55)
    print(f"  Spawning {len(ACCOUNTS)} account(s) in parallel…")
    spawn_all_accounts()
    ready = sum(1 for s in account_pool.values() if s["status"] == "idle")
    print(f"  {ready}/{len(ACCOUNTS)} account(s) ready.")
    print("  Listening on  http://0.0.0.0:5000")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5500, threaded=True)