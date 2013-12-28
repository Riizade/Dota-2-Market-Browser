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
    logging.debug('Market items returned:')
    logging.debug(session.query(MarketItem).all())
    results = session.query(MarketItem).all()
    session.close()
    return render_template("market.html", items=results)

#------------------------------------------------------------------------------
# Script Logic
#------------------------------------------------------------------------------
init_db()
