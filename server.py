from data import *
from flask import *

#------------------------------------------------------------------------------
# Filtering and Paging
#------------------------------------------------------------------------------

# Filters the list of results to only contain items where (attr == value)
def filter_attribute(results, attr, value):
    if not value == None:
        results = [i for i in results if getattr(i, attr) == value]
    return results

# Takes the current request url and modifies it to point to a different page
def page_url(cur_url, page_num):
    page_re = 'p=[0-9]*'
    # The case where a page is already specified
    if (re.search(page_re, cur_url) != None):
        cur_url = re.sub(page_re, 'p='+str(page_num), cur_url)
    # The case where there are previous arguments
    elif (re.search('\?+', cur_url) != None):
        cur_url = cur_url + '&p='+str(page_num)
    # The case where there are no previous arguments
    else:
        cur_url = cur_url+'?p='+str(page_num)

    return cur_url

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

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

app = Flask(__name__)
# Add functions to Jinja2 templates
app.jinja_env.globals.update(page_url=page_url)

#------------------------------------------------------------------------------
# URL Routing
#------------------------------------------------------------------------------

@app.route('/')
def _():
    return render_template("index.html")

@app.route('/market/')
def market():
    session = SessionInstance()
    # Get list of items
    results = session.query(MarketItem).all()
    # Get list of possible values for each field
    hero_list = session.query(Hero).all()
    slot_list = session.query(Slot).all()
    set_list = session.query(Set).all()
    type_list = session.query(Type).all()
    quality_list = []
    session.close()

    # Filter and sort data
    results = filter_results(request, results)
    hero_list.sort(key=lambda x: x.name, reverse=False)
    slot_list.sort(key=lambda x: x.name, reverse=False)
    set_list.sort(key=lambda x: x.name, reverse=False)
    type_list.sort(key=lambda x: x.name, reverse=False)


    page = request.args.get('p')
    if page == None:
        page = 1
    else:
        page = int(page)

    # Calculate the number of pages
    num_pages = len(results)/20
    if (len(results)%20 != 0):
        num_pages = num_pages + 1

    # Get the results present for this page
    results_page = results[(page-1)*20:(page*20)-1]

    logging.info('Market request: '+request.url+', '+str(len(results))+' items matched, '+str(num_pages)+' pages returned')

    return render_template("market.html", items=results_page, cur_url=request.url, num_pages=num_pages, heroes=hero_list, slots=slot_list, sets=set_list, types=type_list, qualities=quality_list)

#------------------------------------------------------------------------------
# Script Logic
#------------------------------------------------------------------------------

if (not os.path.exists('items.db')):
    init_db()

if settings.get('update_items', True):
    continuous_update(3)


