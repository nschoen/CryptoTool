import datetime
import decimal
from uuid import uuid4

class Wallet:

  def __init__(self):
    self.entries = []

  def deposit(self, buy_date, buy_price, amount):
    self.entries.append({
      # 'id': uuid4(),
      'buy_date': buy_date,
      'buy_price': buy_price,
      'amount': amount
    })

  def multi_deposit(self, entries):
    for e in entries:
      self.deposit(e['buy_date'], e['buy_price'], e['amount'])

  '''
  '''
  def withdrawal(self, amount):
    amount_left = amount
    wd_entries = [] # withdrawaled entries

    while amount_left > 0:
      print("amount left: ", amount_left)
      e = self.oldest_entry()
      if amount_left >= e['amount']:
        wd_entries.append(e)
        # remove item
        self.entries[:] = [x for x in self.entries if x != e]
        if len(self.entries) == 0:
          # workaround for oldest_entry(self):
          self.dummy_entry = e.copy()

        amount_left -= e['amount']
      else:
        ec = e.copy()
        ec['amount'] = amount_left
        wd_entries.append(ec)
        e['amount'] -= amount_left
        amount_left = decimal.Decimal(0)

    return wd_entries

  def oldest_entry(self):
    print("Get oldest entry")

    if len(self.entries) == 0:
      print("Dummy entry used ...")
      # workaround as the numbers are not that accurate ...
      # it can happen that the wallet is already empty, to solve this, save the latest removed item
      # and it that ...
      dummy = self.dummy_entry.copy()
      dummy['amount'] = decimal.Decimal('100000000000')
      return dummy


    oldest = self.entries[0]
    for e in self.entries:
      print("e", e)
      if e['buy_date'] < oldest['buy_date']:
        oldest = e
    return oldest

  def get_balance(self):
    balance = decimal.Decimal(0)
    for e in self.entries:
      balance += e['amount']
    return balance
