# -*- coding: utf-8 -*-
"""balance.py —— 数据层：余额拉取、记账模式、令牌模式（峰谷定价）。

逻辑移植自 DeepSeek-Balance-Whale-Widget 的 lib/index.js，保持行为一致：
- 余额：api.deepseek.com/user/balance，Bearer Key，两次重试
- 记账模式：余额正差值累计当日消耗，跨天自动归零归档（.dshw-usage.json）
- 令牌模式：platform.deepseek.com 用量接口按峰谷定价实时换算
- 缓存 TTL 25s；瞬时网络抖动沿用最近余额（stale 标记），不报错

线程模型：BalanceEngine.refresh() 在后台线程执行网络请求，结果放入队列，
由 UI 主线程 drain() 取走（同 dafeiyu-pet 的 _say_queue 模式）。
"""
import json
import os
import threading
import time
from datetime import datetime

import requests

BALANCE_URL = "https://api.deepseek.com/user/balance"
BALANCE_TTL_MS = 25000

# DeepSeek 每百万 token 价格（CNY）：[空闲时段价, 高峰时段价]
# 高峰时段：每日 9:00–12:00 与 14:00–18:00（北京时间）
PEAK_HOURS = ((9, 12), (14, 18))
BASE_PRICE = {"hit": (0.05, 0.1), "miss": (1.5, 3.0), "out": (4.5, 9.0)}
PRICING = {
    "deepseek-chat": BASE_PRICE,
    "deepseek-reasoner": BASE_PRICE,
    "deepseek-v4-flash": BASE_PRICE,
    "deepseek-v4-pro": BASE_PRICE,
    "_default": BASE_PRICE,
}


def price_for(model: str) -> dict:
    m = str(model or "").lower()
    for key, price in PRICING.items():
        if key == "_default":
            continue
        if m.find(key) != -1:
            return price
    return PRICING["_default"]


def is_peak_time(time_sec) -> bool:
    """epoch 秒 → 北京时间小时，落在高峰时段返回 True。"""
    if not isinstance(time_sec, (int, float)) or not _isfinite(time_sec):
        return False
    hour = int((int(time_sec) + 8 * 3600) % 86400 // 3600)
    for start, end in PEAK_HOURS:
        if start <= hour < end:
            return True
    return False


def _isfinite(v) -> bool:
    try:
        return v == v and abs(v) != float("inf")
    except Exception:
        return False


def compute_today_usage(data) -> dict | None:
    """平台用量响应 → (amount, tokens)。兼容两种响应结构。"""
    d = data
    if d and d.get("data") and isinstance(d["data"], dict):
        biz = d["data"].get("biz_data")
        if biz and isinstance(biz, dict) and isinstance(biz.get("series"), list):
            d = biz
        elif isinstance(d["data"].get("series"), list):
            d = d["data"]
    series = d.get("series") if isinstance(d, dict) else None
    if not isinstance(series, list) or len(series) == 0:
        return None
    cost = 0.0
    tokens = 0
    found = False
    for s in series:
        if not isinstance(s, dict):
            continue
        p = price_for(s.get("model"))
        buckets = s.get("buckets") if isinstance(s.get("buckets"), list) else []
        for b in buckets:
            u = b.get("usage") if isinstance(b, dict) else None
            if not isinstance(u, dict):
                continue
            hit = _num(u.get("PROMPT_CACHE_HIT_TOKEN"))
            miss = _num(u.get("PROMPT_CACHE_MISS_TOKEN"))
            out = _num(u.get("RESPONSE_TOKEN"))
            if hit + miss + out == 0:
                continue
            found = True
            tokens += hit + miss + out
            pi = 1 if is_peak_time(b.get("time")) else 0
            cost += (hit / 1e6) * p["hit"][pi] + (miss / 1e6) * p["miss"][pi] + (out / 1e6) * p["out"][pi]
    return {"amount": cost, "tokens": tokens} if found else None


def _num(v) -> float:
    try:
        n = float(v)
        return n if _isfinite(n) else 0.0
    except (TypeError, ValueError):
        return 0.0


# ---------- 记账模式 ----------

def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def read_ledger(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        if isinstance(parsed, dict) and isinstance(parsed.get("date"), str):
            return parsed
    except (OSError, ValueError, TypeError):
        pass
    return {"date": today_key(), "lastBalance": None, "todayUsage": 0, "history": {}}


def write_ledger(path: str, led: dict) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(led, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def record_ledger_usage(path: str, current_balance: float) -> dict:
    """每次观测到余额后记账：正差值累计当日用量，跨天自动归零归档。"""
    t = today_key()
    led = read_ledger(path)
    if led.get("date") != t:
        if led.get("date") and isinstance(led.get("todayUsage"), (int, float)):
            led.setdefault("history", {})[led["date"]] = led["todayUsage"]
        led["date"] = t
        led["lastBalance"] = current_balance
        led["todayUsage"] = 0
    else:
        prev = led.get("lastBalance")
        if isinstance(prev, (int, float)) and isinstance(current_balance, (int, float)) and current_balance < prev:
            cur = led.get("todayUsage", 0)
            led["todayUsage"] = (cur if isinstance(cur, (int, float)) else 0) + (prev - current_balance)
        led["lastBalance"] = current_balance
    history = led.get("history") or {}
    keys = sorted(history.keys())
    while len(keys) > 30:
        history.pop(keys.pop(0))
    led["history"] = history
    write_ledger(path, led)
    return led


# ---------- 网络拉取 ----------

def fetch_balance(api_key: str) -> dict:
    """余额接口，最多两次重试（5xx/网络错误重试，4xx 直接失败）。"""
    if not api_key:
        return {"ok": False, "code": "NO_KEY", "error": "未配置 DEEPSEEK_API_KEY（环境变量或右键菜单设置）"}
    last_err = None
    for attempt in range(2):
        try:
            res = requests.get(
                BALANCE_URL,
                headers={"Authorization": "Bearer " + api_key},
                timeout=20,
            )
        except requests.RequestException as err:
            last_err = err
            if attempt == 0:
                time.sleep(0.5)
            continue
        if not res.ok:
            last_err = RuntimeError("HTTP " + str(res.status_code))
            if res.status_code < 500:
                break
            if attempt == 0:
                time.sleep(0.5)
            continue
        try:
            data = res.json()
        except ValueError:
            return {"ok": False, "code": "PARSE", "error": "余额接口返回不是合法 JSON"}
        info = None
        if isinstance(data, dict) and isinstance(data.get("balance_infos"), list) and data["balance_infos"]:
            info = data["balance_infos"][0]
        if not isinstance(info, dict) or info.get("total_balance") is None:
            return {"ok": False, "code": "SHAPE", "error": "余额接口返回结构异常"}
        return {
            "ok": True,
            "totalBalance": _num(info["total_balance"]),
            "currency": str(info.get("currency") or "CNY"),
            "updatedAt": datetime.now().isoformat(),
        }
    transient = not (last_err and str(last_err).find("HTTP 4") != -1)
    return {
        "ok": False,
        "code": "HTTP",
        "transient": transient,
        "error": "余额接口请求失败: " + str(last_err)[:200],
    }


def fetch_usage(platform_token: str) -> dict:
    """平台今日用量（令牌模式）。"""
    if not platform_token:
        return {"error": "未配置平台令牌"}
    token = platform_token
    if token.lower().startswith("bearer "):
        token = token[7:]
    try:
        now = datetime.now().astimezone()
        tz = int(now.utcoffset().total_seconds())
        start = int(datetime(now.year, now.month, now.day, tzinfo=now.tzinfo).timestamp())
        end = start + 86400
        url = (
            "https://platform.deepseek.com/api/v0/usage/by_api_key/amount"
            "?start={}&end={}&tz={}".format(start, end, tz)
        )
        res = requests.get(url, headers={"Authorization": "Bearer " + token}, timeout=15)
        if not res.ok:
            return {"error": "http " + str(res.status_code)}
        data = res.json()
        u = compute_today_usage(data)
        if u and _isfinite(u["amount"]):
            return {"amount": u["amount"], "tokens": u["tokens"]}
        return {"error": "no usage"}
    except (requests.RequestException, ValueError) as err:
        return {"error": str(err)[:200]}


class BalanceEngine:
    """余额服务：后台线程拉取 → 结果队列；缓存 + 瞬断兜底。"""

    def __init__(self, ledger_path: str):
        self.ledger_path = ledger_path
        self._results: list = []
        self._cache = None          # {"at": epoch_ms, "payload": dict}
        self._in_flight = False
        self._lock = threading.Lock()

    def refresh(self, api_key: str, platform_token: str, usage_mode: str) -> None:
        """启动一次异步刷新；返回前不阻塞。in-flight 时忽略重复请求。"""
        with self._lock:
            if self._in_flight:
                return
            self._in_flight = True
        threading.Thread(
            target=self._worker,
            args=(api_key, platform_token, usage_mode),
            daemon=True,
        ).start()

    def _worker(self, api_key, platform_token, usage_mode) -> None:
        try:
            payload = self._fetch_payload(api_key, platform_token, usage_mode)
            now = time.time() * 1000
            with self._lock:
                if payload.get("ok"):
                    self._cache = {"at": now, "payload": payload}
                elif payload.get("transient") and self._cache:
                    # 瞬时抖动：沿用最近余额
                    cached = dict(self._cache["payload"])
                    cached.update({"stale": True, "error": payload.get("error")})
                    payload = cached
                elif not payload.get("transient"):
                    print("[whale] balance error:", payload.get("code"), payload.get("error"))
                self._results.append(payload)
        finally:
            with self._lock:
                self._in_flight = False

    def _fetch_payload(self, api_key, platform_token, usage_mode) -> dict:
        with self._lock:
            if self._cache and time.time() * 1000 - self._cache["at"] < BALANCE_TTL_MS:
                return dict(self._cache["payload"])
        payload = fetch_balance(api_key)
        if not payload.get("ok"):
            return payload
        # 无论哪种模式都先记入账本（自动累积「鲸鱼记账」数据）
        led = record_ledger_usage(self.ledger_path, payload["totalBalance"])
        mode = "token" if usage_mode == "token" else "ledger"
        full = dict(payload)
        full["isPeak"] = is_peak_time(int(time.time()))
        if mode == "token":
            u = fetch_usage(platform_token)
            if u and u.get("amount") is not None:
                full["todayUsage"] = u["amount"]
                full["usageMode"] = "token"
                return full
        # 无令牌或令牌失败：回落记账模式
        full["todayUsage"] = led.get("todayUsage", 0)
        full["usageMode"] = "ledger"
        return full

    def drain(self) -> list:
        """取出所有待处理结果（UI 主线程调用）。"""
        with self._lock:
            items = self._results
            self._results = []
            return items
