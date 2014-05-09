import re
import httplib2
import unicodedata
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
            ['hero_ability', 'Active Item'],
            ['event_ticket', 'Ticket'],
            ['tournament_passport', 'Ticket']
            ]
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
            ['amulet', 'Neck']
            ]

    #for the general case
    for sm in slot_map:
        if sm[0].lower() == slot.lower():
            return sm[1]

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
                'Autographed',
                'Favored',
                'Ascendant',
                'Auspicious']
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
    ['Auspicious', '#32CD32']
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
    quality = quality_from_name(name)
    name = name.replace(quality, '')
    name = name.strip()

    return name
