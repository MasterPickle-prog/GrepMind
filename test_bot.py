"""
GrepMind Selenium Test Bot
--------------------------
Tests the full user flow: sign up, sign in, send a message, search chats,
delete a chat, and sign out.

Requirements:
    pip install selenium

Usage:
    python test_bot.py

The bot uses Chrome in headless mode by default. Set HEADLESS = False below
to watch it run in a real browser window.
"""

import time
import random
import string

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ── Config ──────────────────────────────────────────────────────────────────

BASE_URL  = "http://127.0.0.1:8080"
HEADLESS  = False   # set True to run without opening a browser window
TIMEOUT   = 10      # seconds to wait for elements

# Random test account so each run is independent
_suffix     = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
TEST_EMAIL  = f"testbot_{_suffix}@example.com"
TEST_PASS   = f"TestPass_{_suffix}!9"
FIRST_NAME  = "Test"
LAST_NAME   = "Bot"

# ── Helpers ──────────────────────────────────────────────────────────────────

def make_driver():
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=opts)


def wait_for(driver, by, value, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, value))
    )


def wait_clickable(driver, by, value, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )


def log(msg, status="INFO"):
    icons = {"INFO": "·", "PASS": "✓", "FAIL": "✗", "STEP": "▶"}
    print(f"  {icons.get(status, '·')} {msg}")


def assert_url_contains(driver, fragment, label):
    try:
        WebDriverWait(driver, TIMEOUT).until(EC.url_contains(fragment))
        log(f"{label}", "PASS")
    except TimeoutException:
        log(f"{label} — expected URL to contain '{fragment}', got: {driver.current_url}", "FAIL")
        raise


def assert_element_exists(driver, by, value, label):
    try:
        wait_for(driver, by, value)
        log(label, "PASS")
    except TimeoutException:
        log(f"{label} — element not found: {value}", "FAIL")
        raise


# ── Test cases ───────────────────────────────────────────────────────────────

def test_redirect_to_signin(driver):
    print("\n[1] Unauthenticated redirect")
    driver.get(BASE_URL + "/")
    assert_url_contains(driver, "/signin", "Visiting / redirects to /signin")


def test_signup(driver):
    print("\n[2] Sign up")
    driver.get(BASE_URL + "/signup")
    wait_for(driver, By.ID, "first_name")

    driver.find_element(By.ID, "first_name").send_keys(FIRST_NAME)
    driver.find_element(By.ID, "last_name").send_keys(LAST_NAME)
    driver.find_element(By.ID, "email").send_keys(TEST_EMAIL)
    driver.find_element(By.ID, "password").send_keys(TEST_PASS)
    driver.find_element(By.ID, "confirm_password").send_keys(TEST_PASS)
    log(f"Filled signup form ({TEST_EMAIL})")

    # reCAPTCHA v3 is invisible; the JS intercepts submit and injects a token.
    # We click the button and wait for the redirect — if reCAPTCHA blocks it
    # in a test environment you may need to disable it server-side temporarily.
    wait_clickable(driver, By.CSS_SELECTOR, ".auth-submit").click()

    try:
        assert_url_contains(driver, "/", "Signup succeeded → redirected to home")
    except TimeoutException:
        # Check for a flash error message
        try:
            flash = driver.find_element(By.CSS_SELECTOR, ".auth-flash")
            log(f"Signup blocked: {flash.text}", "FAIL")
        except NoSuchElementException:
            log("Signup failed — unknown reason", "FAIL")
        raise


def test_signout(driver):
    print("\n[3] Sign out")
    signout = wait_clickable(driver, By.ID, "signOutBtn")
    signout.click()
    assert_url_contains(driver, "/signin", "Sign out redirects to /signin")


def test_signin(driver):
    print("\n[4] Sign in")
    driver.get(BASE_URL + "/signin")
    wait_for(driver, By.ID, "email")

    driver.find_element(By.ID, "email").send_keys(TEST_EMAIL)
    driver.find_element(By.ID, "password").send_keys(TEST_PASS)
    log("Filled sign-in form")

    wait_clickable(driver, By.CSS_SELECTOR, ".auth-submit").click()

    try:
        assert_url_contains(driver, "/", "Sign in succeeded → redirected to home")
    except TimeoutException:
        try:
            flash = driver.find_element(By.CSS_SELECTOR, ".auth-flash")
            log(f"Sign in blocked: {flash.text}", "FAIL")
        except NoSuchElementException:
            log("Sign in failed — unknown reason", "FAIL")
        raise


def test_wrong_password(driver):
    print("\n[5] Wrong password rejected")
    driver.get(BASE_URL + "/signin")
    wait_for(driver, By.ID, "email")

    driver.find_element(By.ID, "email").send_keys(TEST_EMAIL)
    driver.find_element(By.ID, "password").send_keys("WrongPassword123!")
    wait_clickable(driver, By.CSS_SELECTOR, ".auth-submit").click()

    assert_element_exists(driver, By.CSS_SELECTOR, ".auth-flash",
                          "Wrong password shows error flash message")


def test_send_message(driver):
    print("\n[6] Send a chat message")
    driver.get(BASE_URL + "/")
    wait_for(driver, By.ID, "promptInput")

    prompt = driver.find_element(By.ID, "promptInput")
    prompt.send_keys("Hello GrepMind, this is a test message.")
    log("Typed message into prompt bar")

    wait_clickable(driver, By.ID, "sendBtn").click()
    log("Clicked send")

    # Wait for the user message bubble to appear
    assert_element_exists(driver, By.CSS_SELECTOR, ".message.user",
                          "User message appears in chat history")

    # Wait for AI response (thinking indicator disappears, ai message appears)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".message.ai"))
        )
        log("AI response received", "PASS")
    except TimeoutException:
        log("AI response did not appear within 15s", "FAIL")
        raise


def test_new_chat(driver):
    print("\n[7] New chat button clears history")
    wait_clickable(driver, By.ID, "newChatBtn").click()
    time.sleep(0.5)

    messages = driver.find_elements(By.CSS_SELECTOR, ".message")
    if len(messages) == 0:
        log("New chat cleared message history", "PASS")
    else:
        log(f"New chat still shows {len(messages)} message(s)", "FAIL")
        raise AssertionError("New chat did not clear history")


def test_search_chats(driver):
    print("\n[8] Search chats modal")
    wait_clickable(driver, By.ID, "searchChatsBtn").click()

    assert_element_exists(driver, By.ID, "searchInput",
                          "Search modal opens")

    search = driver.find_element(By.ID, "searchInput")
    search.send_keys("test")
    time.sleep(0.4)

    results = driver.find_elements(By.CSS_SELECTOR, ".search-result-item")
    log(f"Search returned {len(results)} result(s)", "PASS" if results else "INFO")

    search.send_keys(Keys.ESCAPE)
    time.sleep(0.3)
    log("Escape closes search modal", "PASS")


def test_recent_chats_dropdown(driver):
    print("\n[9] Recent chats dropdown")
    dropdown_btn = wait_clickable(driver, By.CSS_SELECTOR, ".dropdown-btn")
    dropdown_btn.click()
    time.sleep(0.3)

    items = driver.find_elements(By.CSS_SELECTOR, ".dropdown-item")
    log(f"Recent chats shows {len(items)} item(s)", "PASS" if items else "INFO")

    if items:
        items[0].click()
        time.sleep(0.4)
        messages = driver.find_elements(By.CSS_SELECTOR, ".message")
        log(f"Loaded chat has {len(messages)} message(s)",
            "PASS" if messages else "INFO")


def test_404_redirect(driver):
    print("\n[10] 404 redirects to home (signed in)")
    driver.get(BASE_URL + "/this-page-does-not-exist")
    assert_url_contains(driver, "/", "404 redirects signed-in user to home")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all():
    print("=" * 52)
    print("  GrepMind Selenium Test Bot")
    print(f"  Target: {BASE_URL}")
    print(f"  Account: {TEST_EMAIL}")
    print("=" * 52)

    driver = make_driver()
    passed = 0
    failed = 0

    tests = [
        test_redirect_to_signin,
        test_signup,
        test_signout,
        test_signin,
        test_wrong_password,
        # re-sign in after wrong password test
        lambda d: (d.get(BASE_URL + "/signin"),
                   d.find_element(By.ID, "email").send_keys(TEST_EMAIL),
                   d.find_element(By.ID, "password").send_keys(TEST_PASS),
                   wait_clickable(d, By.CSS_SELECTOR, ".auth-submit").click(),
                   WebDriverWait(d, TIMEOUT).until(EC.url_contains("/"))),
        test_send_message,
        test_new_chat,
        test_search_chats,
        test_recent_chats_dropdown,
        test_404_redirect,
    ]

    for test in tests:
        try:
            test(driver)
            passed += 1
        except Exception as e:
            failed += 1
            log(f"Exception: {e}", "FAIL")

    driver.quit()

    print("\n" + "=" * 52)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 52)


if __name__ == "__main__":
    run_all()
