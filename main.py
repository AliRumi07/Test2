from flask import Flask, render_template_string
import threading
import time
import webbrowser

app = Flask(__name__)

# HTML template with auto-refresh meta tag and JavaScript code
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="300">
    <title>Auto Refresh Page</title>
</head>
<body>
    <script type="text/javascript">
        atOptions = {
            'key' : 'b67bc9dfe217891d4f52e22e6d0b0b71',
            'format' : 'iframe',
            'height' : 60,
            'width' : 468,
            'params' : {}
        };
    </script>
    <script type="text/javascript" src="//www.highperformanceformat.com/b67bc9dfe217891d4f52e22e6d0b0b71/invoke.js"></script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

def open_browser():
    # Wait a moment to ensure the server is up
    time.sleep(1)
    webbrowser.open_new('http://0.0.0.0:8080')

if __name__ == '__main__':
    # Start the Flask server in a separate thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

    # Open the browser
    open_browser()
