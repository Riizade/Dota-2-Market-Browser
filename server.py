from flask import *
import json
from sqlalchemy import *
from BeautifulSoup import BeautifulSoup
import httplib2

app = Flask(__name__)
app.debug = True

#------------------------------------------------------------------------------
# Database Operations
#------------------------------------------------------------------------------
engine = create_engine('sqlite:///:memory:', echo=True)
Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'

    name = Column(String, primary_key=True)
    quantity = Column(Integer)
    price = Column(Float)
    set = Column(String)
    image_url_large = Column(String)
    image_url_small = Column(String)
    item_type = Column(String)
    item_slot = Column(String)
    hero = Column(String)



#usage:
#takes a starting page (set of 100 items)
#returns the starting page to be used for the next call to ensure that there
#are no duplicates and that the function doesn't ask for more items than exist
def update_items(page_start):
    page_count = 100

    #get 100 items from Dota 2 Community Market
    resp, content = httplib2.Http().request(
        "http://steamcommunity.com/market/search/render/?query=appid%3A570&start=" 
        + str(page_start) + "&count=" + str(page_count))

    #DEBUG for working from file
    #content = open('workfile.html', 'r').read()

    request = json.loads(content)

    content = request['results_html']
    soup = BeautifulSoup(content)

    #replace individual characters to clean up the HTML
    temp_str = soup.prettify()
    #remove \r, \n, \t, &gt, &lt, ;, \/span, \/div, \/a, }, &#36, USD, , (yes, the comma)
    temp_str = temp_str.replace('\\r', '').replace('\\n', '').replace('\\t', '')
    temp_str = temp_str.replace('&gt', '').replace('&lt', '').replace(';', '')
    temp_str = temp_str.replace('\\/span', '').replace('\\/div', '').replace('\\/a', '')
    temp_str = temp_str.replace('&#36', '').replace('}', '').replace('USD', '').replace(',', '')

    soup = BeautifulSoup(temp_str)

    for i in soup.findAll('a'):
        quantity = i.div.div.span.span.contents[0].strip('\n\r ')
        price = i.div.div.span.contents[6].strip('\n\r ')
        name = i.div.contents[5].span.contents[0].strip('\n\r ')

        #update item in database
        #TODO

    if (page_start + page_count >= int(request['total_count'])):
        page_start = 0
    else:
        page_start += 100

    return page_start

#------------------------------------------------------------------------------
# URL Routing
#------------------------------------------------------------------------------

@app.route('/')
def _():
    return render_template("index.html")

@app.route('/market/')
def market():
    return render_template("market.html")


if __name__ == '__main__':
    app.run()
