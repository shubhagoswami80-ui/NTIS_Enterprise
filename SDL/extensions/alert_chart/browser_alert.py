from __future__ import annotations

import json


def browser_notification_script(event: dict) -> str:
    """Client-side notification helper. Detection remains server-side."""
    title = json.dumps(f"NTIS Alert · {event.get('symbol', '')}")
    body = json.dumps(str(event.get("rule_name", "Alert")))
    return f"""
<script>
(function(){{
  const fire=()=>{{
    if (!('Notification' in window)) return;
    if (Notification.permission === 'granted') new Notification({title}, {{body:{body}}});
  }};
  if (Notification.permission === 'granted') fire();
  else if (Notification.permission !== 'denied') Notification.requestPermission().then(p=>{{if(p==='granted')fire();}});
}})();
</script>
"""
