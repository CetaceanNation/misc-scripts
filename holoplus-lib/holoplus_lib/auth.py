import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
from http.cookiejar import (
    MozillaCookieJar
)
import httpx
import json
import logging
import nodriver
from nodriver import cdp
import os
from typing import Optional
from urllib import parse as urlparse

from . import Holoplus

ACCOUNT_AUTH_URL = "https://account.hololive.net/v1/auth/"
ANDROID_HEADERS = {
    "user-agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-S908E Build/TP1A.220624.014)",
    "x-android-package": "com.cover_corp.holoplus",
    "x-client-version": "Android/Fallback/X24000001/FirebaseCore-Android"
}
APP_PROTOCOL = "holoplus:///"
CHROME_HEADERS = {
    "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) " +
    "Chrome/129.0.0.0 Safari/537.36",
    "x-browser-channel": "stable",
    "x-browser-copyright": "Copyright 2024 Google LLC. All rights reserved.",
    "x-browser-year": "2024"
}
GOOGLE_API = "https://www.googleapis.com/identitytoolkit/v3/relyingparty"
GOOGLE_API_KEY = "AIzaSyBIBy1CboBwrCShfY1CixfRRynJRF06vx0"
GOOGLE_REFRESH_API = "https://securetoken.googleapis.com/v1/token"
NODRIVER_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-web-security",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-features=IsolateOrigins,site-per-process",
    "--window-size=1920,1080"
]

log = logging.getLogger("holoplus_lib")


class RequestException(Exception):
    pass


class UnexpectedProcedureException(Exception):
    def __init__(self, msg, *args, **kwargs):
        msg = "Something is different about the auth process which requires an" + \
            f" update, please report this!\n\t{msg}"
        super().__init__(msg, *args, **kwargs)


class HoloplusAuth():
    id_token: str
    refresh_token: str
    expiry_time: datetime
    file_path: str

    def __init__(self, file_path: Optional[str] = None):
        if file_path:
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r") as token_file:
                        token_values = json.load(token_file)
                    self.__dict__.update(token_values)
                    log.debug(f"Token loaded from file '{file_path}'")
                except Exception as e:
                    log.error(
                        f"Failed to load token details from file '{file_path}'", e)
            else:
                log.error(f"Token file does not exist '{file_path}'")

    def is_valid(self):
        return self.id_token and self.refresh_token and self.expiry_time

    def is_expired(self):
        return datetime.now(timezone.utc) >= self.expiry_time if self.expiry_time else False

    def set_path(self, file_path: str):
        self.file_path = file_path

    def update(self, token_dict: dict):
        self.id_token = token_dict.get(
            "idToken", token_dict.get("id_token", None))
        self.refresh_token = token_dict.get(
            "refreshToken", token_dict.get("refresh_token", None))
        expire_buffer = int(token_dict.get(
            "expiresIn", token_dict.get("expires_in", None)))
        if expire_buffer > 30:
            expire_buffer -= 30
        self.expiry_time = datetime.now(
            timezone.utc) + timedelta(seconds=expire_buffer)

    def save(self):
        if self.file_path:
            with open(self.file_path, "w") as token_file:
                json.dump(self.__dict__, token_file)
        else:
            log.debug("Token not saved, path not configured.")


async def do_login(current_auth: HoloplusAuth = None, cookies_path: str = None) -> HoloplusAuth:
    cookie_jar = None
    if cookies_path:
        if os.path.isfile(cookies_path):
            cookie_jar = MozillaCookieJar()
            try:
                cookie_jar.load(
                    cookies_path, ignore_discard=True, ignore_expires=True)
            except Exception as e:
                log.error(
                    f"Failed to load cookies from file '{cookies_path}'", e)
        else:
            log.error(f"Cookies file does not exist '{cookies_path}'")

    holoplus = Holoplus(current_auth)
    init_resp = await holoplus.init_auth()
    if not init_resp.is_success:
        raise RequestException("Failed to get initial auth response.")
    init_data = init_resp.json()
    if "session_id" not in init_data or "url" not in init_data:
        raise UnexpectedProcedureException("Missing session_id or url.")

    log.debug("session_id: %s", init_data["session_id"])

    browser = None
    redirect_url = None
    browser_cookies = None
    browser_finished = asyncio.Event()
    close_task = None

    try:
        browser = await nodriver.start(
            headless=False,
            no_sandbox=True,
            browser_args=NODRIVER_ARGS
        )
        tab = await browser.get("about:blank")
        await tab.send(cdp.network.enable())

        async def on_request(event):
            nonlocal browser_cookies, redirect_url
            try:
                url = event.request.url
                if ACCOUNT_AUTH_URL in url:
                    log.debug("Found redirect URL, handling...")
                    browser_cookies = browser.cookies.get_all(True)
                    redirect_url = url
                    browser_finished.set()
            except Exception:
                log.error(f"Issue while intercepting event: {event}")

        tab.add_handler(cdp.network.RequestWillBeSent, on_request)

        async def browser_close():
            try:
                while True:
                    if not browser.tabs:  # all tabs closed
                        log.debug("Browser closed by user")
                        break
                    await asyncio.sleep(0.5)
            except Exception:
                log.debug("Exception with browser, detecting as closed.")
            finally:
                browser_finished.set()

        close_task = asyncio.create_task(browser_close())

        await tab.get(init_data["url"])
        log.info("Browser opened. Please sign in to continue the auth process.")
        await browser_finished.wait()
    except Exception as e:
        log.error("Exception while running nodriver browser!", e)
        browser_finished.set()
    finally:
        if close_task:
            close_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await close_task
        if browser:
            with contextlib.suppress(Exception):
                await browser.close()
    log.debug(
        f"auth redirect: {redirect_url}" if redirect_url else "No callback URL captured")
    log.debug(f"cookies: {browser_cookies}")
    if not redirect_url:
        log.error("Login not detected, pass cookies or try again.")
        return
    async with httpx.AsyncClient() as client:
        client.cookies = browser_cookies
        while not redirect_url.startswith(APP_PROTOCOL):
            auth_resp = await client.get(redirect_url, headers=CHROME_HEADERS)
            if not auth_resp.is_success:
                raise RequestException(
                    f"Failed to get response from '{redirect_url}'.")
            elif auth_resp.status_code % 300 < 10:
                redirect_url = auth_resp.next_request.url
            else:
                raise UnexpectedProcedureException(
                    "Ran out of redirects before returning to holoplus.")
        q_string = urlparse(redirect_url).query
        q_dict = urlparse.parse_qs(q_string)
        if "state" not in q_dict or "code" not in q_dict:
            raise UnexpectedProcedureException(
                "Missing state or code in holoplus URL.")
            token_resp = await holoplus.send_for_token(q_dict["code"], init_data["session_id"], q_dict["state"])
            if not token_resp.is_success:
                raise RequestException(
                    "Failed to get response token response.")
            token_json = token_resp.json()
            if "token" not in token_json:
                raise UnexpectedProcedureException(
                    "No token found in the response.")
            token_json["returnSecureToken"] = True
            google_token_resp = await client.post(f"{GOOGLE_API}/verifyCustomToken",
                                                  headers=ANDROID_HEADERS,
                                                  params={
                                                      "key": GOOGLE_API_KEY},
                                                  json=token_json)
            if not google_token_resp.is_success:
                raise RequestException("Failed to get Google API response")
            auth_json = google_token_resp.json()
    current_auth.update(auth_json)
    log.debug(f"Auth finalized, token expires at {current_auth.expiry_time}")
    return current_auth


async def refresh_token(current_auth: HoloplusAuth) -> HoloplusAuth:
    async with httpx.AsyncClient() as client:
        refresh_json = {
            "grantType": "refresh_token",
            "refreshToken": current_auth.refresh_token
        }
        log.debug("Attempting to refresh auth token.")
        google_token_resp = await client.post(GOOGLE_REFRESH_API,
                                              headers=ANDROID_HEADERS,
                                              params={"key": GOOGLE_API_KEY},
                                              json=refresh_json)
        if not google_token_resp.is_success:
            raise RequestException("Failed to refresh auth token.")
        auth_json = google_token_resp.json()
    current_auth.update(token_dict=auth_json)
    log.debug(f"Auth token refreshed, expires at {current_auth.expiry_time}")
    return current_auth
