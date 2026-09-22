from ntis_integration.engine import compose_evidence, integrate_alerts
def test_compose_is_additive_and_keeps_sdl_owner():
    r=compose_evidence(sdl={"decision_state":"ACTIVE_BULLISH"},retracement={"status":"WATCH"},rsi_momentum={"rsi_15m":61},stock_state={"state":"BULLISH"},pit_differential={"unusual":True},eod_unusual_activity={"event":"Volume Surge"},historical_outcome={"5m":"POSITIVE"},pdna={"pattern":"X"},alerts=[],trading_date="2026-09-22",observation_timestamp="2026-09-22T10:00:00",symbol="ABC")
    assert r["decision_owner"]=="SDL" and r["selection_gate"] is False
    assert r["evidence"]["sdl"]["decision_state"]=="ACTIVE_BULLISH" and r["evidence"]["pit_differential"]["unusual"] is True
def test_alert_integration_preserves_authoritative_timestamp():
    seen=[]
    def build_context(current,previous,*,trading_date,observation_timestamp):
        seen.append((current["symbol"],trading_date,observation_timestamp)); return {"previous":previous or {},"current":current}
    def evaluate_snapshot(rules,context,store=None): return [{"symbol":context["current"]["symbol"],"observation_timestamp":context["current"]["observation_timestamp"]}]
    e=integrate_alerts([{"symbol":"ABC","observation_timestamp":"2026-09-22T10:05:00"}],rules=[],build_context=build_context,evaluate_snapshot=evaluate_snapshot,trading_date="2026-09-22")
    assert seen==[("ABC","2026-09-22","2026-09-22T10:05:00")] and e[0]["observation_timestamp"]=="2026-09-22T10:05:00"
