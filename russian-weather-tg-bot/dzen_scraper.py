# -*- coding: utf-8 -*-
"""
Скрипт загрузки новостей из Дзена по городу: браузер (Playwright) + опционально 2Captcha.

Бесплатно: капчу Yandex SmartCaptcha надёжно решить нельзя — бесплатных сервисов нет.
Мы уменьшаем появление капчи за счёт «стелс»-настроек браузера и человечного поведения.
Платно: 2Captcha (CAPTCHA_2CAPTCHA_API_KEY в .env).

Запуск: python dzen_scraper.py "Челябинск" 5
"""
import asyncio
import logging
import os
import random
import re
import sys
from typing import List, Tuple
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Опционально: API-ключ 2Captcha (платный). Бесплатного решения для SmartCaptcha нет.
CAPTCHA_2CAPTCHA_API_KEY = (os.getenv("CAPTCHA_2CAPTCHA_API_KEY") or os.getenv("2CAPTCHA_API_KEY") or "").strip()

# Скрипт, который скрывает признаки автоматизации (меньше шанс получить капчу)
STEALTH_JS = """
(function() {
    try {
        Object.defineProperty(navigator, 'webdriver', { get: function() { return undefined; }, configurable: true });
        if (window.chrome) window.chrome.runtime = {};
    } catch (e) {}
})();
"""


async def _solve_yandex_smartcaptcha(page_url: str, sitekey: str) -> str:
    """Решает Yandex SmartCaptcha через 2Captcha. Возвращает токен или пустую строку."""
    if not CAPTCHA_2CAPTCHA_API_KEY:
        return ""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://2captcha.com/in.php",
                data={
                    "key": CAPTCHA_2CAPTCHA_API_KEY,
                    "method": "yandex",
                    "sitekey": sitekey,
                    "pageurl": page_url,
                },
            ) as resp:
                text = await resp.text()
            if "OK|" not in text:
                logger.warning("2Captcha in.php: %s", text[:200])
                return ""
            captcha_id = text.split("|", 1)[1].strip()
            for _ in range(24):
                await asyncio.sleep(5)
                async with session.get(
                    "https://2captcha.com/res.php",
                    params={"key": CAPTCHA_2CAPTCHA_API_KEY, "action": "get", "id": captcha_id},
                ) as r:
                    body = await r.text()
                if "OK|" in body:
                    return body.split("|", 1)[1].strip()
                if "CAPCHA_NOT_READY" not in body:
                    break
    except Exception as e:
        logger.warning("2Captcha solve: %s", e)
    return ""


async def fetch_dzen_news_for_city(city_name: str, limit: int = 5) -> List[Tuple[str, str]]:
    """
    Загружает новости из Дзена по названию города через браузер (Playwright).
    При капче пробует 2Captcha, если задан CAPTCHA_2CAPTCHA_API_KEY.
    Возвращает список (заголовок, ссылка).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright не установлен: pip install playwright && playwright install chromium")
        return []

    url = f"https://dzen.ru/news/search?query={quote(city_name, safe='')}"
    out: List[Tuple[str, str]] = []

    # Аргументы, чтобы браузер меньше определялся как бот (бесплатный способ реже получать капчу)
    stealth_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
        "--window-position=0,0",
        "--ignore-certificate-errors",
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=stealth_args)
        context = await browser.new_context(
            locale="ru-RU",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            timezone_id="Europe/Moscow",
            extra_http_headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            },
        )
        page = await context.new_page()
        await page.add_init_script(STEALTH_JS)
        try:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(random.uniform(2.5, 4.5))

            html = await page.content()
            if "робот" in html.lower() or "не робот" in html or "smartcaptcha" in html.lower():
                sitekey = ""
                for m in re.finditer(r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']', html, re.I):
                    sitekey = m.group(1)
                    break
                if not sitekey:
                    for m in re.finditer(r'data-sitekey=["\']([^"\']+)["\']', html, re.I):
                        sitekey = m.group(1)
                        break
                if sitekey and CAPTCHA_2CAPTCHA_API_KEY:
                    token = await _solve_yandex_smartcaptcha(url, sitekey)
                    if token:
                        await page.evaluate(
                            """(token) => {
                                const inp = document.querySelector('input[name="smart-token"]') || document.querySelector('[name="smart-token"]');
                                if (inp) inp.value = token;
                                if (window.smartCaptcha && typeof window.smartCaptcha.render === 'function') { try { window.smartCaptcha.render(token); } catch(e) {} }
                            }""",
                            token,
                        )
                        await asyncio.sleep(2)
                        html = await page.content()

            seen = set()
            # Ссылки на новости: карточки и списки
            links = await page.evaluate(
                """() => {
                const a = document.querySelectorAll('a[href*="dzen.ru"], a[href*="yandex.ru"], a[href*="/news/"]');
                return Array.from(a).slice(0, 30).map(el => ({
                    href: el.href,
                    text: (el.textContent || '').trim().replace(/\\s+/g, ' ')
                })).filter(x => x.text.length > 15 && x.href);
            }"""
            )
            def _is_junk_title(t: str) -> bool:
                low = (t or "").strip().lower()
                return low == "показать все источники" or "показать все источники" in low

            for item in links:
                href = item.get("href") or ""
                text = (item.get("text") or "").strip()
                if len(text) < 15 or href in seen:
                    continue
                if "captcha" in href.lower() or "login" in href:
                    continue
                if _is_junk_title(text):
                    continue
                seen.add(href)
                out.append((text[:200], href))
                if len(out) >= limit:
                    break

            if not out:
                html = await page.content()
                for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]{15,200})</a>', html):
                    link, title = m.group(1), re.sub(r"\s+", " ", m.group(2).strip())
                    if link in seen or len(title) < 15:
                        continue
                    if "показать все источники" in (title or "").lower():
                        continue
                    if "dzen.ru" in link or "yandex" in link or "/news/" in link:
                        seen.add(link)
                        out.append((title[:200], link))
                        if len(out) >= limit:
                            break
        except Exception as e:
            logger.debug("Dzen Playwright %s: %s", city_name, e)
        finally:
            await browser.close()

    return out


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "Москва"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    items = asyncio.run(fetch_dzen_news_for_city(city, limit=limit))
    for i, (title, link) in enumerate(items, 1):
        print(f"{i}. {title}\n   {link}")
    if not items:
        print("(ничего не получено — капча или ошибка)")
    return 0 if items else 1


if __name__ == "__main__":
    sys.exit(main())
