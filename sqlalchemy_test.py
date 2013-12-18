import sqlalchemy
from BeautifulSoup import BeautifulSoup
import httplib2

#get 100 items from Dota 2 Community Market
resp, content = httplib2.Http().request(
    "http://steamcommunity.com/market/search/render/?query=appid%3A570&start=00&count=100")

soup = BeautifulSoup(content)
workfile = open('workfile.html', 'w')

#replace individual characters to clean up the HTML
temp_str = soup.prettify()
#remove \r, \n, \t, &gt, &lt, ;, \/span, \/div, \/a, }
#replace &#36 with $
temp_str = temp_str.replace('\\r', '').replace('\\n', '').replace('\\t', '')
temp_str = temp_str.replace('&gt', '').replace('&lt', '').replace(';', '')
temp_str = temp_str.replace('\\/span', '').replace('\\/div', '').replace('\\/a', '')
temp_str = temp_str.replace('&#36', '$').replace('}', '')

#remove JSON artifact from first line
temp_str = '\n'.join(temp_str.split('\n')[1:]) 

soup = BeautifulSoup(temp_str)
workfile.write(soup.prettify())
workfile.close()

for i in soup.findAll('a'):
    print(i.div.div.span.span.prettify())


