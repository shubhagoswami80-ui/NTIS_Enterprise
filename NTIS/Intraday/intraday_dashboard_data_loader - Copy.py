from datetime import datetime

def load_dashboard_data():

    return {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "READY"
    }
