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


def test_set_permanent_single_only_pins_the_given_angle():
    """把某个角度设为永久，不该顺手把别的角度也变成永不过期。

    原来 set_permanent_single 直接忽略了 angle 参数，把整个 single 桶设成永久，
    于是"钉住 0°"的实际效果是"所有角度再也不过期"。
    """
    cache = WhiteBalanceCache(valid_duration=0.2)
    cache.set_single(0, "g0")
    cache.set_single(45, "g45")

    cache.set_permanent_single(0)
    time.sleep(0.3)

    assert cache.get_single(0) == "g0"
    assert cache.get_single(45) is None, "45° 跟着 0° 一起被钉住了"


def test_per_key_permanent_is_lifted_by_reset_to_temporary():
    """重置为临时缓存要连按角度钉住的键一起放开。"""
    cache = WhiteBalanceCache(valid_duration=0.2)
    cache.set_single(0, "g0")
    cache.set_permanent_single(0)
    time.sleep(0.3)
    assert cache.get_single(0) == "g0", "钉住后不该过期"

    cache.reset_to_temporary(0.2)
    time.sleep(0.3)

    assert cache.get_single(0) is None, "reset_to_temporary 没把按角度钉住的键放回来"


def test_pinning_one_key_does_not_make_the_bucket_permanent():
    """单个键的永久不该让整桶自称永久——模式切换按整桶状态判断。"""
    cache = TimedCache(valid_duration=0.2)
    cache.set("a", 1)
    cache.set_permanent("a")

    assert cache.is_permanent() is False
    assert cache.is_permanent("a") is True
