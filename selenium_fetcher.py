#!/usr/bin/env python3
"""
Selenium-based fetcher to get fully rendered HTML (including JS content)
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def fetch_rendered_html(url: str, wait_time: int = 5, timeout: int = 20) -> str:
    """Fetch fully rendered HTML using headless Chrome"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get(url)
        # Wait for main content to load (tune selector as needed)
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
            )
        except Exception:
            pass
        time.sleep(wait_time)  # Let JS finish
        html = driver.page_source
        return html
    finally:
        driver.quit()

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("Usage: python selenium_fetcher.py <url>")
        exit(1)
    html = fetch_rendered_html(url)
    print(html[:2000]) 