from items import *
from flask import *

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

app = Flask(__name__)

#------------------------------------------------------------------------------
# URL Routing
#------------------------------------------------------------------------------

@app.route('/')
def _():
    return render_template("index.html")

@app.route('/market/')
def market():
    session = SessionInstance()
    logging.info('Market page accessed')
    results = session.query(MarketItem).all()
    session.close()
    return render_template("market.html", items=results)

#------------------------------------------------------------------------------
# Script Logic
#------------------------------------------------------------------------------
if (not os.path.exists('items.db')):
    init_db()

continuous_update()


