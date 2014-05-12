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
import unicodedata

#------------------------------------------------------------------------------
# Server Setup
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
if settings.get('delete_old_db', False):
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

#------------------------------------------------------------------------------
# Database Definitions
#------------------------------------------------------------------------------

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
    rarity = Column(String)
    rarity_color = Column(String)
    description = Column(String)
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
    rarity = Column(String)
    rarity_color = Column(String)
    description = Column(String)
    hero = Column(String)

class WikiInfo(Base):
    __tablename__ = 'wiki_info'
    name = Column(String, primary_key=True) # Name of item
    slot = Column(String)
    rarity = Column(String)
    rarity_color = Column(String)
    description = Column(String)

class Hero(Base):
    __tablename__ = 'heroes'
    name = Column(String, primary_key=True)

class Slot(Base):
    __tablename__ = 'slots'
    name = Column(String, primary_key=True)

class Type(Base):
    __tablename__ = 'types'
    name = Column(String, primary_key=True)

class Set(Base):
    __tablename__ = 'sets'
    name = Column(String, primary_key=True)

class Quality(Base):
    __tablename__ = 'qualities'
    name = Column(String, primary_key=True)

class Rarity(Base):
    __tablename__ = 'rarities'
    name = Column(String, primary_key=True)


#------------------------------------------------------------------------------
# Data Retrieval Functions
#------------------------------------------------------------------------------

# Downloads the Dota 2 item schema and inserts base items into the database
def get_schema():
    logging.info('Downloading schema')

    while True:
        try:
            # Get item schema from Dota 2 API
            resp, content = httplib2.Http().request('http://api.steampowered.com/IEconItems_570/GetSchema/v0001/?key=' + api_key)
            items = json.loads(content)
            break
        except ValueError:
            logging.error('Failed to load item schema from API, retrying...')

    logging.info('Saving schema to file')
    f = open('schema.json', 'w')
    f.write(content)
    f.close()
    logging.info('Updating base items')
    session = SessionInstance()

    for i in items['result']['items']:
        if (i['defindex'] < 900):
            continue

        try:
            item_set = parse_set(i['item_set'])
        except KeyError:
            item_set = 'None'

        wiki_info = info_from_wiki(i['name'])

        upsert(Item(
                name_slug=slugify(i['name']), 
                item_type=parse_type(get_item_type(i)), 
                item_slot=wiki_info['slot'], 
                item_set=item_set,
                image_url_large=i['image_url_large'],
                image_url_small=i['image_url'], 
                hero=get_hero(i['image_url']),
                name=i['name'],
                rarity=wiki_info['rarity'],
                rarity_color=wiki_info['rarity_color'],
                description=wiki_info['description'],
                defindex=i['defindex']))

    session.commit()
    session.close()
    
    logging.info('All base items have been updated')

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
def upsert(datum):

    session = SessionInstance()

    if type(datum) is MarketItem:
        # If the item exists already
        try:
            tmp_item = session.query(MarketItem).filter(MarketItem.name==datum.name)[0]
            # Update item in database
            logging.debug('Updating market item: '+datum.name)
            tmp_item.name = datum.name
            tmp_item.quantity = datum.quantity
            tmp_item.price = datum.price
            tmp_item.name_slug = datum.name_slug
            tmp_item.market_link = datum.market_link
            tmp_item.quality = datum.quality
            tmp_item.quality_color = datum.quality_color
            tmp_item.item_set = datum.item_set
            tmp_item.image_url_large = datum.image_url_large
            tmp_item.image_url_small = datum.image_url_small
            tmp_item.image_url_tiny = datum.image_url_tiny
            tmp_item.item_type = datum.item_type
            tmp_item.item_slot = datum.item_slot
            tmp_item.rarity = datum.rarity
            tmp_item.rarity_color = datum.rarity_color
            tmp_item.description = datum.description
            tmp_item.hero = datum.hero

        # If the item does not exist already
        except IndexError:
            logging.debug('Adding new market item: '+datum.name)
            session.add(datum)

    elif type(datum) is Item:
        try:
            tmp_item = session.query(Item).filter(Item.defindex==datum.defindex)[0]
            logging.debug('Updating base item: '+datum.name)
            tmp_item.name = datum.name
            tmp_item.name_slug = datum.name_slug
            tmp_item.item_set = datum.item_set
            tmp_item.image_url_large = datum.image_url_large
            tmp_item.image_url_small = datum.image_url_small
            tmp_item.item_type = datum.item_type
            tmp_item.item_slot = datum.item_slot
            tmp_item.rarity = datum.rarity
            tmp_item.rarity_color = datum.rarity_color
            tmp_item.description = datum.description
            tmp_item.hero = datum.hero
            tmp_item.defindex = datum.defindex

        except IndexError:
            logging.debug('Adding new base item: '+datum.name)
            session.add(datum)

    elif type(datum) is Hero:
        try:
            tmp_hero = session.query(Hero).filter(Hero.name==datum.name)[0]
        except IndexError:
            logging.debug('Adding new hero: '+datum.name)
            session.add(datum)

    elif type(datum) is Slot:
        try:
            tmp_slot = session.query(Slot).filter(Slot.name==datum.name)[0]
        except IndexError:
            logging.debug('Adding new slot: '+datum.name)
            session.add(datum)

    elif type(datum) is Set:
        try:
            tmp_set = session.query(Set).filter(Set.name==datum.name)[0]
        except IndexError:
            logging.debug('Adding new set: '+datum.name)
            session.add(datum)

    elif type(datum) is Type:
        try:
            tmp_type = session.query(Type).filter(Type.name==datum.name)[0]
        except IndexError:
            logging.debug('Adding new type: '+datum.name)
            session.add(datum)

    elif type(datum) is Quality:
        try:
            tmp_datum = session.query(Quality).filter(Quality.name==datum.name)[0]
        except IndexError:
            logging.debug('Adding new quality: '+datum.name)
            session.add(datum)

    elif type(datum) is Rarity:
        try:
            tmp_datum = session.query(Rarity).filter(Rarity.name==datum.name)[0]
        except IndexError:
            logging.debug('Adding new rarity: '+datum.name)
            session.add(datum)

    else:
        logging.error('Attempted to add data of type '+str(type(datum))+' that has no table')

    session.commit()
    session.close()

# Creates and initializes an empty database
def init_db():
    logging.info('Initialiazing database')
    Item.metadata.create_all(bind=engine)
    MarketItem.metadata.create_all(bind=engine)

def refresh_db():
    # Mine schema and all pages to populate database
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

    logging.info('Updating items from '+str(update_items.cur_item)+' to '+str(update_items.cur_item+item_count-1)+' of '+str(request['total_count']))

    content = request['results_html']

    # Create an SQL session to add items to the database
    session = SessionInstance()

    for i in re.findall(r'market_listing_row_link.+?</a>', content, re.DOTALL):
        if i is None:
            logging.error("No items found on market page")
        try:
            name = re.search('item_name.+?>(.+?)(</span>)', i).group(1)
            name_slug = slugify(basify(name))
            price = float(re.search('(?<=\&#36;)(.+?)(</span>)', i).group(1))
            quantity = int(re.search('(?<=qty">)(.+?)(</span>)', i).group(1).replace(',',''))
            market_link = re.search('href="(.+?)(")', i).group(1)
            image_url_tiny = re.search('<img.+?src="(.+?)(")', i).group(1)
            quality = quality_from_name(name)
            quality_color = colorize(quality)
        except AttributeError:
            logging.error('Could not find item fields in '+str(i))
        # Get base item
        try:
            base_item = session.query(Item).filter(Item.name==basify(name))[0]
        except IndexError:
            logging.warning(name+' has no base item')

            wiki_info = info_from_wiki(basify(name))
            base_item = Item(
                    name_slug=slugify(name), 
                    item_set='None',
                    image_url_large=image_url_tiny,
                    image_url_small=image_url_tiny, 
                    item_type=type_from_name(name),
                    item_slot=slot_from_name(name),
                    rarity=wiki_info['rarity'],
                    rarity_color=wiki_info['rarity_color'],
                    description=wiki_info['description'],
                    hero='None',
                    name=name)

        # Fill in missing fields using the base item
        item_set = base_item.item_set
        image_url_large = base_item.image_url_large
        image_url_small = base_item.image_url_small
        item_type = base_item.item_type
        item_slot = base_item.item_slot
        rarity = base_item.rarity
        rarity_color = base_item.rarity_color
        description = base_item.description
        hero = base_item.hero

        # Check for courier being in the hero slot
        if (hero == "Courier"):
            item_type = "Courier"
            item_slot = "Courier"
            hero = "None"

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
                item_type=item_type,
                item_slot=item_slot,
                rarity=rarity,
                rarity_color=rarity_color,
                description=description,
                hero=hero))

        # Upsert values for item fields
        upsert(Hero(name=hero))
        upsert(Slot(name=item_slot))
        upsert(Set(name=item_set))
        upsert(Type(name=item_type))
        upsert(Quality(name=quality))
        upsert(Rarity(name=rarity))

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

# Periodically updates a market page every (sec) seconds
def market_timer(sec):
   update_items()
   threading.Timer(sec, market_timer).start()
# Periodically updates the schema every (sec) seconds
def schema_timer(sec):
    get_schema()
    threading.Timer(sec, schema_timer).start()

#------------------------------------------------------------------------------
# Item Parsing Functions
#------------------------------------------------------------------------------

# Parses an item's hero from the item's image_url
def get_hero(image_url):
    search = re.search('(?<=icons/econ/items/)\w+', image_url)
    if (search):
        name = search.group(0)
    else:
        name = 'None'

    return hero_name(name)

# Converts names to a standard slug structure
def slugify(s):
    slug = unicodedata.normalize('NFKD', s)
    slug = slug.encode('ascii', 'ignore').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'[-]+', '-', slug)

    return slug

def wikify(s):
    special = {'Reaver': 'Reaver_(Equipment)'}
    # General Case
    if (special.get(s, None) is None):
        s = s.encode('ascii', 'ignore').lower()
        s = properfy(s)
        s = s.replace(' ', '_')
    # Special case
    else:
        s = special.get(s, None)

    return s

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
            ['decoder_ring', 'Key'],
            ['gem_type', 'Gem'],
            ['mysterious_egg', 'Egg'],
            ['hero_ability', 'Action Item'],
            ['event_ticket', 'Ticket'],
            ['tournament_passport', 'Ticket']
            ]
    type_name = type_name.replace(' ','_')
    for tm in type_matches:
        if type_name.lower() == tm[0].lower():
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

# Gets an item's slot from its entry on dota2.gamepedia.com
def slot_from_wiki(item_name):
    session = SessionInstance()

    try:
        item_slot = session.query(WikiInfo).filter(WikiInfo.name==item_name)[0]
    except IndexError:
        logging.debug('Getting item slot for '+item_name+' from the wiki')
        item_slot = get_wiki_slot(item_name)

        if(item_slot is None):
            # Try without quotes
            item_name_tmp = item_name.replace('\'', '')
            item_slot = get_wiki_slot(item_name_tmp)
            if(item_slot is None):
                logging.error('Could not find item slot for item '+item_name+' on the wiki')
                item_slot = 'None'
            else:
                session.add(WikiInfo(name=item_name, slot=item_slot))
        else:
            session.add(WikiInfo(name=item_name, slot=item_slot))
        
    session.commit()
    session.close()

    return item_slot

# Checks if the information returned from a wiki parsing is good or not
def bad_wiki_info(data):
    if data['slot'] == 'N/A' and data['description'] == 'N/A':
        return True
    else:
        return False

# Attempts to find information on an item using the wiki
def info_from_wiki(item_name):
    data = {'slot': 'N/A',
            'rarity': 'N/A',
            'rarity_color': 'N/A',
            'description': 'N/A'}

    session = SessionInstance()

    try:
        item_info = session.query(WikiInfo).filter(WikiInfo.name==item_name)[0]
        data['slot'] = item_info.slot
        data['rarity'] = item_info.rarity
        data['rarity_color'] = item_info.rarity_color
        data['description'] = item_info.description

        logging.debug('Found cached wiki data for item '+item_name)
    except IndexError:
        logging.info('Getting information for item '+item_name+' from the wiki')

        # Try multiple names for wiki URLs
        fields = ['slot', 'rarity', 'rarity_color', 'description']
        names = []
        names.append(item_name)
        names.append('The '+item_name)
        name_no_apostrophe = item_name.replace('\'', '')
        # Only add this variant if the resultant string is different
        if name_no_apostrophe == item_name:
            names.append(name_no_apostrophe)
        for name in names:
            name_data = parse_wiki(name)
            # Look for fields
            for field in fields:
                if not (name_data[field] is None):
                    data[field] = name_data[field]
            # Check if the wiki info is bad
            if (not bad_wiki_info(data)):
                # Break when good data has been gotten
                break

        # If the wiki page was bad, return a warning
        if bad_wiki_info(data):
            logging.warning('Could not find wiki info for item '+item_name)

        # DEBUG find the dumb slot parse
        if ('href' in data['slot']):
            logging.warning('Item '+item_name+' has the strange slot')

        # Add info to cache database table
        session.add(WikiInfo(
                    name=item_name,
                    slot=data['slot'],
                    rarity=data['rarity'],
                    rarity_color=data['rarity_color'],
                    description=data['description']))

        session.commit()
        session.close()

    return data

# Parses a wiki page for information and returns that data as a dictionary
def parse_wiki(item_name):
    name = wikify(item_name)

    url = 'http://dota2.gamepedia.com/'+name
    resp, content = httplib2.Http().request(url)

    f = open('test.html', 'w')
    f.write(content)
    f.close()

    # Parse slot
    search = re.search('Equip Slot:<br />(.+)', content)
    if (search):
        item_slot = search.group(1)
    else:
        item_slot = None

    # Parse description
    search = re.search('style="font-style:italic;padding:6px 10px;">(.+)', content)
    if(search):
        item_description = search.group(1).decode('UTF-8')
    else:
        item_description = None

    # Parse rarity
    rarities = ['Common',
                'Uncommon',
                'Rare',
                'Mythical',
                'Legendary',
                'Ancient',
                'Immortal',
                'Arcana']
    item_rarity  = None
    for rarity in rarities:
        search = re.search('color=".+?">'+rarity+'</font></b>', content)
        if (search):
            item_rarity = rarity

    rarity_colors = {'Common': '#B0C3D9',
                    'Uncommon': '#5E98D9', 
                    'Rare': '#4B69FF',
                    'Mythical': '#8847FF', 
                    'Legendary': '#D32CE6',  
                    'Ancient': '#EB4B4B',
                    'Immortal': '#E4AE33',  
                    'Arcana': '#ADE55C'}

    rarity_color = rarity_colors.get(item_rarity, None)

    data = {'slot': item_slot,
            'rarity': item_rarity,
            'rarity_color': rarity_color,
            'description': item_description}

    return data

def get_wiki_slot(item_name):
    name = wikify(item_name)

    url = 'http://dota2.gamepedia.com/'+name
    resp, content = httplib2.Http().request(url)

    search = re.search('Equip Slot:<br />(.+)', content)
    if (search):
        item_slot = search.group(1)
    else:
        item_slot = None

    return item_slot


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
            ['international_courier', 'Courier'],
            ['abomination', 'Head'],
            ['amulet', 'Neck'],
            ['antennae', 'Head'],
            ['arm_guards', 'Arms'],
            ['arm_shields', 'Arms'],
            ['arm_wraps', 'Arms'],
            ['armbands', 'Arms'],
            ['armguards', 'Arms'],
            ['armlet', 'Arms'],
            ['armlets', 'Arms'],
            ['axe', 'Weapon'],
            ['axes', 'Weapon'],
            ['back_and_banner', 'Back'],
            ['back_and_shield', 'Back'],
            ['backpack', 'Back'],
            ['grandfather\'s_ribs', 'Back'],
            ['ballnchains', 'Belt'],
            ['bandage', 'Head'],
            ['bandana', 'Head'],
            ['bandanna', 'Head'],
            ['bangles', 'Arms'],
            ['banner', 'Back'],
            ['banner_pack', 'Back'],
            ['banners', 'Back'],
            ['basket', 'Back'],
            ['bat', 'Mount'],
            ['battleaxe', 'Weapon'],
            ['battlewings', 'Back'],
            ['beard', 'Neck'],
            ['belly_guard', 'Belt'],
            ['belt_and_wrap', 'Belt'],
            ['belt_doll_and_manacle', 'Belt'],
            ['honored_belt', 'Belt'],
            ['utility_belt', 'Belt'],
            ['beret', 'Head'],
            ['bicorne', 'Head'],
            ['bindings', 'Belt'],
            ['birch', 'Weapon'],
            ['blade', 'Weapon'],
            ['blade_weapon', 'Weapon'],
            ['bladed_tail', 'Tail'],
            ['blades', 'Weapon'],
            ['blink_dagger', 'Weapon'],
            ['blouse', 'Chest'],
            ['body_wrap', 'Armor'],
            ['bonds', 'Arms'],
            ['bone_club', 'Weapon'],
            ['bone_helm', 'Head'],
            ['booby_trap', 'Shuriken'],
            ['book', 'Misc'],
            ['boots', 'Feet'],
            ['bow', 'Weapon']
            ]

    slot = slot.strip('_')
    slot = slot.replace(' ','_')
    slot = slot.lower()
    # For the special cases in slot_map
    for sm in slot_map:
        if sm[0].lower() == slot:
            return sm[1]

    logging.debug('No match for slot '+slot+', returning '+properfy(slot))

    # For the general case
    return properfy(slot)

def parse_set(setname):
    hero_strings = set(['abaddon','alchemist','ancient_apparition','antimage','axe','bane','batrider','beastmaster','bloodseeker','bounty_hunter','brewmaster','bristleback','broodmother','centaur','chaos_knight','chen','clinkz','crystal_maiden','dark_seer','dazzle','death_prophet','disruptor','doom_bringer','dragon_knight','drow_ranger','earth_spirit','earthshaker','elder_titan','ember_spirit','enchantress','enigma','faceless_void','furion','gyrocopter','huskar','invoker','jakiro','juggernaut','keeper_of_the_light','kunkka','legion_commander','leshrac','lich','life_stealer','lina','lion','lone_druid','luna','lycan','magnataur','medusa','meepo','mirana','morphling','naga_siren','nevermore','night_stalker','nyx_assassin','obsidian_destroyer','ogre_magi','omniknight','phantom_assassin','phantom_lancer','puck','pudge','pugna','queenofpain','rattletrap','razor','riki','rubick','sand_king','shadow_demon','shadow_shaman','shredder','silencer','skeleton_king','skywrath_mage','slardar','slark','sniper','spectre','spirit_breaker','storm_spirit','sven','templar_assassin','tidehunter','tinker','tiny','treant','troll_warlord','tusk','undying','ursa','vengefulspirit','venomancer','viper','visage','warlock','weaver','wisp','witch_doctor','zuus'])
    set_split = setname.split('_')

    # Remove hero names
    if (len(set_split) > 2):
        # Checks for one word hero names
        if set_split[0] in hero_strings:
            set_split = set_split[1:]
        # Checks for two word hero names
        if set_split[0]+'_'+set_split[1] in hero_strings:
            set_split = set_split[2:]

    return properfy('_'.join(set_split))

# Determines an item's quality from its name
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
                'Autographed',
                'Favored',
                'Ascendant',
                'Auspicious',
                'Exalted']

    session = SessionInstance()

    # Check to see if the item's whole name is a base item
    try:
        tmp_item = session.query(Item).filter(Item.name==name)[0]
        return 'Normal'
    # If not, then extract the quality from the item's name
    except IndexError:
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
    ['Autographed', '#ADE55C'],
    ['Favored', '#FFFF00'],
    ['Ascendant', '#EB4B4B'],
    ['Auspicious', '#32CD32'],
    ['Exalted', '#CCCCCD']
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

    # For the special cases in name_map
    for nm in name_map:
        if nm[0] == name:
            return nm[1]

    # For the general case
    return properfy(name)

# Takes a snake case string and turns it into a proper noun with spaces
def properfy(string):
    noncapital = ['of', 'the', 'a', 'from']
    # Capitalize the words and switch underscores to spaces
    n = ''
    # For each word
    for s in string.replace('_',' ').split(' '):
        if s not in noncapital:
            s = s.capitalize()
        n = n + ' ' + s

    # Strip left space
    n = n.strip(' ')

    # Capitalize words after hyphens
    for m in re.findall('(?<=-)[a-z]', n):
        n = n.replace('-'+m, '-'+m.capitalize())

    return n

# Returns the name of the base item (removes quality from the name)
def basify(name):
    quality = quality_from_name(name)
    name = name.replace(quality, '')
    name = name.strip()

    return name
