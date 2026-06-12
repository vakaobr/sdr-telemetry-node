"""rtl_airband config generation (P8.4)."""

import pytest

from app.rtl_airband import USABLE_HZ, AirbandConfigError, render_config


def test_single_channel_config():
    conf = render_config(["118.1"] and [118.1], serial="stx:0:28", icecast_host="icecast")
    assert 'serial = "stx:0:28"' in conf
    assert "freq = 118.1000" in conf
    assert 'modulation = "am"' in conf
    assert 'mountpoint = "atc"' in conf  # first channel → primary mount
    assert 'mountpoint = "atc_118100"' in conf
    assert "centerfreq = 118.1000" in conf


def test_multi_channel_centres_tuner_and_mounts_each():
    conf = render_config([118.1, 119.1, 120.3], serial="s", icecast_host="icecast")
    assert "centerfreq = 119.2000" in conf  # (118.1 + 120.3) / 2
    for f in ("atc_118100", "atc_119100", "atc_120300"):
        assert f'mountpoint = "{f}"' in conf
    assert 'mountpoint = "atc"' in conf  # primary = first channel only
    assert conf.count('mountpoint = "atc"') == 1


def test_empty_channels_rejected():
    with pytest.raises(AirbandConfigError, match="no ATC channels"):
        render_config([], serial="s", icecast_host="icecast")


def test_out_of_band_rejected():
    with pytest.raises(AirbandConfigError, match="118"):
        render_config([99.5], serial="s", icecast_host="icecast")


def test_span_too_wide_rejected_with_guidance():
    # 118.1 and 136.0 are ~18 MHz apart — can't fit one tuner
    with pytest.raises(AirbandConfigError, match="within"):
        render_config([118.1, 136.0], serial="s", icecast_host="icecast")


def test_span_at_limit_accepted():
    span_mhz = USABLE_HZ / 1e6
    render_config([118.1, 118.1 + span_mhz - 0.01], serial="s", icecast_host="icecast")


def test_icecast_credentials_embedded():
    conf = render_config(
        [121.5], serial="s", icecast_host="ice", icecast_port=8123, icecast_password="sekret"
    )
    assert 'server = "ice"' in conf
    assert "port = 8123" in conf
    assert 'password = "sekret"' in conf
