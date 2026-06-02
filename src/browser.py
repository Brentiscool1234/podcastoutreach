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
BROWSE_URL = "https://www.matchmaker.fm/search/shows"

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
            if not driver:
                log_cb("ERROR: Browser failed to launch. Check the log for details.")
                return False
            # Save driver immediately so the browser isn't orphaned if navigation fails
            _driver = driver
            time.sleep(1)
            try:
                log_cb(f"Navigating to {LOGIN_URL} ...")
                _driver.get(LOGIN_URL)
                log_cb("Browser ready. Please log in. Solve any captcha manually.")
            except Exception as e:
                log_cb(f"Navigation error (browser is still open): {e}")
            return True
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


def search_podcasts(categories: list, log_cb: Callable[[str], None], max_results: int = 50) -> list:
    global _driver
    if _driver is None:
        log_cb("Browser not running.")
        return []
    all_results = []
    try:
        def _paginate_and_scrape(start_url: str):
            _driver.get(start_url)
            time.sleep(3)
            while True:
                found = _scrape_listings(log_cb, max_per_page=max_results)
                existing_links = {r["link"] for r in all_results}
                for r in found:
                    if r["link"] not in existing_links:
                        all_results.append(r)
                        existing_links.add(r["link"])
                if len(all_results) >= max_results:
                    break
                # Look for next page
                next_btn = None
                for sel in [
                    "a[aria-label='Next page']",
                    "a[rel='next']",
                    "li.next a",
                    ".pagination li:last-child a",
                    "button[aria-label*='next' i]",
                ]:
                    try:
                        els = _driver.find_elements(By.CSS_SELECTOR, sel)
                        for el in els:
                            if el.is_displayed() and el.is_enabled():
                                next_btn = el
                                break
                        if next_btn:
                            break
                    except Exception:
                        pass
                if next_btn:
                    try:
                        next_btn.click()
                        time.sleep(3)
                    except Exception:
                        break
                else:
                    break

        if categories:
            for cat in categories:
                url = f"{BROWSE_URL}?category={urllib.request.quote(cat)}"
                log_cb(f"Searching category: {cat}")
                _paginate_and_scrape(url)
                log_cb(f"  Total so far: {len(all_results)}")
                if len(all_results) >= max_results:
                    break
        else:
            log_cb("Navigating to podcast search (no category filter)...")
            _paginate_and_scrape(BROWSE_URL)

        all_results = all_results[:max_results]
        log_cb(f"Total unique podcasts found: {len(all_results)}")
    except Exception as e:
        log_cb(f"ERROR during search: {e}")
    return all_results


_NAV_NOISE = {"find a show", "browse", "search", "podcast", "matchmaker"}


def _scrape_listings(log_cb: Callable[[str], None], max_per_page: int = 50) -> list:
    """Scrape podcast cards from the current search results page."""
    results = []
    try:
        wait = WebDriverWait(_driver, 8)
        try:
            wait.until(EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-trigger='find-shows-profile']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".profile-avatar-wrapper")),
            ))
        except TimeoutException:
            log_cb("Page may still be loading or no results found.")

        # Primary: cards with the specific data-trigger attribute
        cards = _driver.find_elements(By.CSS_SELECTOR, "a[data-trigger='find-shows-profile'][href*='/show/']")
        # Fallback: any anchor linking to /show/
        if not cards:
            cards = _driver.find_elements(By.CSS_SELECTOR, "a[href*='/show/']")

        seen = set()
        for card in cards:
            if len(results) >= max_per_page:
                break
            try:
                href = card.get_attribute("href") or ""
                if not href or href in seen:
                    continue
                seen.add(href)

                # Extract name — try selectors inside the card anchor
                name = ""
                for sel in [
                    ".profile-header", "h2", "h3", "h1", "h4",
                    "[class*='Header']", "[class*='title']", "[class*='name']",
                ]:
                    try:
                        el = card.find_element(By.CSS_SELECTOR, sel)
                        t = el.text.strip()
                        if t:
                            name = t
                            break
                    except Exception:
                        pass

                if not name:
                    # Fallback: first non-empty non-noise line of card text
                    for line in card.text.splitlines():
                        line = line.strip()
                        if line and line.lower() not in _NAV_NOISE:
                            name = line
                            break

                if not name:
                    continue

                # Description
                desc = ""
                for sel in [".profile-card__pitch", "[class*='pitch']", "p"]:
                    try:
                        el = card.find_element(By.CSS_SELECTOR, sel)
                        t = el.text.strip()
                        if t:
                            desc = t[:200]
                            break
                    except Exception:
                        pass

                # Category
                category = ""
                try:
                    for sel in [".profile-pill", "[class*='pill']", "[class*='categor']"]:
                        pills = card.find_elements(By.CSS_SELECTOR, sel)
                        if pills:
                            category = ", ".join(p.text.strip() for p in pills[:3] if p.text.strip())
                            break
                except Exception:
                    pass

                results.append({
                    "name": name,
                    "host_name": name,
                    "description": desc,
                    "category": category,
                    "link": href,
                    "card_index": len(results),
                })
            except Exception:
                pass
    except Exception as e:
        log_cb(f"Scraping error: {e}")
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
        time.sleep(3)

        # Step 1: click Send Message button on the podcast profile
        # Try the known data-trigger attribute first (confirmed from matchmaker.fm DOM)
        pitch_btn = _find_element_by_selectors([
            "button[data-trigger='show-profile-message-send-intent']",
            *_PITCH_BTN_SELECTORS,
        ])
        if pitch_btn is None:
            pitch_btn = _find_button_by_text(["send a message", "send message", "pitch", "apply", "contact", "reach out", "book", "request"])

        if pitch_btn:
            log_cb("Found message button — clicking...")
            _driver.execute_script("arguments[0].scrollIntoView(true);", pitch_btn)
            time.sleep(0.5)
            pitch_btn.click()
            time.sleep(2)
        else:
            log_cb("Could not find message button — form may already be visible.")

        # Step 2: select Guest profile from the react-select dropdown
        _select_guest_profile(log_cb)

        # Step 3: wait for textarea to become enabled (it's disabled until profile selected)
        log_cb("Waiting for message textarea to become active...")
        wait = WebDriverWait(_driver, 10)
        try:
            textarea = wait.until(EC.element_to_be_clickable((By.ID, "message")))
        except TimeoutException:
            textarea = _find_element_by_selectors(_PITCH_TEXTAREA_SELECTORS)

        if textarea:
            log_cb("Filling in pitch text...")
            _driver.execute_script("arguments[0].scrollIntoView(true);", textarea)
            _driver.execute_script("arguments[0].removeAttribute('disabled');", textarea)
            textarea.click()
            textarea.clear()
            for chunk in _chunk_text(pitch_text, 50):
                textarea.send_keys(chunk)
                time.sleep(0.04)
            log_cb("Pitch text filled.")
        else:
            log_cb("WARNING: Could not find textarea — please paste pitch manually in the browser.")

        # Step 4: ask user to confirm (captcha may need solving) — skip in automated mode
        if confirm_cb is not None:
            should_submit = confirm_cb()
        else:
            should_submit = True

        if not should_submit:
            log_cb("Pitch submission cancelled.")
            return False

        # Step 5: click the Send button (exact text from modal)
        submit_btn = _find_button_by_text(["send"])
        if submit_btn is None:
            submit_btn = _find_element_by_selectors(_SUBMIT_BTN_SELECTORS)

        if submit_btn:
            log_cb("Sending pitch...")
            _driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
            time.sleep(0.3)
            submit_btn.click()
            time.sleep(2)
            success = _check_submission_success(log_cb)
            log_cb("Pitch sent successfully!" if success else "Pitch sent — verify in browser.")
            return True
        else:
            log_cb("Could not find Send button — please click it manually in the browser.")
            return False

    except Exception as e:
        log_cb(f"ERROR during pitch submission: {e}")
        return False


def _select_guest_profile(log_cb: Callable[[str], None]):
    """Select the Guest profile from the react-select dropdown in the send-message modal."""
    try:
        wait = WebDriverWait(_driver, 8)

        # The dropdown control — try the exact class first, then the generic react-select pattern
        control = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".css-1sq9woi-control, [class*='-control']")))
        control.click()
        time.sleep(0.8)

        # react-select renders options into a menu with role="option"
        options = _driver.find_elements(By.CSS_SELECTOR, "[class*='-option'], [role='option']")
        for opt in options:
            try:
                if opt.is_displayed() and "guest" in opt.text.lower():
                    opt.click()
                    log_cb(f"Selected profile: {opt.text.strip()}")
                    time.sleep(0.5)
                    return
            except Exception:
                pass

        # Fallback: type "guest" into the react-select input to filter, then pick first result
        try:
            rs_input = _driver.find_element(By.CSS_SELECTOR, "input[role='combobox']")
            rs_input.send_keys("guest")
            time.sleep(0.8)
            options = _driver.find_elements(By.CSS_SELECTOR, "[class*='-option'], [role='option']")
            if options:
                options[0].click()
                log_cb(f"Selected profile via search: {options[0].text.strip()}")
                time.sleep(0.5)
                return
        except Exception:
            pass

        log_cb("Could not auto-select guest profile — please select it manually in the browser.")
    except Exception as e:
        log_cb(f"Profile selection error ({e}) — please select manually.")


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
