"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import time

from polcam.core.caching import TimedCache, WhiteBalanceCache


def test_timed_cache_expires_per_key():
    """每个键各自计时，写入别的键不该给它续命。"""
    cache = TimedCache(valid_duration=0.2)
    cache.set("a", 1)
    time.sleep(0.1)
    cache.set("b", 2)
    time.sleep(0.15)

    assert cache.get("b") == 2
    assert cache.get("a") is None


def test_white_balance_gains_expire_per_angle():
    """四个角度的白平衡增益要各自过期。

    以前 single/quad 两个模式各自只有一个桶键，值才是 {角度: 增益} 的字典，
    于是任何一个角度的写入都会刷新整桶的时间戳 —— 别的角度还在续期的话，
    一个早过了有效期的增益会一直被端出来。
    """
    cache = WhiteBalanceCache(valid_duration=0.2)
    cache.set_quad(0, "g0")
    time.sleep(0.1)
    cache.set_quad(45, "g45")
    time.sleep(0.15)

    assert cache.get_quad(0) is None, "0° 的增益被别的角度续了命"
    assert cache.get_quad(45) == "g45"
