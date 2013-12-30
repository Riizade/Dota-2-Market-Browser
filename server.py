from items import *
from flask import *

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

app = Flask(__name__)

#------------------------------------------------------------------------------
# URL Routing
#------------------------------------------------------------------------------

def filter_attribute(results, attr, value):
    if not value == None:
        results = [i for i in results if getattr(i, attr) == value]
    return results

def filter_results(request, results):
     #equality filters
    queries = [
            'hero',
            'item_slot',
            'item_type',
            'item_set',
            'quality']
    for query in queries:
        results = filter_attribute(results, query, request.args.get(query))

    #price filters
    price_min = request.args.get('price_min')
    if not price_min == None:
        results = [i for i in results if getattr(i, 'price') >= float(price_min)]
    price_max = request.args.get('price_max')
    if not price_max == None:
        results = [i for i in results if getattr(i, 'price') <= float(price_max)]


    #sort results
    desc = (request.args.get('desc') == 'yes')
    if not request.args.get('sort') == None:
        results.sort(key=lambda x: getattr(x, request.args.get('sort')), reverse=desc)

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

    results = filter_results(request, results)
    return render_template("market.html", items=results)

#------------------------------------------------------------------------------
# Script Logic
#------------------------------------------------------------------------------
if (not os.path.exists('items.db')):
    init_db()

#continuous_update()


