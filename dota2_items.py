import json
items = json.load(open('dota2_schema.json'))
print(items['result'])
