# The entry point for the server

from server import app
import json
settings = json.load(open('config.json'))

app.run(debug=settings['debug'], host=settings['host'])
