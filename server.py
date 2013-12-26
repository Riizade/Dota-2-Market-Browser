from flask import *
import json
from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from BeautifulSoup import BeautifulSoup
import httplib2
import re
import os
import os.path
import unicodedata

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

app = Flask(__name__)

#DEBUG remove database every time
os.remove('items.db')

engine = create_engine('sqlite:///items.db', echo=True)
Base = declarative_base()
SessionInstance = sessionmaker(bind=engine)

class Item(Base):
    __tablename__ = 'items'

    defindex = Column(Integer, primary_key=True)
    name_slug = Column(String)
    name = Column(String)
    set = Column(String)
    image_url_large = Column(String)
    image_url_small = Column(String)
    item_type = Column(String)
    item_slot = Column(String)
    hero = Column(String)

class MarketItem(Base):
    __tablename__ = 'market_items'

    name = Column(String, primary_key=True)
    name_slug = Column(String)
    quantity = Column(Integer)
    price = Column(Float)
    quality = Column(Integer)
    quality_color = Column(String)
    market_link = Column(String)

#gets items from the dota 2 schema
def get_items():
    #DEBUG for working from file
    items = json.load(open('dota2_schema.json', 'r'))

    session = SessionInstance()

    for i in items['result']['items']:
        if (i['defindex'] < 900):
            print('Skipping default item')
            continue

        #get image if it doesn't exist
        if not os.path.exists('./static/assets/images/' + slugify(i['name']) + '.png'):
            resp, content = httplib2.Http().request(i['image_url_large'])
            #save small image
            with open('./static/assets/images/' + slugify(i['name']) + '.png', 'w+') as f:
                f.write(content)

        session.add(Item(
                    name_slug=slugify(i['name']), 
                    item_type=parse_item_type(i), 
                    item_slot=parse_item_slot(i), 
                    image_url_large=i['image_url_large'],
                    image_url_small=i['image_url'], 
                    hero=get_hero(i['image_url']),
                    name=i['name'],
                    defindex=i['defindex']))

    session.commit()
    session.close()

def get_hero(image_url):
    search = re.search('(?<=icons/econ/items/)\w+', image_url)
    if (search):
        name = search.group(0)
    else:
        name = 'None'

    return name

def slugify(s):
    slug = unicodedata.normalize('NFKD', s)
    slug = slug.encode('ascii', 'ignore').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'[-]+', '-', slug)

    return slug

def parse_item_type(item):
    if (item['item_class'] == 'dota_item_wearable'):
        item_type = 'Equipment'
    elif (item['item_class'] == 'tool'):
        try:
            item_type = item['tool']['type']
        except KeyError:
            item_type = item['attributes'][0]['name']
    elif (item['item_class'] == 'supply_crate'):
        item_type = 'Treasure Chest'
    else:
        item_type = 'Unknown'

    return item_type

def parse_item_slot(item):
    if (not item['item_class'] == 'dota_item_wearable'):
        return 'None'
    else:
        search = re.search('(?<=DOTA_WearableType_)\w+', item['item_type_name'])
        if (search):
            return search.group(0)
        else:
            return 'None'

def parse_quality(name):
    qualities =['Inscribed',
                'Heroic',
                'Genuine',
                'Cursed',
                'Corrupted',
                'Unusual',
                'Elder',
                'Frozen',
                'Self-Made',
                'Autographed']
    for quality in qualities:
        if (re.search(quality, name)):
            return quality
       
    #return 'Normal' if no quality matches 
    return 'Normal'

def quality_color(quality):
    if (quality == 'Frozen'):
        return "#4983B3"
    elif (quality == 'Corrupted'):
        return "#A32C2E"
    elif (quality == 'Cursed'):
        return "#8650AC"
    elif (quality == 'Genuine'):
        return "#4D7455"
    elif (quality == 'Unusual' or quality == 'Heroic'):
        return "#8650AC"
    elif (quality == 'Elder'):
        return "#476291"
    elif (quality == 'Self-Made'):
        return "#70B04A"
    else:
        return "#FFFFFF"

def init_db():
    Item.metadata.create_all(bind=engine)
    MarketItem.metadata.create_all(bind=engine)

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

    #create sql session to add items to the database
    session = SessionInstance()

    for i in soup.findAll('a'):
        name = i.div.contents[5].span.contents[0].strip('\n\r ')
        name_slug = slugify(name)
        quantity = int(i.div.div.span.span.contents[0].strip('\n\r '))
        price = float(i.div.div.span.contents[6].strip('\n\r '))
        market_link = i['href']
        quality = parse_quality(name)
        quality_color = quality_color(quality)


        try:
            tmp_item = session.query(MarketItem).filter(MarketItem.name==name)
            #update item in database
            tmp_item.name = name
            tmp_item.quantity = quantity
            tmp_item.price = price
            tmp_item.name_slug = name_slug
            tmp_item.market_link = market_link
            tmp_item.quality = quality
            tmp_item.quality_color = quality_color

        except ValueError:
            session.add(MarketItem(name=name, name_slug=name_slug, quantity=quantity,
                        price=price, market_link=market_link, quality=quality,
                        quality_color=quality_color))


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
