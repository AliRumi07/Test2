from flask import Flask, render_template_string
import threading
import time
import webbrowser

app = Flask(__name__)

# URL to open and refresh
url_to_open = "https://www.profitablecpmrate.com/zjywtxpi?key=c2a6b1eca784188993e7fb397787d80b"

# HTML template with auto-refresh meta tag
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="300">
    <title>Auto Refresh Page</title>
</head>
<body>
    <iframe src="{{ url }}" width="100%" height="100%"></iframe>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template, url=url_to_open)

def open_browser():
    # Wait a moment to ensure the server is up
    time.sleep(1)
    webbrowser.open_new('http://0.0.0.0:8080')

if __name__ == '__main__':
    # Start the Flask server in a separate thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

    # Open the browser
    open_browser()
