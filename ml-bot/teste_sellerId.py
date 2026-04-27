import requests
from bs4 import BeautifulSoup

url = "https://lista.mercadolivre.com.br/valvula-sandero"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

resp = requests.get(url, headers=headers)
print(resp.status_code)
print(resp.text[:2000])  # primeiras linhas do HTML