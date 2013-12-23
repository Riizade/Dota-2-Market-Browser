import sqlalchemy
from BeautifulSoup import BeautifulSoup
import httplib2
import json

page_start = 0
page_count = 100

#get 100 items from Dota 2 Community Market
resp, content = httplib2.Http().request(
    "http://steamcommunity.com/market/search/render/?query=appid%3A570&start=" 
    + str(page_start) + "&count=" + str(page_count))

#DEBUG for working from file
#content = open('workfile.html', 'r').read()

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

for i in soup.findAll('a'):
    quantity = i.div.div.span.span.contents[0].strip('\n\r ')
    price = i.div.div.span.contents[6].strip('\n\r ')
    name = i.div.contents[5].span.contents[0].strip('\n\r ')

    #update item in database
    #DEBUG this just prints stuff, needs to be replaced with database logic
    print(name)
    print('----------------------')
    print(int(quantity))
    print('----------------------')
    print(float(price))
    print('----------------------')
    print('----------------------')

if (page_start + page_count >= int(request['total_count'])):
    page_start = 0
else:
    page_start += 100
