import sys
import yaml
from PyQt6.QtWidgets import QApplication

from ui.dashboard import CartDashboard
from ui.ui_controller import UIController

def main():
    """
    Main entry point for the Smart Cart UI application.
    """
    # Load network config to get Main PC2 IP
    try:
        # Assuming the app is run from the project root
        with open("configs/network_config.yaml", "r") as f:
            net_cfg = yaml.safe_load(f)
        # Assumes structure like: pc2_main: ip: "..."
        main_pc2_ip = net_cfg["pc2_main"]["ip"]
    except (IOError, KeyError, TypeError) as e:
        print("="*50)
        print(f"WARNING: Could not load Main PC IP from config file: {e}")
        print("  - File: 'configs/network_config.yaml'")
        print("  - Expected key path: 'pc2_main' -> 'ip'")
        print("  Defaulting to '127.0.0.1' for local testing.")
        print("="*50)
        main_pc2_ip = "127.0.0.1"

    app = QApplication(sys.argv)
    dashboard = CartDashboard()

    # UIController links the dashboard to the main server via TCP
    _controller = UIController(dashboard, main_pc2_ip)
    
    print(f"UI Application started. Connecting to Main Hub at {main_pc2_ip}")

    dashboard.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
