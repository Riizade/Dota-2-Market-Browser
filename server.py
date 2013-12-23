from flask import *
import json

app = Flask(__name__)
app.debug = True

@app.route('/')
def _():
    return render_template("index.html")

@app.route('/market/')
def market():
    return render_template("market.html")


if __name__ == '__main__':
    app.run()
