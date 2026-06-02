import time
import threading
from typing import Callable, Optional

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

LOGIN_URL = "https://www.matchmaker.fm/login"
BROWSE_URL = "https://www.matchmaker.fm/search"

_driver: Optional[object] = None
_driver_lock = threading.Lock()


def is_available() -> bool:
    return SELENIUM_AVAILABLE


def get_driver():
    return _driver


def launch_browser(log_cb: Callable[[str], None]) -> bool:
    global _driver
    if not SELENIUM_AVAILABLE:
        log_cb("ERROR: selenium / undetected-chromedriver not installed.")
        return False
    with _driver_lock:
        if _driver is not None:
            log_cb("Browser already running.")
            return True
        try:
            log_cb("Launching Chrome browser...")
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            driver = uc.Chrome(options=options)
            driver.get(LOGIN_URL)
            _driver = driver
            log_cb("Browser launched. Please log in. Solve any captcha manually.")
            return True
        except Exception as e:
            log_cb(f"ERROR launching browser: {e}")
            return False


def fill_login(email: str, password: str, log_cb: Callable[[str], None]) -> bool:
    global _driver
    if _driver is None:
        log_cb("Browser not running. Launch browser first.")
        return False
    try:
        wait = WebDriverWait(_driver, 10)
        email_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[id*='email']")))
        email_field.clear()
        email_field.send_keys(email)

        pw_field = _driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pw_field.clear()
        pw_field.send_keys(password)

        # Try to find and click submit button
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
        # matchmaker.fm redirects away from /login when logged in
        if "login" not in current_url and "matchmaker.fm" in current_url:
            log_cb(f"Appears logged in. Current URL: {current_url}")
            return True
        # Check for user profile elements
        try:
            _driver.find_element(By.CSS_SELECTOR, "[class*='avatar'], [class*='profile'], [class*='user-menu'], nav a[href*='dashboard']")
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
    """Navigate to search page, apply category filters, and scrape results."""
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
    """Best-effort category filter application — matchmaker.fm UI may vary."""
    try:
        # Look for filter/category elements generically
        filter_buttons = _driver.find_elements(By.CSS_SELECTOR, "[class*='filter'], [class*='category'], [class*='tag']")
        for btn in filter_buttons:
            try:
                text = btn.text.strip().lower()
                for cat in categories:
                    if cat.lower() in text:
                        btn.click()
                        log_cb(f"  Applied filter: {btn.text.strip()}")
                        time.sleep(0.5)
                        break
            except Exception:
                pass
    except Exception as e:
        log_cb(f"Note: Could not apply filters automatically ({e}). Apply manually in browser.")


def _scrape_listings(log_cb: Callable[[str], None]) -> list:
    """Scrape podcast cards/listings from current page."""
    results = []
    try:
        # Generic selectors for podcast cards — adapt if matchmaker.fm uses specific classes
        card_selectors = [
            "[class*='podcast-card']",
            "[class*='show-card']",
            "[class*='result-item']",
            "article",
            "[class*='listing']",
        ]
        cards = []
        for sel in card_selectors:
            cards = _driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                break

        for card in cards[:50]:  # limit to 50
            try:
                name = ""
                desc = ""
                category = ""
                link = ""

                # Try common name patterns
                for name_sel in ["h2", "h3", "h4", "[class*='title']", "[class*='name']"]:
                    try:
                        name = card.find_element(By.CSS_SELECTOR, name_sel).text.strip()
                        if name:
                            break
                    except Exception:
                        pass

                # Description
                for desc_sel in ["p", "[class*='description']", "[class*='desc']", "[class*='bio']"]:
                    try:
                        desc = card.find_element(By.CSS_SELECTOR, desc_sel).text.strip()
                        if desc:
                            break
                    except Exception:
                        pass

                # Link
                try:
                    link = card.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                except Exception:
                    pass

                if name:
                    results.append({"name": name, "description": desc[:200], "category": category, "link": link, "card_index": len(results)})
            except Exception:
                pass
    except Exception as e:
        log_cb(f"Note: Scraping error: {e}")
    return results


def open_podcast(link: str, log_cb: Callable[[str], None]):
    global _driver
    if _driver and link:
        _driver.get(link)
        log_cb(f"Opened: {link}")


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
