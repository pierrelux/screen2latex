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
        self.setGeometry(100, 100, 800, 400)
        
        self.browser = QWebEngineView()
        layout = QVBoxLayout()
        
        self.image_label = QLabel()
        layout.addWidget(self.image_label)
        
        self.loading_label = QLabel()
        self.loading_movie = QMovie("/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/ProgressIndeterminate.gif")
        self.loading_label.setMovie(self.loading_movie)
        self.loading_movie.start()
        layout.addWidget(self.loading_label)
        layout.addWidget(self.browser)
        
        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.copy_button)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.markdown_content = latex_content  # Store original markdown content
        self.render_latex(latex_content)
    
    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.markdown_content)
        print("Markdown copied to clipboard!")

    def stop_loading_spinner(self):
        self.loading_movie.stop()
        self.loading_label.hide()

    def set_image(self, image_path):
        pixmap = QPixmap(image_path)
        self.image_label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio))

    def render_latex(self, latex_content):
        self.stop_loading_spinner()
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <script type="text/javascript" async
          src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML">
        </script>
        </head>
        <body>
        <div style='font-size: 20px;'>
        {latex_content}
        </div>
        </body>
        </html>
        """
        self.browser.setHtml(html_template)

class ScreenCaptureApp(QSystemTrayIcon):
    def __init__(self):
        super().__init__(QIcon("/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns"))
        self.latex_output = ""
        self.html_content = ""  # Initialize html_content
        self.markdown_content = ""  # Initialize markdown_content
        
        self.menu = QMenu()
        self.capture_action = QAction("Capture Screen")
        self.capture_action.triggered.connect(self.capture_screen)
        self.menu.addAction(self.capture_action)
        
        self.preview_action = QAction("Show LaTeX Output")
        self.preview_action.triggered.connect(self.show_latex_window)
        self.menu.addAction(self.preview_action)
        
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
        
        # First convert image to get both HTML and markdown content
        self.latex_output = self.convert_image_to_latex(screenshot_path)
        
        # Create and show the preview window only after we have the content
        self.preview_window = LaTeXPreviewWindow(self.latex_output)
        self.preview_window.markdown_content = self.markdown_content
        self.preview_window.set_image(screenshot_path)
        self.preview_window.show()
        self.preview_window.raise_()
        self.preview_window.activateWindow()
        self.preview_window.render_latex(self.latex_output)
    
    def get_screenshot_path(self):
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return os.path.join(temp_dir, f"screenshot_{timestamp}.png")
    
    def show_latex_window(self, screenshot_path):
        self.preview_window = LaTeXPreviewWindow(self.latex_output)
        self.preview_window.markdown_content = self.markdown_content
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
                                    "text": "Extract content from the image in two formats - HTML and Markdown. Follow these guidelines:\n\n"
                                           "1. Provide two versions separated by '---'\n"
                                           "2. HTML version (first):\n"
                                           "   - Regular text in <p> tags\n"
                                           "   - Math expressions in $$...$$\n"
                                           "   - Equations that should be on separate lines in \\begin{align}...\\end{align}\n"
                                           "3. Markdown version (second):\n"
                                           "   - Regular text in standard markdown\n"
                                           "   - Inline math in $...$ \n"
                                           "   - Display math in $$...$$\n"
                                           "4. Do not include any markdown code blocks or explanatory text in the output."
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
                content = response.choices[0].message.content
                print("\nRAW OPENAI RESPONSE:")
                print("=" * 50)
                print(content)
                print("=" * 50 + "\n")
                
                # Clean up the content
                content = content.strip()
                
                # Split on "---" surrounded by newlines
                if '\n---\n' in content:
                    html_version, markdown_version = content.split('\n---\n')
                else:
                    html_version = content
                    markdown_version = content
                
                self.html_content = html_version.strip()
                self.markdown_content = markdown_version.strip()
                return self.html_content
                
            except Exception as e:
                print("Error extracting content:", str(e))
                return "Extraction failed. Please try again with a clearer image."

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tray_app = ScreenCaptureApp()
    sys.exit(app.exec())
