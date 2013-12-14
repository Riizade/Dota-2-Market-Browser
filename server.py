import flask
import json

app = Flask(__name__)
app.debug = True

@app.route('/')
def _():
    return render_template("index.html")
