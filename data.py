from items import *
from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from BeautifulSoup import BeautifulSoup
from wand.image import Image
from wand.exceptions import BlobError
import json
import httplib2
import re
import os
import os.path
import logging
import time
import threading

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

settings = json.load(open('config.json'))
api_key = settings.get('api_key', '')

# Parse logging levels
log_num = settings.get('log_level', 0)
level = logging.ERROR
if log_num == 1:
    level = logging.CRITICAL
elif log_num == 2:
    level = logging.WARNING
elif log_num == 3:
    level = logging.INFO
elif log_num == 4:
    level = logging.DEBUG

log_num = settings.get('sql_log_level', 0)
sql_level = logging.ERROR
if log_num == 1:
    sql_level = logging.CRITICAL
elif log_num == 2:
    sql_level = logging.WARNING
elif log_num == 3:
    sql_level = logging.INFO
elif log_num == 4:
    sql_level = logging.DEBUG

# Delete db if requested
if settings.get('init_new_db', False):
    if os.path.isfile('items.db'):
        os.remove('items.db')

engine = create_engine('sqlite:///items.db', echo=False)
Base = declarative_base()
SessionInstance = sessionmaker(bind=engine)
logging.basicConfig(
        format='%(asctime)s %(levelname)s: %(message)s',
        filename='./logs/server-'+time.strftime('%Y-%m-%d_%H:%M:%S',time.gmtime())+'.log', 
        level=level)
sqlalchemy_log = logging.getLogger("sqlalchemy")
sqlalchemy_log.setLevel(sql_level)
sqlalchemy_log.propagate = True

class Item(Base):
    __tablename__ = 'items'

    defindex = Column(Integer, primary_key=True)
    name_slug = Column(String)
    name = Column(String)
    item_set = Column(String)
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
    item_set = Column(String)
    image_url_large = Column(String)
    image_url_small = Column(String)
    image_url_tiny = Column(String)
    item_type = Column(String)
    item_slot = Column(String)
    hero = Column(String)

# Downloads the Dota 2 item schema and inserts base items into the database
def get_schema():

    # Get item schema from Dota 2 API
    resp, content = httplib2.Http().request('http://api.steampowered.com/IEconItems_570/GetSchema/v0001/?key=' + api_key)

    while True:
        try:
            items = json.loads(content)
            break
        except ValueError:
            logging.error('Failed to load item schema from API, retrying...')

    session = SessionInstance()

    for i in items['result']['items']:
        if (i['defindex'] < 900):
            continue

        try:
            item_set = parse_set(i['item_set'])
        except KeyError:
            item_set = 'None'

        upsert(Item(
                name_slug=slugify(i['name']), 
                item_type=parse_type(get_item_type(i)), 
                item_slot=get_item_slot(i), 
                item_set=item_set,
                image_url_large=i['image_url_large'],
                image_url_small=i['image_url'], 
                hero=get_hero(i['image_url']),
                name=i['name'],
                defindex=i['defindex']))

    session.commit()
    session.close()

# Checks if the image has already been downloaded using the name
# Downloads the item image if it doesn't exist already
def download_image(name, url):
    count = 0

    base_name = slugify(basify(name))

    if not os.path.exists('./static/assets/images/' + base_name + '.png'):
        while count < 5:
            count = count + 1
            time.sleep(1)
            logging.info('Downloading image for '+name)
            resp, content = httplib2.Http().request(url)
            soup = BeautifulSoup(content)

            try:
                img_url = soup.find("div", { "class" : "market_listing_largeimage" }).img['src']
            except AttributeError:
                logging.error('Item '+name+' was unable to retrieve its image')
                time.sleep(3)
                continue

            logging.debug('Image for '+name+' is at url '+img_url)
            resp, content = httplib2.Http().request(img_url)

            try:
                with Image(blob=content) as img:
                    img.crop(4, 64, 352+4, 232+64)
                    img.save(filename='./static/assets/images/' + base_name + '.png')
                    return
            except BlobError:
                logging.error('Item '+name+' was unable to save its image')
                time.sleep(3)
                if os.path.exists('./static/assets/images/' + base_name + '.png'):
                    os.remove('./static/assets/images/' + base_name + '.png')
    if (count >= 5):
        logging.error('Skipping image for '+name)

# Updates an item if it already exists
# Inserts an item if it doesn't already exist
def upsert(item):

    session = SessionInstance()

    if type(item) is MarketItem:
        #if the item exists already
        try:
            tmp_item = session.query(MarketItem).filter(MarketItem.name==item.name)[0]
            #update item in database
            logging.debug('Updating market item: '+item.name)
            tmp_item.name = item.name
            tmp_item.quantity = item.quantity
            tmp_item.price = item.price
            tmp_item.name_slug = item.name_slug
            tmp_item.market_link = item.market_link
            tmp_item.quality = item.quality
            tmp_item.quality_color = item.quality_color
            tmp_item.item_set = item.item_set
            tmp_item.image_url_large = item.image_url_large
            tmp_item.image_url_small = item.image_url_small
            tmp_item.image_url_tiny = item.image_url_tiny
            tmp_item.item_type = item.item_type
            tmp_item.item_slot = item.item_slot
            tmp_item.hero = item.hero

        #if the item does not exist already
        except IndexError:
            logging.debug('Adding new market item: '+item.name)
            session.add(item)

    elif type(item) is Item:
        try:
            tmp_item = session.query(Item).filter(Item.defindex==item.defindex)[0]
            logging.debug('Updating base item: '+item.name)
            tmp_item.name = item.name
            tmp_item.name_slug = item.name_slug
            tmp_item.item_set = item.item_set
            tmp_item.image_url_large = item.image_url_large
            tmp_item.image_url_small = item.image_url_small
            tmp_item.item_type = item.item_type
            tmp_item.item_slot = item.item_slot
            tmp_item.hero = item.hero
            tmp_item.defindex = item.defindex

        except IndexError:
            logging.debug('Adding new base item: '+item.name)
            session.add(item)


    session.commit()
    session.close()

# Initializes the database by mining all available market pages
def init_db():
    logging.info('Initialiazing database')
    Item.metadata.create_all(bind=engine)
    MarketItem.metadata.create_all(bind=engine)

    get_schema()
    cur_page = 0
    #do-while Python
    while True:
        cur_page = update_items()
        time.sleep(2)
        if cur_page == 0:
            break

# Takes a starting market page number (set of 100 items) 
# Upserts all items on that page into the database
# Returns the starting page to be used for the next call to ensure that there
# are no duplicates and that the function doesn't ask for more items than exist
def update_items():

    item_count = 100
    logging.info('Updating items from '+str(update_items.cur_item)+' to '+str(update_items.cur_item+item_count-1))

    while True:
        try:
            # Get 100 items from Dota 2 Community Market
            resp, content = httplib2.Http().request(
                "http://steamcommunity.com/market/search/render/?query=appid%3A570&start=" 
                + str(update_items.cur_item) + "&count=" + str(item_count))

            request = json.loads(content)
            break
        except ValueError:
            logging.error('Failed to load items '+str(update_items.cur_item)+' to '+str(update_items.cur_item+item_count-1)+', retrying...')

    if (request['total_count'] == 0):
        logging.error('Market page returned no items')

    content = request['results_html']
    soup = BeautifulSoup(content)

    # Create an SQL session to add items to the database
    session = SessionInstance()

    #DEBUG
    f = open('market.html', 'w')
    f.write(content)
    f.close()

    for i in re.findall(r'market_listing_row_link.+?</a>', content, re.DOTALL):
        name = re.search('item_name.+?>(.+?)(</span>)', i).group(1)
        name_slug = slugify(basify(name))
        price = float(re.search('(?<=\&#36;)(.+?)(</span>)', i).group(1))
        quantity = int(re.search('(?<=qty">)(.+?)(</span>)', i).group(1).replace(',',''))
        market_link = re.search('href="(.+?)(")', i).group(1)
        image_url_tiny = re.search('<img.+?src="(.+?)(")', i).group(1)
        quality = quality_from_name(name)
        quality_color = colorize(quality)
        
        # Get base item
        try:
            base_item = session.query(Item).filter(Item.name_slug==name_slug)[0]
        except IndexError:
            logging.warning(name+' has no base item')
            base_item = Item(
                    name_slug=slugify(name), 
                    item_set='None',
                    image_url_large=image_url_tiny,
                    image_url_small=image_url_tiny, 
                    item_type=type_from_name(name),
                    item_slot=slot_from_name(name),
                    hero='None',
                    name=name)

        # Fill in missing fields using the base item
        item_set = base_item.item_set
        image_url_large = base_item.image_url_large
        image_url_small = base_item.image_url_small
        item_type = base_item.item_type
        item_slot = base_item.item_slot
        hero = base_item.hero

        # Upsert the MarketItem
        upsert(MarketItem(
                name=name,
                name_slug=name_slug,
                quantity=quantity,
                price=price,
                market_link=market_link,
                image_url_tiny=image_url_tiny,
                image_url_small=image_url_small,
                image_url_large=image_url_large,
                quality=quality,
                quality_color=quality_color,
                item_set=item_set,
                item_type=parse_type(item_type),
                item_slot=parse_slot(item_slot),
                hero=hero))

        download_image(name, market_link)

    # Update the value to be used for the next call in order to request pages
    # sequentially
    if (update_items.cur_item + item_count >= int(request['total_count'])):
        update_items.cur_item = 0
    else:
        update_items.cur_item += item_count

    # Close the session
    session.close()

    return update_items.cur_item

# Creates a static attribute of the update_items() function
update_items.cur_item = 0

# Periodically updates the database every (sec) seconds
def continuous_update(sec):
   update_items()
   threading.Timer(sec, continuous_update).start()