# The entry point for the server

from server import app
import json
settings = json.load(open('config.json'))

app.run(debug=settings.get('debug', default=False), host=settings.get('host', default='0.0.0.0'))
