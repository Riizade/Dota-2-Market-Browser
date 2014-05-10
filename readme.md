# Dota 2 Market Browser
## Dependencies
* Python
* sqlalchemy
* Wand
* BeautifulSoup
* Flask
* MagickWand

## Installing Dependencies
    apt-get install python-pip
    pip install sqlalchemy
    pip install Wand
    pip install beautifulsoup
    pip install flask
    apt-get install libmagickwand-dev
    
    run.sh additionally requires xterm (though could be easily modified to work with other terminals)

# Configuration
The main config file is config.json

Here are the accepted fields for config.json

    update_items: whether or not to continuously update the market listings of items
    api_key: your API key for use with Valve's market API
    log_level: the amount of information to log (0-4), higher numbers give more information in logs
    sql_log_level: the amount of information to log for SQLAlchemy (0-4)
    delete_old_db: deletes the current item database
    populate_db: does a full parse of the schema and all market items on startup
