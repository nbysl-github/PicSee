
import sys
import json
import time
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer

class TestRunner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.view = QWebEngineView()
        self.setCentralWidget(self.view)
        self.resize(1920, 1080)
        self.view.loadFinished.connect(self.on_load_finished)
        # Load the absolute path to waterfall.html
        import os
        path = os.path.abspath("waterfall.html")
        self.view.load(QUrl.fromLocalFile(path))
        self.test_id = None
        self.results = {}

    def on_load_finished(self):
        print("Page loaded, starting Directory Switch test...")
        # Start the test
        self.view.page().runJavaScript("startDirectorySwitchUnitTest('ds-123')")
        
        # Poll for results
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_result)
        self.timer.start(500)

    def check_result(self):
        self.view.page().runJavaScript("getDirectorySwitchUnitTestResult('ds-123')", self.handle_result)

    def handle_result(self, res):
        if res and res.get('status') == 'done':
            self.timer.stop()
            print("Test Result:", json.dumps(res['result'], indent=2))
            if res['result'].get('success'):
                print("PASSED")
                sys.exit(0)
            else:
                print("FAILED")
                sys.exit(1)
        elif res and res.get('status') == 'error':
            self.timer.stop()
            print("Test Error:", res.get('error'))
            sys.exit(1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    runner = TestRunner()
    runner.show()
    sys.exit(app.exec_())
