from flask import *
import json
from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from BeautifulSoup import BeautifulSoup
import httplib2
import re
import os

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

app = Flask(__name__)

engine = create_engine('sqlite:///items.db', echo=True)
Base = declarative_base()
SessionInstance = sessionmaker(bind=engine)

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

#gets items from the dota 2 schema
def get_items():
    #DEBUG for working from file
    items = json.load(open('dota2_schema.json', 'r'))

    session = SessionInstance()

    for i in items['result']['items']:
        session.add(Item(name=i['name'], item_type=i['item_class'], 
            item_slot=i['item_type_name'], image_url_large=i['image_url_large'],
            image_url_small=i['image_url'], hero=get_hero(i['image_url'])))
        session.commit()

    session.close()

def get_hero(image_url):
    search = re.search('(?<=icons/econ/items/)\w+', image_url)
    if (search):
        name = search.group(0)
    else:
        name = 'None'

    return name

def init_db():
    Item.metadata.create_all(bind=engine)
    get_items()
    cur_page = 0
    #do-while Python
    while True:
        cur_page = update_items(cur_page)
        if cur_page == 0:
            break

#usage:
#takes a starting page (set of 100 items)
#returns the starting page to be used for the next call to ensure that there
#are no duplicates and that the function doesn't ask for more items than exist
def update_items(current_page):
    item_count = 100

    #get 100 items from Dota 2 Community Market
    #resp, content = httplib2.Http().request(
    #    "http://steamcommunity.com/market/search/render/?query=appid%3A570&start=" 
    #    + str(current_page) + "&count=" + str(item_count))

    #DEBUG for working from file
    content = open('workfile.html', 'r').read()

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

    #create sql session to add items to the database
    session = SessionInstance()

    for i in soup.findAll('a'):
        name = i.div.contents[5].span.contents[0].strip('\n\r ')

        tmp_item = session.query(Item).filter(Item.name==name)
        #update item in database
        tmp_item.quantity = int(i.div.div.span.span.contents[0].strip('\n\r '))
        tmp_item.price = float(i.div.div.span.contents[6].strip('\n\r '))
        session.commit()

    if (current_page + item_count >= int(request['total_count'])):
        current_page = 0
    else:
        current_page += item_count

    #close the session
    session.close()

    return current_page

#------------------------------------------------------------------------------
# URL Routing
#------------------------------------------------------------------------------

@app.route('/')
def _():
    return render_template("index.html")

@app.route('/market/')
def market():
    session = SessionInstance()
    items = session.query(Item).all()
    session.close()
    return render_template("market.html", items=items)

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# Script Logic
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
init_db()
