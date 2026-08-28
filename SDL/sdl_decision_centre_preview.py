*** Begin Patch
*** Update File: SDL/sdl_decision_centre_preview.py
@@
 def add_first_times(df: pd.DataFrame) -> pd.DataFrame:
@@
     out["first_trigger_timestamp"] = out["symbol"].map(first_map)
     return out
+
+
+def apply_board_filter_state(df: pd.DataFrame) -> pd.DataFrame:
+    """Apply the same live Decision Board filters to any displayed snapshot.
+
+    Presentation-only: this never recalculates SDL decisions.
+    Replay therefore uses exactly the current Live filter state.
+    """
+    if df is None or df.empty:
+        return pd.DataFrame()
+
+    out = df.copy()
+    direction_choice = st.session_state.get("board_direction", "All")
+    strength_choice = st.session_state.get("board_strength", "All")
+    progress_choice = st.session_state.get("board_progress", "All")
+    stage_choice = st.session_state.get("board_stage", "All")
+
+    if direction_choice != "All":
+        out = out[
+            out.get("direction_label", pd.Series("", index=out.index))
+            .astype(str).str.upper().eq(direction_choice.upper())
+        ]
+
+    if strength_choice != "All":
+        wanted = strength_choice.upper().split("/")[0].strip()
+        out = out[
+            out.get("strength_label", pd.Series("", index=out.index))
+            .astype(str).str.upper().str.contains(wanted, regex=False, na=False)
+        ]
+
+    progress = pd.to_numeric(
+        out.get("progress", pd.Series(index=out.index, dtype=float)),
+        errors="coerce",
+    ).fillna(-1)
+
+    if progress_choice == "25%+":
+        out = out[progress >= 25]
+    elif progress_choice == "50%+":
+        out = out[progress >= 50]
+    elif progress_choice == "70%+":
+        out = out[progress >= 70]
+    elif progress_choice == "75%+":
+        out = out[progress >= 75]
+    elif progress_choice == "Breakout":
+        out = out[breakout_series(out)]
+
+    if stage_choice != "All":
+        p = pd.to_numeric(
+            out.get("progress", pd.Series(index=out.index, dtype=float)),
+            errors="coerce",
+        )
+        if stage_choice == "100%+ BREAKOUT":
+            out = out[breakout_series(out)]
+        elif stage_choice == "25–<50% EARLY":
+            out = out[(p >= 25) & (p < 50)]
+        elif stage_choice == "50–<75%":
+            out = out[(p >= 50) & (p < 75)]
+        elif stage_choice == "75–<100% APPROACHING":
+            out = out[(p >= 75) & (p < 100)]
+
+    return out
@@
 def run_snapshot(path: Path | None) -> pd.DataFrame:
@@
-        return add_first_times(candidates(source))
+        out = add_first_times(candidates(source))
+        # Display/audit timestamp from the selected snapshot only.
+        # This does not alter SDL decision or alert semantics.
+        if not out.empty:
+            out["observation_timestamp"] = observation_ts(path)
+        return out

@@
-    st.session_state["refresh_seconds"] = st.selectbox(
+    st.session_state["refresh_seconds"] = st.selectbox(
@@
-            [5, 10, 15, 30, 60],
-            index=[5, 10, 15, 30, 60].index(int(st.session_state["refresh_seconds"])),
+            [3, 5, 7, 10, 15],
+            index=[3, 5, 7, 10, 15].index(int(st.session_state["refresh_seconds"])),
@@
-        filtered = live.copy()
-        direction_choice = st.session_state.get("board_direction", "All")
-        strength_choice = st.session_state.get("board_strength", "All")
-        progress_choice = st.session_state.get("board_progress", "All")
-        stage_choice = st.session_state.get("board_stage", "All")
-
-        if direction_choice != "All":
-            filtered = filtered[
-                filtered.get("direction_label", pd.Series("", index=filtered.index))
-                .astype(str).str.upper().eq(direction_choice.upper())
-            ]
-
-        if strength_choice != "All":
-            wanted = strength_choice.upper().split("/")[0].strip()
-            filtered = filtered[
-                filtered.get("strength_label", pd.Series("", index=filtered.index))
-                .astype(str).str.upper().str.contains(wanted, regex=False, na=False)
-            ]
-
-        progress = pd.to_numeric(
-            filtered.get("progress", pd.Series(index=filtered.index, dtype=float)),
-            errors="coerce",
-        ).fillna(-1)
-
-        if progress_choice == "25%+":
-            filtered = filtered[progress >= 25]
-        elif progress_choice == "50%+":
-            filtered = filtered[progress >= 50]
-        elif progress_choice == "70%+":
-            filtered = filtered[progress >= 70]
-        elif progress_choice == "75%+":
-            filtered = filtered[progress >= 75]
-        elif progress_choice == "Breakout":
-            filtered = filtered[breakout_series(filtered)]
-
-        if stage_choice != "All":
-            p = pd.to_numeric(
-                filtered.get("progress", pd.Series(index=filtered.index, dtype=float)),
-                errors="coerce",
-            )
-            if stage_choice == "100%+ BREAKOUT":
-                filtered = filtered[breakout_series(filtered)]
-            elif stage_choice == "25–<50% EARLY":
-                filtered = filtered[(p >= 25) & (p < 50)]
-            elif stage_choice == "50–<75%":
-                filtered = filtered[(p >= 50) & (p < 75)]
-            elif stage_choice == "75–<100% APPROACHING":
-                filtered = filtered[(p >= 75) & (p < 100)]
+        filtered = apply_board_filter_state(live)
@@
-                replay_visible = replay_df.copy() if isinstance(replay_df, pd.DataFrame) else pd.DataFrame()
+                replay_visible = (
+                    apply_board_filter_state(replay_df)
+                    if isinstance(replay_df, pd.DataFrame)
+                    else pd.DataFrame()
+                )
@@
-        [5, 10, 15, 30, 60],
-        index=[5, 10, 15, 30, 60].index(int(st.session_state["refresh_seconds"])),
+        [3, 5, 7, 10, 15],
+        index=[3, 5, 7, 10, 15].index(int(st.session_state["refresh_seconds"])),
*** End Patch
*** Begin Patch
*** Update File: SDL/sdl_decision_centre_preview.py
@@
 defaults = {
@@
 }
 for key, value in defaults.items():
     if key not in st.session_state:
         st.session_state[key] = value
+
+if st.session_state["refresh_seconds"] not in {3, 5, 7, 10, 15}:
+    st.session_state["refresh_seconds"] = 10
@@
     st.session_state["refresh_seconds"] = st.selectbox(
*** End Patch
