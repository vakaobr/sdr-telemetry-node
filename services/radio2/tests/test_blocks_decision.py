"""Schedule blocks + desired-mode priority logic (P7 unit tests)."""

from app.scheduler.blocks import active_block, hhmm_to_min, make_blocks
from app.scheduler.decision import Override, desired_mode
from app.scheduler.passes import Pass

BLOCKS = make_blocks([("atc", "07:00", "23:00"), ("ais", "23:00", "07:00")])


def m(hh: int, mm: int = 0) -> int:
    return hh * 60 + mm


# -- blocks --------------------------------------------------------------------


def test_hhmm_parsing():
    assert hhmm_to_min("00:00") == 0 and hhmm_to_min("23:59") == 1439


def test_daytime_is_atc():
    assert active_block(m(12), BLOCKS) == "atc"
    assert active_block(m(7), BLOCKS) == "atc"  # inclusive start
    assert active_block(m(22, 59), BLOCKS) == "atc"


def test_night_wraps_to_ais():
    assert active_block(m(23), BLOCKS) == "ais"  # inclusive start of wrap block
    assert active_block(m(3), BLOCKS) == "ais"
    assert active_block(m(6, 59), BLOCKS) == "ais"


def test_no_blocks_returns_none():
    assert active_block(m(12), []) is None


def test_gap_in_schedule_returns_none():
    sparse = make_blocks([("atc", "09:00", "17:00")])
    assert active_block(m(20), sparse) is None


# -- decision priority ----------------------------------------------------------


def a_pass(now: int) -> Pass:
    return Pass("NOAA 19", aos=now, los=now + 600, max_el=45)


def test_idle_when_nothing_active():
    assert desired_mode(1000, override=None, current_pass=None, block=None, faulted=set()) == (
        "idle",
        "schedule",
    )


def test_block_when_scheduled():
    assert (
        desired_mode(1000, override=None, current_pass=None, block="atc", faulted=set())[0] == "atc"
    )


def test_satellite_preempts_block():
    mode, reason = desired_mode(
        1000, override=None, current_pass=a_pass(1000), block="atc", faulted=set()
    )
    assert mode == "satellite" and reason == "preempt"


def test_override_preempts_everything():
    mode, reason = desired_mode(
        1000,
        override=Override("ais", expires_at=None),
        current_pass=a_pass(1000),
        block="atc",
        faulted=set(),
    )
    assert mode == "ais" and reason == "manual"


def test_expired_override_ignored():
    assert (
        desired_mode(
            2000,
            override=Override("ais", expires_at=1500),
            current_pass=None,
            block="atc",
            faulted=set(),
        )[0]
        == "atc"
    )


def test_auto_override_releases():
    assert (
        desired_mode(
            1000,
            override=Override("auto", expires_at=None),
            current_pass=None,
            block="atc",
            faulted=set(),
        )[0]
        == "atc"
    )


def test_faulted_satellite_falls_through_to_block():
    mode, _ = desired_mode(
        1000, override=None, current_pass=a_pass(1000), block="atc", faulted={"satellite"}
    )
    assert mode == "atc"


def test_faulted_block_falls_through_to_idle():
    assert (
        desired_mode(1000, override=None, current_pass=None, block="atc", faulted={"atc"})[0]
        == "idle"
    )
