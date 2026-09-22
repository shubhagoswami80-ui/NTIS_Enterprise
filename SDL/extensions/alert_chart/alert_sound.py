"""Browser-side optional sound controller for NTIS SDL B4."""
from __future__ import annotations
from dataclasses import dataclass
from html import escape

@dataclass(frozen=True)
class SoundSettings:
    enabled: bool = False
    volume: float = 0.35
    tone: str = "soft"
    def normalized(self) -> "SoundSettings":
        volume = max(0.0, min(1.0, float(self.volume)))
        tone = self.tone if self.tone in {"single", "double", "soft"} else "soft"
        return SoundSettings(bool(self.enabled), volume, tone)

def sound_html(settings: SoundSettings, trigger: bool = False, nonce: str = "sdl", test_button: bool = False, compact: bool = True) -> str:
    s = settings.normalized()
    vol = f"{s.volume:.3f}"
    tone = escape(s.tone)
    trigger_js = "true" if trigger else "false"
    button = ""
    if test_button:
        button = '<button id="sdlSoundTest" type="button" style="background:#0e2037;color:#eef4fb;border:1px solid #315277;border-radius:7px;padding:6px 10px;font-size:11px;cursor:pointer">▶ Test sound</button>'
    return f'''<div id="{escape(nonce)}" style="font-family:inherit;color:#cbd7e7;font-size:11px">{button}
<script>
(function() {{
  const key='ntis_sdl_audio_unlocked_v1';
  const enabled={str(s.enabled).lower()};
  const volume={vol};
  const tone='{tone}';
  const trigger={trigger_js};
  function playBeep() {{
    try {{
      const C=window.AudioContext||window.webkitAudioContext;
      if(!C) return;
      const c=new C();
      const start=()=>{{
        const now=c.currentTime;
        const notes=tone==='single'?[740]:tone==='soft'?[520]:[660,880];
        notes.forEach((f,i)=>{{
          const o=c.createOscillator(), g=c.createGain();
          o.type='sine'; o.frequency.value=f;
          const t=now+i*0.12;
          g.gain.setValueAtTime(0,t);
          g.gain.linearRampToValueAtTime(Math.max(0.015,volume*0.10),t+0.018);
          g.gain.exponentialRampToValueAtTime(0.001,t+0.11);
          o.connect(g); g.connect(c.destination); o.start(t); o.stop(t+0.12);
        }});
        setTimeout(()=>{{try{{c.close();}}catch(e){{}}}},450);
      }};
      if(c.state==='suspended') c.resume().then(start).catch(()=>{{}}); else start();
    }} catch(e) {{}}
  }}
  function unlockAndTest() {{ try {{ localStorage.setItem(key,'1'); }} catch(e) {{}}; playBeep(); }}
  const test=document.getElementById('sdlSoundTest');
  if(test) test.addEventListener('click',unlockAndTest);
  if(trigger && enabled) {{ let unlocked=false; try {{ unlocked=localStorage.getItem(key)==='1'; }} catch(e) {{}}; if(unlocked) playBeep(); }}
}})();
</script></div>'''
