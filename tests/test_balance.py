# -*- coding: utf-8 -*-
"""balance.py 纯逻辑单测（不依赖 Qt，可直接运行：python tests/test_balance.py）。"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from balance import (
    compute_today_usage,
    is_peak_time,
    price_for,
    read_ledger,
    record_ledger_usage,
    today_key,
    write_ledger,
)

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok:", name)
    else:
        FAIL += 1
        print("  FAIL:", name)


# ---------- 峰谷时间 ----------
# 北京时间 2026-01-01 10:00 = epoch + 8h 的 UTC 10 点
def bj(hour, minute=0, day=1):
    """构造北京时间的 epoch 秒（2026-01-day）。"""
    # 2026-01-01 00:00 UTC = epoch
    import datetime
    dt = datetime.datetime(2026, 1, day, hour, minute, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    return int(dt.timestamp())


check("09:00 是高峰", is_peak_time(bj(9)))
check("11:59 是高峰", is_peak_time(bj(11, 59)))
check("12:00 非高峰", not is_peak_time(bj(12)))
check("13:59 非高峰", not is_peak_time(bj(13, 59)))
check("14:00 是高峰", is_peak_time(bj(14)))
check("17:59 是高峰", is_peak_time(bj(17, 59)))
check("18:00 非高峰", not is_peak_time(bj(18)))
check("08:00 非高峰", not is_peak_time(bj(8)))
check("非法值返回 False", not is_peak_time("abc") and not is_peak_time(None))

# ---------- 模型价格 ----------
check("deepseek-chat 命中", price_for("deepseek-chat") == price_for("deepseek-reasoner"))
check("v4-flash 命中", price_for("deepseek-v4-flash")["hit"][0] == 0.05)
check("未知模型走默认", price_for("gpt-4o")["miss"][1] == 3.0)

# ---------- 平台用量换算 ----------
sample = {
    "data": {
        "biz_data": {
            "series": [
                {
                    "model": "deepseek-chat",
                    "buckets": [
                        {"time": bj(10), "usage": {"PROMPT_CACHE_HIT_TOKEN": 1000000, "PROMPT_CACHE_MISS_TOKEN": 1000000, "RESPONSE_TOKEN": 1000000}},
                    ],
                }
            ]
        }
    }
}
u = compute_today_usage(sample)
# 高峰价：hit 0.1 + miss 3.0 + out 9.0 = 12.10 CNY
check("峰谷换算金额", u is not None and abs(u["amount"] - (0.1 + 3.0 + 9.0)) < 1e-9)
check("token 统计", u["tokens"] == 3000000)
check("空数据返回 None", compute_today_usage({"data": {}}) is None)
check("兼容扁平结构", compute_today_usage({"series": [{"model": "x", "buckets": []}]}) is None)

# ---------- 记账模式 ----------
with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, ".dshw-usage.json")

    # 首次：只记录 lastBalance，当日用量 0
    led = record_ledger_usage(path, 100.0)
    check("首次记账 todayUsage=0", led["todayUsage"] == 0 and led["lastBalance"] == 100.0)

    # 余额下降 → 记账差值
    led = record_ledger_usage(path, 95.5)
    check("差值记账 4.5", abs(led["todayUsage"] - 4.5) < 1e-9)

    # 余额上升（充值）→ 不计负值
    led = record_ledger_usage(path, 200.0)
    check("充值不计负值", led["todayUsage"] == 4.5 and led["lastBalance"] == 200.0)

    # 再次下降累计
    led = record_ledger_usage(path, 190.0)
    check("累计 14.5", abs(led["todayUsage"] - 14.5) < 1e-9)

    # 读回
    led2 = read_ledger(path)
    check("账本落盘可读回", led2["date"] == today_key() and abs(led2["todayUsage"] - 14.5) < 1e-9)

    # 历史归档保留 30 天（经 record_ledger_usage 截断）
    led = read_ledger(path)
    led["history"] = {f"2025-12-{d:02d}": 1.0 for d in range(1, 40)}
    led["lastBalance"] = 190.0
    write_ledger(path, led)
    led3 = record_ledger_usage(path, 190.0)
    check("历史归档上限 30", len(led3["history"]) <= 30)

print()
print(f"PASS={PASS} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
