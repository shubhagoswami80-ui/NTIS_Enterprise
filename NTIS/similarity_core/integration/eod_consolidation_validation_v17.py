
"""
NTIS V17 Consolidation Validation

Validates consolidated core modules.
Existing modules remain untouched.
"""

def run_validation():

    results = {}

    try:
        from eod_data_resolution_core_v17 import EODDataResolutionCoreV17
        results["DATA RESOLUTION CORE"] = "PASS"
    except Exception as e:
        results["DATA RESOLUTION CORE"] = f"FAIL: {e}"

    try:
        from eod_replay_dashboard_core_v17 import EODReplayDashboardCoreV17
        results["REPLAY DASHBOARD CORE"] = "PASS"
    except Exception as e:
        results["REPLAY DASHBOARD CORE"] = f"FAIL: {e}"

    try:
        from eod_runtime_control_core_v17 import EODRuntimeControlCoreV17
        results["RUNTIME CONTROL CORE"] = "PASS"
    except Exception as e:
        results["RUNTIME CONTROL CORE"] = f"FAIL: {e}"

    try:
        from eod_service_management_core_v17 import EODServiceManagementCoreV17
        results["SERVICE MANAGEMENT CORE"] = "PASS"
    except Exception as e:
        results["SERVICE MANAGEMENT CORE"] = f"FAIL: {e}"

    try:
        from eod_governance_audit_core_v17 import EODGovernanceAuditCoreV17
        results["GOVERNANCE AUDIT CORE"] = "PASS"
    except Exception as e:
        results["GOVERNANCE AUDIT CORE"] = f"FAIL: {e}"

    try:
        from eod_production_control_core_v17 import EODProductionControlCoreV17
        results["PRODUCTION CONTROL CORE"] = "PASS"
    except Exception as e:
        results["PRODUCTION CONTROL CORE"] = f"FAIL: {e}"

    try:
        from eod_final_integration_core_v17 import EODFinalIntegrationCoreV17
        results["FINAL INTEGRATION CORE"] = "PASS"
    except Exception as e:
        results["FINAL INTEGRATION CORE"] = f"FAIL: {e}"

    print("=" * 60)
    print("NTIS V17 CONSOLIDATION VALIDATION")
    print("=" * 60)

    for key, value in results.items():
        print(f"{key:<35} {value}")

    overall = all(value == "PASS" for value in results.values())

    print("=" * 60)
    print("OVERALL STATUS:", "READY" if overall else "CHECK REQUIRED")
    print("=" * 60)

    return results


if __name__ == "__main__":
    run_validation()
