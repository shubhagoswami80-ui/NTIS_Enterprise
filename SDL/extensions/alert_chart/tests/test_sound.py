from alert_chart.alert_sound import SoundSettings, sound_html


def test_sound_defaults_off():
    assert SoundSettings().normalized().enabled is False


def test_sound_clamps_volume_and_tone():
    s = SoundSettings(True, 3, "bad").normalized()
    assert s.volume == 1.0
    assert s.tone == "double"


def test_sound_html_is_self_contained():
    html = sound_html(SoundSettings(True, 0.5, "single"), trigger=True, nonce="x")
    assert "AudioContext" in html
    assert "trigger=true" in html
    assert "volume=0.500" in html
