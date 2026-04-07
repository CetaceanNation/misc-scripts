import asyncio
from datetime import datetime, timedelta, timezone
from http.cookiejar import (
    CookieJar,
    MozillaCookieJar
)
import httpx
import json
import logging
import os
import re
from typing import Optional


ACCOUNT_AUTH_URL = "https://account.hololive.net/v1/auth/"
ANDROID_HEADERS = {
    "user-agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-S908E Build/TP1A.220624.014)",
    "x-android-package": "com.cover_corp.holoplus",
    "x-client-version": "Android/Fallback/X24000001/FirebaseCore-Android"
}
APP_SCHEME = "holoplus"
AUTH_API = "https://api.holoplus.com/v2/auth"
BASE_URL = "https://api.holoplus.com/"
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
HOLOPLUS_HEADERS = {
    "app-version": "3.4.2 (215)",
    "content-type": "text/plain; charset=utf-8",
    "release-type": "app_data",
    "user-agent": "Dart/3.10 (dart:io)"
}
HOLOPLUS_SIGNUP_RE = r"(?:state=)(?P<state>[^&]+).*(?:code=)(?P<code>[^&]+)"
NODRIVER_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-features=IsolateOrigins,site-per-process"
]

log = logging.getLogger("holoplus_lib")


class AuthException(Exception):
    pass


class CookieLoadException(Exception):
    pass


class RequestException(Exception):
    def __init__(self, response=None, *args, **kwargs):
        msg = f"Failed to get response from '{response.url}', status {response.status_code}"
        super().__init__(msg, *args, **kwargs)
    pass


class UnexpectedProcedureException(Exception):
    def __init__(self, msg, *args, **kwargs):
        msg = "Something is different about the auth process which requires an" + \
            f" update, please report this!\n\t{msg}"
        super().__init__(msg, *args, **kwargs)


class HoloplusAuth():
    id_token: str = None
    refresh_token: str = None
    expiry_time: datetime = None
    path: str = None

    def __init__(self):
        pass

    def is_valid(self) -> bool:
        return self.id_token and self.refresh_token and self.expiry_time

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expiry_time if self.expiry_time else False

    def get_bearer(self) -> Optional[dict]:
        if self.id_token:
            return {
                "authorization": f"Bearer {self.id_token}"
            }
        else:
            return None

    def set_path(self, token_path: str) -> None:
        self.path = token_path

    def update(self, token_dict: dict):
        self.id_token = token_dict.get(
            "idToken", token_dict.get("id_token", None))
        self.refresh_token = token_dict.get(
            "refreshToken", token_dict.get("refresh_token", None))
        expire_buffer = token_dict.get(
            "expiresIn", token_dict.get("expires_in", None))
        if expire_buffer:
            expire_buffer = int(expire_buffer)
            if expire_buffer > 30:
                expire_buffer -= 30
            self.expiry_time = datetime.now(
                timezone.utc) + timedelta(seconds=expire_buffer)
        expiry_time = token_dict.get("expiry_time", None)
        if expiry_time:
            self.expiry_time = datetime.fromisoformat(expiry_time)

    def save(self) -> None:
        if self.path:
            try:
                with open(self.path, "w") as token_file:
                    json.dump({
                        "id_token": self.id_token,
                        "refresh_token": self.refresh_token,
                        "expiry_time": self.expiry_time.isoformat()
                    }, token_file)
                    log.debug(f"Saved token details to file '{self.path}'")
                    return
            except Exception as e:
                log.error(f"Could not save token to '{self.path}'", e)
                self.path = None


class Holoplus():
    auth: HoloplusAuth = HoloplusAuth()
    client: httpx.AsyncClient = None
    headers: dict = HOLOPLUS_HEADERS.copy()

    def __init__(self, token_path: str = None):
        if token_path:
            self.auth.set_path(token_path)
            if os.path.isfile(token_path):
                try:
                    with open(token_path, "r") as token_file:
                        token_values = json.load(token_file)
                    log.debug(f"Token details loaded from file '{token_path}'")
                    self.update_auth(token_values)
                except Exception as e:
                    log.error(
                        f"Failed to load token details from file '{token_path}'", e)
            else:
                log.warn(f"Token file does not exist '{token_path}', will create if necessary")

    def __enter__(self):
        raise RuntimeError("Must be instantiated in an async context")

    def __exit__(self, *args):
        pass

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=self.headers
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.aclose()

    async def request(self, url: str, method: str = "GET", **kwargs) -> Optional[dict]:
        if self.auth.is_valid() and self.auth.is_expired():
            await self.refresh_token()
        request_headers = self.headers.copy()
        request_headers.update(kwargs.pop("headers", {}))
        log.debug(f"Requesting '{url}'")
        resp = await self.client.request(
            method,
            url,
            headers=request_headers,
            **kwargs
        )
        if not resp.is_success:
            raise RequestException(resp)
        return resp.json()

    def update_auth(self, token_values: dict) -> None:
        self.auth.update(token_values)
        self.auth.save()
        self.headers.update(self.auth.get_bearer())

    async def valid_auth(self) -> bool:
        try:
            await self.request("v1/me")
        except Exception:
            log.debug("Could not retrieve response from user endpoint, unauthenticated")
            return False
        log.debug("Received response from user endpoint, authenticated")
        return True

    async def do_login(self, cookies_path: str = None) -> bool:
        init_data = await self.request("v2/auth")
        if "session_id" not in init_data or "url" not in init_data:
            raise UnexpectedProcedureException("Missing session_id or url")
        log.debug("session_id: %s", init_data["session_id"])
        cookie_jar = None
        redirect_url = init_data["url"]
        if cookies_path:
            if os.path.isfile(cookies_path):
                cookie_jar = MozillaCookieJar()
                try:
                    cookie_jar.load(
                        cookies_path, ignore_discard=True, ignore_expires=True)
                except Exception as e:
                    raise CookieLoadException(
                        f"Failed to load cookies from file '{cookies_path}'", e)
            else:
                raise CookieLoadException(
                    f"Cookies file does not exist '{cookies_path}'")
        else:
            import contextlib

            # Need to patch nodriver for cookies from newer versions of Chromium
            # https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/2297
            from nodriver.cdp.network import Cookie
            Cookie.__dataclass_fields__['same_party'].default = False
            Cookie.__dataclass_fields__['same_party'].default_factory = None
            cookie_from_json = Cookie.from_json

            def from_json_patch(json):
                if 'sameParty' not in json:
                    json['sameParty'] = False
                return cookie_from_json(json)
            Cookie.from_json = from_json_patch
            # Finished patch

            import nodriver
            from nodriver import cdp
            from screeninfo import get_monitors
            browser = None
            browser_finished = asyncio.Event()
            close_task = None
            try:
                main_display = get_monitors()[0]
                browser_args = NODRIVER_ARGS.copy()
                browser_args.extend([
                    f"--window-size={int(main_display.width / 2.0)},{int((main_display.height * 2.0) / 3.0)}",
                    f"--window-position={int(main_display.width / 4.0)},{int(main_display.height / 6.0)}"
                ])
                browser = await nodriver.start(
                    headless=False,
                    no_sandbox=True,
                    browser_args=browser_args
                )
                tab = await browser.get("about:blank")
                await tab.send(cdp.network.enable())

                async def on_request(event):
                    nonlocal cookie_jar, redirect_url
                    try:
                        url = event.request.url
                        if ACCOUNT_AUTH_URL in url and "callback" in url:
                            log.debug("Found auth redirect URL, handling...")
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
                                browser_finished.set()
                                break
                            await asyncio.sleep(0.5)
                    except Exception:
                        log.debug(
                            "Exception with browser, assuming it was closed")
                        browser_finished.set()

                close_task = asyncio.create_task(browser_close())

                await tab.get(redirect_url)
                log.info(
                    "Browser opened. Please sign in to continue the auth process")
                await browser_finished.wait()
                cookies_list = await browser.cookies.get_all(True)
                cookie_jar = CookieJar()
                for cookie in cookies_list:
                    cookie_jar.set_cookie(cookie)
            except Exception as e:
                log.error("Failed to get authentication from browser", e)
                browser_finished.set()
            finally:
                if close_task:
                    close_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await close_task
                if browser is not None:
                    with contextlib.suppress(Exception):
                        browser.stop()
                        await browser.close()
        if not cookie_jar:
            log.error("Got no cookies for authentication, cannot continue")
            return False
        async with httpx.AsyncClient() as client:
            client.cookies.jar = cookie_jar
            while isinstance(redirect_url, str) or redirect_url.scheme != APP_SCHEME:
                log.debug(f"Auth redirect: {redirect_url}")
                auth_resp = await client.get(redirect_url, headers=CHROME_HEADERS)
                if auth_resp.next_request:
                    redirect_url = auth_resp.next_request.url
                else:
                    raise AuthException(
                        "Ran out of redirects before returning to Holoplus, your cookies may be invalid")
            log.debug(f"Holoplus URL: {redirect_url}")
            query_param_m = re.search(HOLOPLUS_SIGNUP_RE, str(redirect_url))
            if not query_param_m:
                raise UnexpectedProcedureException(
                    "Missing state or code in holoplus URL")
            token_json = await self.request("v2/auth/token", "POST",
                                            headers={
                                                "content-type": "application/json; charset=utf-8"},
                                            json={
                                                "code": query_param_m.group("code"),
                                                "session_id": init_data["session_id"],
                                                "state": query_param_m.group("state")
                                            })
            if "token" not in token_json:
                raise UnexpectedProcedureException(
                    "No token found in the response")
            token_json["returnSecureToken"] = True
            google_token_resp = await client.post(f"{GOOGLE_API}/verifyCustomToken",
                                                  headers=ANDROID_HEADERS,
                                                  params={
                                                      "key": GOOGLE_API_KEY},
                                                  json=token_json)
            if not google_token_resp.is_success:
                raise RequestException(google_token_resp)
        self.update_auth(google_token_resp.json())
        log.debug(
            f"Auth process succeeded, token expires at {self.auth.expiry_time}")
        return True

    async def refresh_token(self):
        log.debug("Attempting to refresh auth token")
        async with httpx.AsyncClient() as client:
            refresh_json = {
                "grantType": "refresh_token",
                "refreshToken": self.auth.refresh_token
            }
            google_token_resp = await client.post(GOOGLE_REFRESH_API,
                                                  headers=ANDROID_HEADERS,
                                                  params={
                                                      "key": GOOGLE_API_KEY},
                                                  json=refresh_json)
            if not google_token_resp.is_success:
                raise RequestException(google_token_resp)
            auth_json = google_token_resp.json()
        self.update_auth(auth_json)
        log.debug(
            f"Auth refreshed, token expires at {self.auth.expiry_time}")
