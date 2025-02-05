import sys
import os
import datetime
import base64
import subprocess
import tempfile
from PIL import Image
from openai import OpenAI
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtGui import QAction, QIcon, QMovie, QClipboard, QPixmap
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt

class LaTeXPreviewWindow(QMainWindow):
    def __init__(self, latex_content):
        super().__init__()
        self.setWindowTitle("LaTeX Preview")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create main widget and layout
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        # Setup image preview
        self.image_label = QLabel()
        self.image_label.setMinimumSize(800, 600)
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label)
        
        # Setup HTML/LaTeX preview
        self.browser = QWebEngineView()
        self.browser.setMinimumHeight(200)  # Ensure some space for the LaTeX content
        layout.addWidget(self.browser)
        
        # Setup copy button
        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.copy_button)
        
        self.setCentralWidget(main_widget)
        self.html_content = latex_content
        self.render_latex(latex_content)
    
    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.html_content)
        print("HTML content copied to clipboard!")

    def stop_loading_spinner(self):
        self.loading_movie.stop()
        self.loading_label.hide()

    def set_image(self, image_path):
        pixmap = QPixmap(image_path)
        self.image_label.setPixmap(pixmap)
        
        # Resize window to fit the image plus some padding
        window_width = pixmap.width() + 50
        window_height = pixmap.height() + 100
        self.resize(window_width, window_height)

    def render_latex(self, latex_content):
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script type="text/javascript" async
                src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML">
            </script>
            <style>
                body {{ 
                    font-family: Arial, sans-serif;
                    font-size: 16px;
                    padding: 20px;
                    line-height: 1.6;
                }}
            </style>
        </head>
        <body>
            {latex_content}
        </body>
        </html>
        """
        self.browser.setHtml(html_template)

class ScreenCaptureApp(QSystemTrayIcon):
    def __init__(self):
        super().__init__(QIcon("/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns"))
        
        self.latex_output = ""
        
        self.menu = QMenu()
        self.capture_action = QAction("Capture Screen")
        self.capture_action.triggered.connect(self.capture_screen)
        self.menu.addAction(self.capture_action)
        
        self.menu.addSeparator()
        
        self.quit_action = QAction("Quit")
        self.quit_action.triggered.connect(QApplication.quit)
        self.menu.addAction(self.quit_action)
        
        self.setContextMenu(self.menu)
        self.show()

    def capture_screen(self):
        screenshot_path = self.get_screenshot_path()
        command = ["screencapture", "-i", screenshot_path]
        subprocess.run(command)
        
        # Ensure the screenshot file is created before proceeding
        import time
        retries = 5
        while retries > 0 and not os.path.exists(screenshot_path):
            time.sleep(0.5)
            retries -= 1
        
        if not os.path.exists(screenshot_path):
            print("Error: Screenshot file not found.")
            return
        
        # First get the LaTeX output and markdown content
        self.latex_output = self.convert_image_to_latex(screenshot_path)
        # Then show the window
        self.show_latex_window(screenshot_path)
        self.preview_window.render_latex(self.latex_output)
        print("Extracted LaTeX Output:\n", self.latex_output)
    
    def get_screenshot_path(self):
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return os.path.join(temp_dir, f"screenshot_{timestamp}.png")
    
    def show_latex_window(self, screenshot_path=None):
        self.preview_window = LaTeXPreviewWindow(self.latex_output)
        self.preview_window.html_content = self.html_content
        if screenshot_path:  # Only try to set image if we have a path
            self.preview_window.set_image(screenshot_path)
        self.preview_window.show()
        self.preview_window.raise_()
        self.preview_window.activateWindow()
    
    def convert_image_to_latex(self, image_path):
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")
            client = OpenAI()
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Output only the direct HTML with LaTeX math notation. For math, use \\[...\\] for display math and \\(...\\) for inline math. For text, use HTML paragraphs. Do not include any meta commentary or markdown code blocks."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "data:image/png;base64," + image_data}
                                }
                            ]
                        }
                    ],
                    max_tokens=500
                )
                self.html_content = response.choices[0].message.content
                return self.html_content
                
            except Exception as e:
                error_msg = f"Error extracting LaTeX: {str(e)}"
                print(error_msg)
                self.html_content = error_msg
                return error_msg

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tray_app = ScreenCaptureApp()
    sys.exit(app.exec())
