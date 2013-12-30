from items import *
from flask import *

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

app = Flask(__name__)

#------------------------------------------------------------------------------
# URL Routing
#------------------------------------------------------------------------------

def filter_results(results, attr, value):
    if not value == None:
        results = [i for i in results if getattr(i, attr) == value]
    return results


@app.route('/')
def _():
    return render_template("index.html")

@app.route('/market/')
def market():
    session = SessionInstance()
    logging.info('Market page accessed')
    results = session.query(MarketItem).all()
    session.close()

    #filter results
    queries = [
            'hero',
            'item_slot',
            'item_type',
            'item_set',
            'quality']

    for query in queries:
        results = filter_results(results, query, request.args.get(query))

    #sort results
    asc = (request.args.get('asc') == 'yes')
    results.sort(key=lambda x: getattr(x, request.args.get('sort')), reverse=asc)



    return render_template("market.html", items=results)

#------------------------------------------------------------------------------
# Script Logic
#------------------------------------------------------------------------------
if (not os.path.exists('items.db')):
    init_db()

#continuous_update()


