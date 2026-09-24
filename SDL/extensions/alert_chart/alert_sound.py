"""Browser-side optional alert sound controller for NTIS SDL B4."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class SoundSettings:
    enabled: bool = False
    volume: float = 0.35
    tone: str = "long"

    def normalized(self) -> "SoundSettings":
        volume = max(0.0, min(1.0, float(self.volume)))
        tone = self.tone if self.tone in {"long", "single", "double", "soft"} else "long"
        return SoundSettings(bool(self.enabled), volume, tone)


def sound_html(
    settings: SoundSettings,
    trigger: bool = False,
    nonce: str = "sdl",
    test_button: bool = False,
    compact: bool = True,
) -> str:
    """Return a self-contained browser WebAudio alert.

    ``long`` is the trader-oriented default: a clear sustained alert with a
    short rising edge and controlled decay, long enough to be noticed without
    repeating continuously. Test Sound is a direct user gesture and also
    unlocks browser audio for later alert events.
    """
    s = settings.normalized()
    vol = f"{s.volume:.3f}"
    tone = escape(s.tone)
    trigger_js = "true" if trigger else "false"
    button = ""
    if test_button:
        button = (
            '<button id="sdlSoundTest" type="button" '
            'style="background:#0e2037;color:#eef4fb;border:1px solid #315277;'
            'border-radius:6px;padding:4px 8px;font-size:10px;cursor:pointer">'
            '▶ Test long alert</button>'
        )

    return f'''<div id="{escape(nonce)}" style="font-family:inherit;color:#cbd7e7;font-size:10px">{button}
<script>
(function() {{
  const key='ntis_sdl_audio_unlocked_v2';
  const enabled={str(s.enabled).lower()};
  const volume={vol};
  const tone='{tone}';
  const trigger={trigger_js};

  function playAlert() {{
    try {{
      const C=window.AudioContext||window.webkitAudioContext;
      if(!C) return;
      const c=new C();

      const start=()=>{{
        const now=c.currentTime;
        const master=c.createGain();
        master.gain.setValueAtTime(0.0001, now);
        master.gain.linearRampToValueAtTime(Math.max(0.018, volume*0.17), now+0.035);
        master.gain.setValueAtTime(Math.max(0.018, volume*0.17), now+0.58);
        master.gain.exponentialRampToValueAtTime(0.001, now+0.92);
        master.connect(c.destination);

        const makeTone=(freq, startAt, duration, type, gainScale)=>{{
          const o=c.createOscillator();
          const g=c.createGain();
          o.type=type;
          o.frequency.setValueAtTime(freq, startAt);
          o.frequency.linearRampToValueAtTime(freq*1.035, startAt+0.16);
          o.frequency.linearRampToValueAtTime(freq*0.99, startAt+duration);
          g.gain.setValueAtTime(0.0001, startAt);
          g.gain.linearRampToValueAtTime(Math.max(0.008, volume*gainScale), startAt+0.035);
          g.gain.setValueAtTime(Math.max(0.008, volume*gainScale), startAt+Math.max(0.08, duration-0.10));
          g.gain.exponentialRampToValueAtTime(0.001, startAt+duration);
          o.connect(g); g.connect(master);
          o.start(startAt); o.stop(startAt+duration+0.02);
        }};

        if(tone==='single') {{
          makeTone(760, now, 0.42, 'sine', 0.55);
        }} else if(tone==='double') {{
          makeTone(700, now, 0.30, 'sine', 0.48);
          makeTone(920, now+0.18, 0.36, 'sine', 0.52);
        }} else if(tone==='soft') {{
          makeTone(540, now, 0.55, 'sine', 0.38);
        }} else {{
          // LONG: sustained, unmistakable trader alert with a subtle harmonic.
          makeTone(760, now, 0.88, 'sine', 0.62);
          makeTone(1520, now+0.015, 0.72, 'sine', 0.12);
        }}

        setTimeout(()=>{{try{{c.close();}}catch(e){{}}}},1150);
      }};

      if(c.state==='suspended') c.resume().then(start).catch(()=>{{try{{c.close();}}catch(e){{}}}});
      else start();
    }} catch(e) {{}}
  }}

  function unlockAndTest() {{
    try {{ localStorage.setItem(key,'1'); }} catch(e) {{}}
    playAlert();
  }}

  const test=document.getElementById('sdlSoundTest');
  if(test) test.addEventListener('click', unlockAndTest, {{once:false}});

  if(trigger && enabled) {{
    let unlocked=false;
    try {{ unlocked=localStorage.getItem(key)==='1'; }} catch(e) {{}}
    if(unlocked) playAlert();
  }}
}})();
</script></div>'''
