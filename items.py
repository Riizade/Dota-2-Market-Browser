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
import logging
import time
import threading
from wand.image import Image
from wand.exceptions import BlobError

#------------------------------------------------------------------------------
# Setup
#------------------------------------------------------------------------------

settings = json.load(open('config.json'))
api_key = settings['api_key']
level = logging.ERROR
if settings['log_level'] == 1:
    level = logging.WARNING
elif settings['log_level'] == 2:
    level = logging.DEBUG

engine = create_engine('sqlite:///items.db', echo=False)
Base = declarative_base()
SessionInstance = sessionmaker(bind=engine)
logging.basicConfig(
        format='%(asctime)s %(levelname)s: %(message)s',
        filename='./logs/server-'+time.strftime('%Y-%m-%d_%H:%M:%S',time.gmtime())+'.log', 
        level=level)
sqlalchemy_log = logging.getLogger("sqlalchemy")
sqlalchemy_log.setLevel(level)
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

#gets items from the dota 2 schema
def get_schema():
    #DEBUG for working from file
    items = json.load(open('dota2_schema.json', 'r'))

    #get from network
    #resp, content = httplib2.Http().request('http://api.steampowered.com/IEconItems_570/GetSchema/v0001/?key=' + api_key)
    #items = json.loads(content)

    session = SessionInstance()

    for i in items['result']['items']:
        if (i['defindex'] < 900):
            continue

        try:
            item_set = properfy('_'.join(i['item_set'].split('_')[1:]))
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

def get_hero(image_url):
    search = re.search('(?<=icons/econ/items/)\w+', image_url)
    if (search):
        name = search.group(0)
    else:
        name = 'None'

    return hero_name(name)

# Checks if the image has already been downloaded using the name
# Downloads the item image if it doesn't exist already
def download_image(name, url):
    count = 0

    if not os.path.exists('./static/assets/images/' + slugify(basify(name)) + '.png'):
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
                    img.save(filename='./static/assets/images/' + slugify(basify(name)) + '.png')
                    return
            except BlobError:
                logging.error('Item '+name+' was unable to save its image')
                time.sleep(3)
                if os.path.exists('./static/assets/images/' + slugify(basify(name)) + '.png'):
                    os.remove('./static/assets/images/' + slugify(basify(name)) + '.png')
    if (count >= 5):
        logging.error('Skipping image for '+name)

# Converts names to a standard slug structure
def slugify(s):
    slug = unicodedata.normalize('NFKD', s)
    slug = slug.encode('ascii', 'ignore').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'[-]+', '-', slug)

    return slug

# Gets the item type as listed by the Dota 2 Schema
def get_item_type(item):

    if (item['item_class'] == 'tool'):
        try:
            item_type = item['tool']['type']
        except KeyError:
            item_type = item['attributes'][0]['name']
    else:
        item_type = item['item_class']

    return item_type

# Renames Valve's item types to make more sense
def parse_type(type_name):
    type_matches = [
            ['dota_item_wearable', 'Equipment'],
            ['supply_crate', 'Chest'],
            ['league_view_pass', 'Ticket'],
            ['pennant_upgrade', 'Pennant'],
            ['fortunate_soul', 'Booster'],
            ['gift', 'Bundle'],
            ['dynamic_recipe', 'Recipe'],
            ['decoder_ring', 'Key']
            ]
    for tm in type_matches:
        if type_name == tm[0]:
            return tm[1]

    return properfy(type_name)

# Determines an item's type from name alone in cases where the item has no schema entry
def type_from_name(name):
    name_matches = [
            ['Greevil', 'Courier'],
            ['Inscribed', 'Gem'],
            ['Prismatic', 'Gem'],
            ['Kinetic', 'Gem'],
            ['Ethereal', 'Gem'],
            ['Spectator', 'Gem'],
            ['Announcer', 'Announcer'],
            ['Mega-Kills', 'Announcer'],
            ['Egg', 'Egg'],
            ['Autograph:', 'Autograph'],
            ['Recipe:', 'Recipe']
            ]

    for nm in name_matches:
        if re.search(nm[0], name):
            return nm[1]

    return 'None'

# Determines an item's slot from its name in cases where the item has no schema entry
def slot_from_name(name):
    name_matches = [
        ['Greevil', 'Courier'],
        ['Inscribed', 'Inscribed Gem'],
        ['Prismatic', 'Prismatic Gem'],
        ['Kinetic', 'Kinetic Gem'],
        ['Ethereal', 'Ethereal Gem'],
        ['Spectator', 'Spectator Gem'],
        ['Mega-Kills', 'Mega-Kills Announcer'],
        ['Announcer', 'Announcer'],
        ['Egg', 'Egg'],
        ['Autograph:', 'Autograph'],
        ['Recipe:', 'Recipe']
        ]

    for nm in name_matches:
        if re.search(nm[0], name):
            return nm[1]

    return 'None'

# Gets an item's slot from its schema entry
def get_item_slot(item):
    if (not item['item_class'] == 'dota_item_wearable'):
        return 'None'
    else:
        search = re.search('(?<=DOTA_WearableType_)\w+', item['item_type_name'])
        if (search):
            return parse_slot(search.group(0))
        else:
            return 'None'

# Renames Valve's item slots to make more sense
def parse_slot(slot):
    slot_map = [
            ['International_HUD_Skin', 'HUD Skin'],
            ['pennant_upgrade', 'Pennant'],
            ['international_courier', 'Courier']
            ]

    #for the general case
    for sm in slot_map:
        if sm[0] == slot:
            return sm[1]

    return properfy(slot)

# Determines an item's quality from its name in cases where the item has no schema entry
def quality_from_name(name):
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
        if (re.match(quality, name)):
            return quality
       
    # return 'Normal' if no quality matches 
    return 'Normal'

# Determine the color of an item from its quality string
def colorize(quality):

    quality_map = [
    ['Frozen', '#4983B3'],
    ['Corrupted', '#A32C2E'],
    ['Cursed', '#8650AC'],
    ['Genuine', '#4D7455'],
    ['Unusual', '#8650AC'],
    ['Heroic', '#8650AC'],
    ['Elder', '#476291'],
    ['Self-Made', '#70B04A'],
    ['Inscribed', '#CF6632'],
    # colors unknown
    ['Autographed', '#FFFFFF']
    ]
    
    for qm in quality_map:
        if quality == qm[0]:
            return qm[1]

    #if there are no matches
    return "#FFFFFF"

# Translates hero names from their internal names to their actual names
def hero_name(name):
    #for special cases
    name_map = [
    ['blood_seeker', 'Bloodseeker'],
    ['furion', 'Nature\'s Prophet'],
    ['drow', 'Drow Ranger'],
    ['antimage', 'Anti-Mage'],
    ['lanaya', 'Templar Assassin'],
    ['tuskarr', 'Tusk'],
    ['centaur', 'Centaur Warrunner'],
    ['rikimaru', 'Riki'],
    ['shadowshaman', 'Shadow Shaman'],
    ['skeleton_king', 'Wraith King'],
    ['nerubian_assassin', 'Nyx Assassin'],
    ['obsidian_destroyer', 'Outworld Devourer'],
    ['windrunner', 'Windranger'],
    ['siren', 'Naga Siren'],
    ['queenofpain', 'Queen of Pain'],
    ['necrolyte', 'Necrophos'],
    ['witchdoctor', 'Witch Doctor']
    ]

    #for the general case
    for nm in name_map:
        if nm[0] == name:
            return nm[1]

    return properfy(name)

# Takes a snake case string and turns it into a proper noun with spaces
def properfy(string):
    
    noncapital = ['of', 'the', 'a']
    #capitalize the words and switch underscores to spaces
    n = ''
    #for each word
    for s in string.replace('_',' ').split(' '):
        if s not in noncapital:
            s = s.capitalize()
        n = n + ' ' + s

    #strip left space
    n = n.strip(' ')

    return n

# Returns the name of the base item (removes quality from the name)
def basify(name):
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
        if (re.match(quality, name)):
            return (' ').join(name.split(' ')[1:])

    return name

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

    # Get 100 items from Dota 2 Community Market
    resp, content = httplib2.Http().request(
        "http://steamcommunity.com/market/search/render/?query=appid%3A570&start=" 
        + str(update_items.cur_item) + "&count=" + str(item_count))

    # DEBUG for working from file
    #content = open('workfile.html', 'r').read()

    request = json.loads(content)

    content = request['results_html']
    soup = BeautifulSoup(content)

    # Create an SQL session to add items to the database
    session = SessionInstance()

    # Parse page's HTML for items
    for i in soup.findAll('a'):
        name = i.div.contents[5].span.contents[0].strip('\n\r ')
        name_slug = slugify(basify(name))
        quantity = int(i.div.div.span.span.contents[0].strip('\n\r ').replace(',',''))
        price = float(i.div.div.span.contents[6].replace('&#36;','').replace('USD','').strip('\n\r '))
        market_link = i['href']
        image_url_tiny = i.img['src']
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
                    image_url_large=i.img['src'],
                    image_url_small=i.img['src'], 
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
