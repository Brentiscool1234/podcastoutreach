import time
import threading
import os
import zipfile
import urllib.request
import json
from typing import Callable, Optional

try:
    import undetected_chromedriver as uc
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException,
    )
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        WDM_AVAILABLE = True
    except ImportError:
        WDM_AVAILABLE = False
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    WDM_AVAILABLE = False

LOGIN_URL = "https://www.matchmaker.fm/login"
BROWSE_URL = "https://www.matchmaker.fm/search"

_driver: Optional[object] = None
_driver_lock = threading.Lock()
_launching = False  # True while browser is starting up

# Selectors for matchmaker.fm — these cover the most common patterns seen in
# podcast marketplace sites; update if the site changes its class names.
_PITCH_BTN_SELECTORS = [
    "button[class*='pitch']",
    "a[class*='pitch']",
    "button[class*='apply']",
    "a[class*='apply']",
    "button[class*='contact']",
    "a[class*='contact']",
    "button[class*='request']",
    "a[class*='request']",
    "[data-testid*='pitch']",
    "[data-testid*='apply']",
]

_PITCH_TEXTAREA_SELECTORS = [
    "textarea[name*='pitch']",
    "textarea[name*='message']",
    "textarea[name*='bio']",
    "textarea[name*='body']",
    "textarea[placeholder*='pitch']",
    "textarea[placeholder*='message']",
    "textarea[placeholder*='tell']",
    "textarea",
]

_SUBMIT_BTN_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button[class*='submit']",
    "button[class*='send']",
    "button[class*='confirm']",
]


def is_available() -> bool:
    return SELENIUM_AVAILABLE


def is_launching() -> bool:
    return _launching


def _get_chrome_major_version() -> Optional[int]:
    """Read installed Chrome major version from the Windows registry."""
    import re
    # Method 1: Windows registry (most reliable)
    try:
        import winreg
        for key_path in [
            r"SOFTWARE\Google\Chrome\BLBeacon",
            r"SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon",
        ]:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                version, _ = winreg.QueryValueEx(key, "version")
                winreg.CloseKey(key)
                major = int(version.split(".")[0])
                return major
            except Exception:
                pass
    except ImportError:
        pass

    # Method 2: read version file Chrome installs alongside the exe
    import os, glob
    chrome_dirs = [
        r"C:\Program Files\Google\Chrome\Application",
        r"C:\Program Files (x86)\Google\Chrome\Application",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application"),
    ]
    for d in chrome_dirs:
        try:
            # Chrome's version folder is named after the version, e.g. "124.0.6367.82"
            versions = [f for f in os.listdir(d) if re.match(r"\d+\.\d+\.\d+\.\d+", f)]
            if versions:
                return int(versions[0].split(".")[0])
        except Exception:
            pass

    return None  # uc will try to auto-detect


def _try_launch(log_cb: Callable[[str], None]):
    version = _get_chrome_major_version()
    log_cb(f"Detected Chrome version: {version}" if version else "Chrome version not detected — using auto-detect.")

    def _stealth_options():
        opts = webdriver.ChromeOptions()
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        return opts

    # Attempt 1: correct chromedriver from Google's Chrome for Testing API.
    # This always has the right win64 binary for any Chrome version including new ones.
    try:
        log_cb("Attempt 1: fetching correct ChromeDriver from Google...")
        driver_path = _download_chromedriver_for_testing(version, log_cb)
        if driver_path:
            service = ChromeService(driver_path)
            driver = webdriver.Chrome(service=service, options=_stealth_options())
            log_cb("Chrome launched successfully.")
            return driver
    except Exception as e:
        log_cb(f"Attempt 1 failed: {type(e).__name__} — {e}")
        _kill_orphan_chrome()

    # Attempt 2: Selenium built-in driver manager
    try:
        log_cb("Attempt 2: Selenium built-in driver manager...")
        driver = webdriver.Chrome(options=_stealth_options())
        log_cb("Chrome launched (selenium built-in manager).")
        return driver
    except Exception as e:
        log_cb(f"Attempt 2 failed: {type(e).__name__}")
        _kill_orphan_chrome()

    # Attempt 3: undetected_chromedriver
    try:
        log_cb("Attempt 3: undetected_chromedriver...")
        opts = uc.ChromeOptions()
        opts.add_argument("--start-maximized")
        driver = uc.Chrome(options=opts, version_main=version)
        log_cb("Chrome launched (undetected mode).")
        return driver
    except Exception as e:
        log_cb(f"Attempt 3 failed: {type(e).__name__}")

    log_cb("ERROR: All launch attempts failed. Make sure Google Chrome is installed and up to date.")
    return None


def _kill_orphan_chrome():
    """Kill any Chrome processes left open by a failed driver launch."""
    try:
        import subprocess
        subprocess.run(
            ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def _download_chromedriver_for_testing(version: Optional[int], log_cb: Callable[[str], None]) -> Optional[str]:
    """Download the matching win64 ChromeDriver from Google's Chrome for Testing API."""
    cache_dir = os.path.join(os.path.expanduser("~"), ".chromedriver_cache")
    os.makedirs(cache_dir, exist_ok=True)

    # Check cached driver first
    if version:
        cached = os.path.join(cache_dir, f"chromedriver_{version}.exe")
        if os.path.exists(cached):
            log_cb(f"Using cached ChromeDriver for version {version}.")
            return cached

    # Fetch the known-good versions JSON from Google
    log_cb("Fetching ChromeDriver version list from Google...")
    url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())

    # Find the newest entry matching our major version
    download_url = None
    matched_version = None
    for entry in reversed(data.get("versions", [])):
        v = entry.get("version", "")
        major = int(v.split(".")[0]) if v else 0
        if version is None or major == version:
            drivers = entry.get("downloads", {}).get("chromedriver", [])
            for d in drivers:
                if d.get("platform") == "win64":
                    download_url = d["url"]
                    matched_version = v
                    break
        if download_url:
            break

    if not download_url:
        log_cb(f"No ChromeDriver found for Chrome {version} in Google's list.")
        return None

    log_cb(f"Downloading ChromeDriver {matched_version} (win64)...")
    zip_path = os.path.join(cache_dir, "chromedriver_win64.zip")
    urllib.request.urlretrieve(download_url, zip_path)

    log_cb("Extracting ChromeDriver...")
    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if name.endswith("chromedriver.exe"):
                # Extract just the exe, rename to versioned name
                data = z.read(name)
                out_name = f"chromedriver_{version or 'latest'}.exe"
                out_path = os.path.join(cache_dir, out_name)
                with open(out_path, "wb") as f:
                    f.write(data)
                log_cb(f"ChromeDriver saved to {out_path}")
                return out_path

    log_cb("Could not find chromedriver.exe inside the downloaded zip.")
    return None


def get_driver():
    return _driver


def launch_browser(log_cb: Callable[[str], None]) -> bool:
    global _driver, _launching
    if not SELENIUM_AVAILABLE:
        log_cb("ERROR: selenium / undetected-chromedriver not installed.")
        return False
    if _launching:
        log_cb("Browser is already starting up — please wait...")
        return False
    with _driver_lock:
        if _driver is not None:
            log_cb("Browser already running.")
            return True
        _launching = True
        try:
            driver = _try_launch(log_cb)
            if driver:
                _driver = driver
                _driver.get(LOGIN_URL)
                log_cb("Browser ready. Please log in. Solve any captcha manually.")
                return True
            log_cb("ERROR: Browser failed to launch. Check the log for details.")
            return False
        finally:
            _launching = False


def fill_login(email: str, password: str, log_cb: Callable[[str], None]) -> bool:
    global _driver
    if _driver is None:
        log_cb("Browser not running. Launch browser first.")
        return False
    try:
        wait = WebDriverWait(_driver, 10)
        email_field = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[id*='email']")))
        email_field.clear()
        email_field.send_keys(email)

        pw_field = _driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pw_field.clear()
        pw_field.send_keys(password)

        try:
            submit = _driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            submit.click()
            log_cb("Login form submitted. Waiting for captcha or redirect...")
        except NoSuchElementException:
            log_cb("Could not find submit button — please click Login manually in the browser.")
        return True
    except Exception as e:
        log_cb(f"ERROR filling login form: {e}. Please fill credentials manually in the browser.")
        return False


def check_login_status(log_cb: Callable[[str], None]) -> bool:
    global _driver
    if _driver is None:
        log_cb("Browser not running.")
        return False
    try:
        current_url = _driver.current_url
        if "login" not in current_url and "matchmaker.fm" in current_url:
            log_cb(f"Logged in. Current URL: {current_url}")
            return True
        try:
            _driver.find_element(By.CSS_SELECTOR,
                "[class*='avatar'], [class*='profile'], [class*='user-menu'], nav a[href*='dashboard']")
            log_cb("Login detected via page element.")
            return True
        except NoSuchElementException:
            pass
        log_cb(f"Not logged in yet. Current URL: {current_url}")
        return False
    except Exception as e:
        log_cb(f"ERROR checking login status: {e}")
        return False


def search_podcasts(categories: list, log_cb: Callable[[str], None]) -> list:
    global _driver
    if _driver is None:
        log_cb("Browser not running.")
        return []
    results = []
    try:
        log_cb("Navigating to podcast search...")
        _driver.get(BROWSE_URL)
        time.sleep(3)

        if categories:
            log_cb(f"Applying category filters: {', '.join(categories)}")
            _apply_category_filters(categories, log_cb)
            time.sleep(2)

        log_cb("Scraping podcast listings...")
        results = _scrape_listings(log_cb)
        log_cb(f"Found {len(results)} podcasts.")
    except Exception as e:
        log_cb(f"ERROR during search: {e}")
    return results


def _apply_category_filters(categories: list, log_cb: Callable[[str], None]):
    try:
        filter_buttons = _driver.find_elements(
            By.CSS_SELECTOR, "[class*='filter'], [class*='category'], [class*='tag'], [class*='genre']")
        for btn in filter_buttons:
            try:
                text = btn.text.strip().lower()
                for cat in categories:
                    if cat.lower().split(" ")[0] in text:
                        btn.click()
                        log_cb(f"  Applied filter: {btn.text.strip()}")
                        time.sleep(0.5)
                        break
            except Exception:
                pass
    except Exception as e:
        log_cb(f"Note: Could not apply filters automatically ({e}). Apply manually in browser.")


def _scrape_listings(log_cb: Callable[[str], None]) -> list:
    results = []
    try:
        card_selectors = [
            "[class*='podcast-card']",
            "[class*='show-card']",
            "[class*='result-item']",
            "[class*='podcast-item']",
            "[class*='show-item']",
            "article",
            "[class*='listing']",
            "[class*='grid-item']",
        ]
        cards = []
        for sel in card_selectors:
            cards = _driver.find_elements(By.CSS_SELECTOR, sel)
            if len(cards) > 1:
                break

        if not cards:
            log_cb("Could not auto-detect podcast cards. Try scrolling in the browser.")
            return []

        for card in cards[:50]:
            try:
                name = ""
                desc = ""
                link = ""
                category = ""

                for name_sel in ["h2", "h3", "h4", "[class*='title']", "[class*='name']", "[class*='podcast-name']"]:
                    try:
                        name = card.find_element(By.CSS_SELECTOR, name_sel).text.strip()
                        if name:
                            break
                    except Exception:
                        pass

                for desc_sel in ["p", "[class*='description']", "[class*='desc']", "[class*='bio']", "[class*='subtitle']"]:
                    try:
                        desc = card.find_element(By.CSS_SELECTOR, desc_sel).text.strip()
                        if desc:
                            break
                    except Exception:
                        pass

                for cat_sel in ["[class*='category']", "[class*='genre']", "[class*='tag']"]:
                    try:
                        category = card.find_element(By.CSS_SELECTOR, cat_sel).text.strip()
                        if category:
                            break
                    except Exception:
                        pass

                try:
                    link = card.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                except Exception:
                    pass

                # Try to find a host name separate from the podcast name
                host_name = ""
                for host_sel in ["[class*='host']", "[class*='author']", "[class*='presenter']", "[class*='by']"]:
                    try:
                        host_name = card.find_element(By.CSS_SELECTOR, host_sel).text.strip()
                        if host_name:
                            break
                    except Exception:
                        pass

                if name:
                    results.append({
                        "name": name,
                        "host_name": host_name or name,
                        "description": desc[:200],
                        "category": category,
                        "link": link,
                        "card_index": len(results),
                    })
            except Exception:
                pass
    except Exception as e:
        log_cb(f"Note: Scraping error: {e}")
    return results


def open_podcast(link: str, log_cb: Callable[[str], None]):
    global _driver
    if _driver and link:
        _driver.get(link)
        log_cb(f"Opened podcast page: {link}")


def send_pitch(
    link: str,
    pitch_text: str,
    confirm_cb: Callable[[], bool],
    log_cb: Callable[[str], None],
) -> bool:
    """
    Navigate to a podcast profile page, find the pitch/apply button,
    fill in the pitch text, then ask the user to confirm before submitting.

    confirm_cb: called on the main thread to ask the user to confirm submission.
                Should return True to submit, False to cancel.
    """
    global _driver
    if _driver is None:
        log_cb("Browser not running.")
        return False
    if not link:
        log_cb("No podcast link to navigate to.")
        return False

    try:
        log_cb(f"Navigating to podcast page: {link}")
        _driver.get(link)
        time.sleep(2)

        # Step 1: find and click the Pitch / Apply / Contact button
        pitch_btn = _find_element_by_selectors(_PITCH_BTN_SELECTORS)
        if pitch_btn is None:
            # Also search by visible text
            pitch_btn = _find_button_by_text(["pitch", "apply", "contact", "reach out", "book", "request"])

        if pitch_btn:
            log_cb("Found pitch/apply button — clicking it...")
            _driver.execute_script("arguments[0].scrollIntoView(true);", pitch_btn)
            time.sleep(0.5)
            pitch_btn.click()
            time.sleep(2)
            log_cb("Pitch form opened.")
        else:
            log_cb("Could not find a pitch button automatically. The form may already be visible, or try clicking manually in the browser.")

        # Step 2: find a textarea and fill in the pitch
        textarea = _find_element_by_selectors(_PITCH_TEXTAREA_SELECTORS)
        if textarea:
            log_cb("Found pitch textarea — filling in your pitch...")
            textarea.clear()
            # Type slowly to avoid bot detection
            for chunk in _chunk_text(pitch_text, 50):
                textarea.send_keys(chunk)
                time.sleep(0.05)
            log_cb("Pitch text filled in.")
        else:
            log_cb("Could not find a textarea automatically. Please paste your pitch manually in the browser, then confirm in the app.")

        # Step 3: ask user to confirm before submitting
        should_submit = confirm_cb()
        if not should_submit:
            log_cb("Pitch submission cancelled by user.")
            return False

        # Step 4: submit
        submit_btn = _find_element_by_selectors(_SUBMIT_BTN_SELECTORS)
        if submit_btn is None:
            submit_btn = _find_button_by_text(["submit", "send", "send pitch", "confirm", "apply"])

        if submit_btn:
            log_cb("Submitting pitch...")
            _driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
            time.sleep(0.3)
            submit_btn.click()
            time.sleep(2)

            # Check for success indicators
            success = _check_submission_success(log_cb)
            if success:
                log_cb("Pitch submitted successfully!")
            else:
                log_cb("Pitch submitted — check the browser to confirm. A captcha may have appeared.")
            return True
        else:
            log_cb("Could not find submit button. Please click Submit manually in the browser.")
            return False

    except Exception as e:
        log_cb(f"ERROR during pitch submission: {e}")
        return False


def _find_element_by_selectors(selectors: list):
    """Try a list of CSS selectors and return the first visible matching element."""
    for sel in selectors:
        try:
            elements = _driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elements:
                if el.is_displayed() and el.is_enabled():
                    return el
        except Exception:
            pass
    return None


def _find_button_by_text(keywords: list):
    """Find a clickable element whose visible text contains any keyword."""
    try:
        clickables = _driver.find_elements(By.CSS_SELECTOR, "button, a, [role='button']")
        for el in clickables:
            try:
                if not el.is_displayed():
                    continue
                text = el.text.strip().lower()
                for kw in keywords:
                    if kw in text:
                        return el
            except Exception:
                pass
    except Exception:
        pass
    return None


def _check_submission_success(log_cb: Callable[[str], None]) -> bool:
    """Look for success/thank-you indicators after submission."""
    try:
        success_selectors = [
            "[class*='success']",
            "[class*='thank']",
            "[class*='confirmation']",
            "[class*='sent']",
            "[role='alert']",
        ]
        for sel in success_selectors:
            try:
                el = _driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    log_cb(f"Success indicator found: '{el.text[:80]}'")
                    return True
            except Exception:
                pass
        # Also check URL change to a success/confirmation page
        if any(kw in _driver.current_url for kw in ["success", "confirm", "thank", "sent"]):
            return True
    except Exception:
        pass
    return False


def _chunk_text(text: str, size: int):
    for i in range(0, len(text), size):
        yield text[i:i + size]


def close_browser(log_cb: Callable[[str], None]):
    global _driver
    with _driver_lock:
        if _driver is not None:
            try:
                _driver.quit()
            except Exception:
                pass
            _driver = None
            log_cb("Browser closed.")
        else:
            log_cb("No browser running.")
