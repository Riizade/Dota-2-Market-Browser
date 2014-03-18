from items import *
from flask import *

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

app = Flask(__name__)
#add functions to template
app.jinja_env.globals.update(page_url=page_url)

#------------------------------------------------------------------------------
# URL Routing
#------------------------------------------------------------------------------

# Filters the list of results to only contain items where (attr == value)
def filter_attribute(results, attr, value):
    if not value == None:
        results = [i for i in results if getattr(i, attr) == value]
    return results

# Takes the current request url and modifies it to point to a different page
def page_url(cur_url, page_num):
    if (re.search('p=[0-9]*', cur_url)):
        return re.sub('p=[0-9]*', 'p=' + str(page_num), cur_url)
    elif ('?' in cur_url):
        return cur_url + '&p=' + str(page_num)
    else:
        return cur_url + '?p=' + str(page_num)


# Parses a request string and uses it to filter item search results
# Returns a list containing the item results
def filter_results(request, results):
    # Equality filters (filters without ranges of values)
    queries = [
            'hero',
            'item_slot',
            'item_type',
            'item_set',
            'quality']
    for query in queries:
        results = filter_attribute(results, query, request.args.get(query))

    # Filter by price
    price_min = request.args.get('price_min')
    if not price_min == None:
        results = [i for i in results if getattr(i, 'price') >= float(price_min)]
    price_max = request.args.get('price_max')
    if not price_max == None:
        results = [i for i in results if getattr(i, 'price') <= float(price_max)]


    # Sort the results
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

    page = request.args.get('p')
    if page == None:
        page = 1
    else:
        page = int(page)

    results_page = results[(page-1)*20:(page*20)-1]

    return render_template("market.html", items=results_page, cur_url=request.url, num_pages=(len(results)%20))

#------------------------------------------------------------------------------
# Script Logic
#------------------------------------------------------------------------------

if (not os.path.exists('items.db')):
    init_db()


#continuous_update(3)


