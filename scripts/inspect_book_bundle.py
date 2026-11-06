import re
import urllib.request

req = urllib.request.Request('https://alrahma.ama8.uk/reception/book', headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8')
        scripts = re.findall(r'src="([^"]+\.js)"', html)
        print('Found scripts in /reception/book:', len(scripts))
        for s in scripts:
            print(' ', s)
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code)
