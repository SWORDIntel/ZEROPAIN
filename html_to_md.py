
import html2text
import sys

with open(sys.argv[1], 'r') as f:
    html = f.read()

h = html2text.HTML2Text()
h.ignore_links = False
markdown = h.handle(html)
print(markdown)
