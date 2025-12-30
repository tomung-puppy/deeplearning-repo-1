# ui/dashboard_v2.py
"""
Enhanced AI Smart Cart Dashboard
- 3 states: Standby, Shopping, Checkout
- Real-time cart updates with toast notifications
- Obstacle warnings and safety alerts
- Shopping timer and session management
"""

import sys
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QFrame,
    QStackedWidget,
    QDialog,
    QMessageBox,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor


class DangerLevel(Enum):
    NORMAL = 0
    CAUTION = 1
    CRITICAL = 2


class CartState(Enum):
    STANDBY = "standby"
    SHOPPING = "shopping"
    CHECKOUT = "checkout"


class LEDWidget(QFrame):
    """LED indicator for obstacle status"""

    def __init__(self, size: int = 60):
        super().__init__()
        self.setFixedSize(size, size)
        self.current_level = DangerLevel.NORMAL
        self._update_style()

    def set_level(self, level: DangerLevel):
        self.current_level = level
        self._update_style()

    def _update_style(self):
        color_map = {
            DangerLevel.NORMAL: "#4CAF50",  # Green
            DangerLevel.CAUTION: "#FFC107",  # Yellow
            DangerLevel.CRITICAL: "#F44336",  # Red
        }
        color = color_map[self.current_level]
        radius = self.width() // 2
        self.setStyleSheet(
            f"""
            background-color: {color};
            border-radius: {radius}px;
            border: 3px solid #ddd;
        """
        )


class ToastNotification(QWidget):
    """Toast notification for product added feedback"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        layout = QHBoxLayout()
        self.setLayout(layout)

        self.label = QLabel()
        self.label.setStyleSheet(
            """
            QLabel {
                background-color: rgba(76, 175, 80, 220);
                color: white;
                padding: 15px 25px;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
        """
        )
        layout.addWidget(self.label)

        # Animation
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")

    def show_message(self, message: str, duration: int = 3000):
        """Show toast message with fade in/out animation"""
        self.label.setText(message)
        self.adjustSize()

        # Position at bottom center of parent
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 50
            self.move(x, y)

        # Fade in
        self.opacity_effect.setOpacity(0)
        self.show()

        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.start()

        # Auto hide after duration
        QTimer.singleShot(duration, self._fade_out)

    def _fade_out(self):
        self.animation.setDuration(300)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.finished.connect(self.hide)
        self.animation.start()


class CheckoutDialog(QDialog):
    """Checkout confirmation dialog"""

    def __init__(self, total_price: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Checkout Confirmation")
        self.setModal(True)
        self.setFixedSize(450, 250)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Title
        title = QLabel("🛒 Complete Your Shopping?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        layout.addWidget(title)

        layout.addSpacing(20)

        # Total amount
        amount_label = QLabel(f"Total Amount: ₩{total_price:,}")
        amount_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        amount_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        amount_label.setStyleSheet("color: #2196F3;")
        layout.addWidget(amount_label)

        layout.addSpacing(30)

        # Buttons
        btn_layout = QHBoxLayout()

        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.setFixedHeight(50)
        cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #757575;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """
        )
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("✅ Confirm")
        confirm_btn.setFixedHeight(50)
        confirm_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)


class CartDashboard(QMainWindow):
    """
    Enhanced AI Smart Cart Dashboard with 3 states:
    - STANDBY: Initial screen showing cart availability
    - SHOPPING: Active shopping with cart items display
    - CHECKOUT: Confirmation before ending session
    """

    # Signals
    start_shopping_signal = pyqtSignal()
    end_shopping_signal = pyqtSignal()
    confirm_checkout_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("AI Smart Cart Dashboard")
        self.setFixedSize(1024, 768)

        # State
        self.current_state = CartState.STANDBY
        self.cart_items: List[Dict] = []
        self.total_price: int = 0
        self.session_start_time: Optional[datetime] = None
        self.session_id: Optional[int] = None

        # Timer for shopping duration
        self.shopping_timer = QTimer()
        self.shopping_timer.timeout.connect(self._update_timer)

        # Build UI
        self._build_ui()
        self._switch_to_standby()

    def _build_ui(self):
        """Build main UI with stacked widget for different states"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Stacked widget for 3 states
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Create pages
        self.standby_page = self._create_standby_page()
        self.shopping_page = self._create_shopping_page()

        self.stacked_widget.addWidget(self.standby_page)
        self.stacked_widget.addWidget(self.shopping_page)

        # Toast notification
        self.toast = ToastNotification(self)

    def _create_standby_page(self) -> QWidget:
        """Create standby/welcome screen"""
        page = QWidget()
        layout = QVBoxLayout()
        page.setLayout(layout)

        layout.addStretch()

        # Cart icon and title
        icon = QLabel("🛒")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Arial", 120))
        layout.addWidget(icon)

        title = QLabel("AI Smart Cart Ready")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Tap 'Start Shopping' to begin")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Arial", 18))
        subtitle.setStyleSheet("color: #757575;")
        layout.addWidget(subtitle)

        layout.addSpacing(50)

        # Start button
        self.start_btn = QPushButton("🛍️  Start Shopping")
        self.start_btn.setFixedSize(300, 70)
        self.start_btn.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.start_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        self.start_btn.clicked.connect(self._on_start_shopping)

        btn_container = QHBoxLayout()
        btn_container.addStretch()
        btn_container.addWidget(self.start_btn)
        btn_container.addStretch()
        layout.addLayout(btn_container)

        layout.addStretch()

        return page

    def _create_shopping_page(self) -> QWidget:
        """Create active shopping screen"""
        page = QWidget()
        layout = QVBoxLayout()
        page.setLayout(layout)

        # Header
        header = self._create_header()
        layout.addLayout(header)

        # Body (cart table + info panel)
        body = QHBoxLayout()

        # Left: Cart table
        left_panel = self._create_cart_table_panel()
        body.addWidget(left_panel, stretch=3)

        # Right: Info panel
        right_panel = self._create_info_panel()
        body.addWidget(right_panel, stretch=1)

        layout.addLayout(body)

        # Footer
        footer = self._create_footer()
        layout.addLayout(footer)

        return page

    def _create_header(self) -> QHBoxLayout:
        """Create header with title and timer"""
        header = QHBoxLayout()

        title = QLabel("🛒 Shopping in Progress")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # Shopping timer
        timer_label = QLabel("⏱️ Shopping Time:")
        timer_label.setFont(QFont("Arial", 14))
        header.addWidget(timer_label)

        self.timer_value = QLabel("00:00:00")
        self.timer_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.timer_value.setStyleSheet("color: #2196F3;")
        header.addWidget(self.timer_value)

        return header

    def _create_cart_table_panel(self) -> QFrame:
        """Create cart items table panel"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # Title
        title = QLabel("📦 Cart Items")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Product", "Price", "Qty", "Subtotal"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        assert header is not None
        header.setStretchLastSection(True)
        header.setDefaultSectionSize(150)

        layout.addWidget(self.table)

        return panel

    def _create_info_panel(self) -> QFrame:
        """Create right info panel with LED and total"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # Obstacle status
        obstacle_title = QLabel("⚠️ Obstacle Status")
        obstacle_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        obstacle_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(obstacle_title)

        self.led = LEDWidget(80)
        led_container = QHBoxLayout()
        led_container.addStretch()
        led_container.addWidget(self.led)
        led_container.addStretch()
        layout.addLayout(led_container)

        self.obstacle_text = QLabel("No Obstacles")
        self.obstacle_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.obstacle_text.setFont(QFont("Arial", 12))
        layout.addWidget(self.obstacle_text)

        layout.addSpacing(30)

        # Total price
        total_title = QLabel("💰 Total Amount")
        total_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(total_title)

        self.total_label = QLabel("₩ 0")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #4CAF50;")
        layout.addWidget(self.total_label)

        layout.addSpacing(20)

        # Item count
        self.item_count_label = QLabel("0 items")
        self.item_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.item_count_label.setFont(QFont("Arial", 12))
        self.item_count_label.setStyleSheet("color: #757575;")
        layout.addWidget(self.item_count_label)

        layout.addStretch()

        return panel

    def _create_footer(self) -> QHBoxLayout:
        """Create footer with action buttons"""
        footer = QHBoxLayout()

        footer.addStretch()

        self.end_btn = QPushButton("🏁 Finish Shopping")
        self.end_btn.setFixedSize(200, 50)
        self.end_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.end_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #FF5722;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
        """
        )
        self.end_btn.clicked.connect(self._on_end_shopping)
        footer.addWidget(self.end_btn)

        return footer

    # =========================
    # State Management
    # =========================
    def _switch_to_standby(self):
        """Switch to standby state"""
        self.current_state = CartState.STANDBY
        self.stacked_widget.setCurrentWidget(self.standby_page)
        self.shopping_timer.stop()

    def _switch_to_shopping(self):
        """Switch to shopping state"""
        self.current_state = CartState.SHOPPING
        self.stacked_widget.setCurrentWidget(self.shopping_page)
        self.session_start_time = datetime.now()
        self.shopping_timer.start(1000)  # Update every second

    def _on_start_shopping(self):
        """Start shopping button clicked"""
        self.start_shopping_signal.emit()
        self.reset_cart()
        self._switch_to_shopping()

    def _on_end_shopping(self):
        """End shopping button clicked"""
        # Show checkout confirmation dialog
        dialog = CheckoutDialog(self.total_price, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.confirm_checkout_signal.emit()
            self._switch_to_standby()
            self.reset_cart()

    def _update_timer(self):
        """Update shopping timer display"""
        if self.session_start_time:
            elapsed = datetime.now() - self.session_start_time
            hours = int(elapsed.total_seconds() // 3600)
            minutes = int((elapsed.total_seconds() % 3600) // 60)
            seconds = int(elapsed.total_seconds() % 60)
            self.timer_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    # =========================
    # Public API (Controller uses these)
    # =========================
    def update_cart_display(self, items: List[Dict], total: int):
        """
        Update cart display with full cart data from DB
        items = [
            {
                product_id,
                product_name,
                price,
                quantity,
                subtotal
            },
            ...
        ]
        """
        print(f"[Dashboard] Updating cart: {len(items)} items, total=₩{total}")

        # Group by product_id
        grouped_items = {}
        for item in items:
            product_id = item["product_id"]
            if product_id in grouped_items:
                grouped_items[product_id]["quantity"] += item["quantity"]
                grouped_items[product_id]["subtotal"] += item["subtotal"]
            else:
                grouped_items[product_id] = {
                    "product_name": item["product_name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                    "subtotal": item["subtotal"],
                }

        # Update table
        self.table.setRowCount(0)
        for product_id, item in grouped_items.items():
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(item["product_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"₩{item['price']:,}"))
            self.table.setItem(row, 2, QTableWidgetItem(str(item["quantity"])))
            self.table.setItem(row, 3, QTableWidgetItem(f"₩{item['subtotal']:,}"))

        # Update total
        self.total_price = total
        self.total_label.setText(f"₩{self.total_price:,}")

        # Update item count
        total_items = sum(item["quantity"] for item in grouped_items.values())
        self.item_count_label.setText(
            f"{total_items} item{'s' if total_items != 1 else ''}"
        )

    def show_product_added(self, product_name: str):
        """Show toast notification when product is added"""
        self.toast.show_message(f"✅ {product_name} added to cart!")

    def set_danger_level(self, level: DangerLevel, message: str = ""):
        """Update obstacle danger level"""
        self.led.set_level(level)

        if level == DangerLevel.CRITICAL:
            self.obstacle_text.setText(f"⚠️ {message or 'Critical Warning!'}")
            self.obstacle_text.setStyleSheet("color: #F44336; font-weight: bold;")
        elif level == DangerLevel.CAUTION:
            self.obstacle_text.setText(f"⚠️ {message or 'Caution'}")
            self.obstacle_text.setStyleSheet("color: #FFC107; font-weight: bold;")
        else:
            self.obstacle_text.setText("✅ Clear")
            self.obstacle_text.setStyleSheet("color: #4CAF50;")

    def reset_cart(self):
        """Reset cart to empty state"""
        self.cart_items.clear()
        self.total_price = 0
        self.table.setRowCount(0)
        self.total_label.setText("₩ 0")
        self.item_count_label.setText("0 items")
        self.session_start_time = None
        self.timer_value.setText("00:00:00")

    def set_session_id(self, session_id: int):
        """Set current shopping session ID"""
        self.session_id = session_id


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CartDashboard()
    window.show()
    sys.exit(app.exec())
