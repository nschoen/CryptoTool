import requests
import json
import csv
import decimal
import sys
from datetime import timezone

prices = {}

def request_price(dt, from_symbol, to_symbol):
  timestamp = int(dt.replace(tzinfo=timezone.utc).timestamp())

  if from_symbol == 'MIOTA':
    from_symbol = 'IOT'

  if from_symbol == 'IOT' and to_symbol == 'EUR':
    iota_usd = request_price(dt, 'IOT', 'USD')
    usd_eur = request_price(dt, 'USD', 'EUR')
    iota_eur = iota_usd * usd_eur
    print("Price", iota_eur)
    write_local_price(timestamp, from_symbol, to_symbol, iota_eur)
    write_csv()
    return iota_eur

  if from_symbol == 'NEO' and to_symbol == 'EUR':
    neo_usd = request_price(dt, 'NEO', 'USD')
    usd_eur = request_price(dt, 'USD', 'EUR')
    neo_eur = neo_usd * usd_eur
    print("Price", neo_eur)
    write_local_price(timestamp, from_symbol, to_symbol, neo_eur)
    write_csv()
    return neo_eur

  if from_symbol == 'BCN' and to_symbol == 'EUR':
    bcn_usd = request_price(dt, 'BCN', 'USD')
    usd_eur = request_price(dt, 'USD', 'EUR')
    bcn_eur = bcn_usd * usd_eur
    print("Price", bcn_eur)
    write_local_price(timestamp, from_symbol, to_symbol, bcn_eur)
    write_csv()
    return bcn_eur

  if from_symbol == 'USDT' and to_symbol == 'EUR':
    usdt_usd = request_price(dt, 'USDT', 'USD')
    usd_eur = request_price(dt, 'USD', 'EUR')
    usdt_eur = usdt_usd * usd_eur
    print("Price", usdt_eur)
    write_local_price(timestamp, from_symbol, to_symbol, usdt_eur)
    write_csv()
    return usdt_eur

  local_price = read_local_price(timestamp, from_symbol, to_symbol)
  if local_price:
    return local_price['price']

  print("Request new price from api", timestamp, from_symbol, to_symbol)
  r = requests.get(f"https://min-api.cryptocompare.com/data/histohour?fsym={from_symbol}&tsym={to_symbol}&limit=1&toTs={timestamp}&api_key=b8de9413e329720a2f2a66ff04a86c2ac1db96efae3599742e8086ed217b75ba")

  pdata = r.json()

  if 'Response' in pdata and pdata['Response'] == 'Error':
    print("--- Error ---")
    print(f"Path for {dt} From Symbol {from_symbol} and To Symbol {to_symbol} does not exists!")
    sys.exit()

  price = decimal.Decimal((pdata['Data'][0]['open'] + pdata['Data'][0]['close']) / 2)
  price = decimal.Decimal(round(price, 2))
  print("Price", price)
  write_local_price(timestamp, from_symbol, to_symbol, price)
  write_csv()

  return price

def read_local_price(timestamp, from_symbol, to_symbol):
  key = f"{from_symbol}-{to_symbol}-{timestamp}"
  if key in prices:
    return prices[key]

def write_local_price(timestamp, from_symbol, to_symbol, price):
  key = f"{from_symbol}-{to_symbol}-{timestamp}"
  prices[key] = {
    "timestamp": timestamp,
    "from_symbol": from_symbol,
    "to_symbol": to_symbol,
    "price": price,
  }
  return prices[key]

def read_csv():
  with open('prices.csv', mode='r') as csv_file:
    prices_reader = csv.DictReader(csv_file)
    for price in prices_reader:
      write_local_price(int(price['timestamp']), price['from_symbol'], price['to_symbol'], decimal.Decimal(price['price']))

"""
Overrides the transactions.csv with the provided transactions
"""
def write_csv():
  with open('prices.csv', mode='w') as csv_file:
    fieldnames = [
      'timestamp',
      'from_symbol',
      'to_symbol',
      'price'
    ]

    writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    #for price in prices:
    for key, price in prices.items():
      writer.writerow(price)

read_csv()
