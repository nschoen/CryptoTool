from wallet import Wallet

class Exchange:
  def __init__(self, name):
    self.name = name
    self.wallets = {}

  def deposit(self, asset, buy_date, buy_price, amount):
    print("-- Deposit (", self.name, "):", buy_date, buy_price, amount, asset)
    if asset not in self.wallets:
      self.wallets[asset] = Wallet()
    wallet = self.wallets[asset]
    wallet.deposit(buy_date, buy_price, amount)
    print("-- End Deposit Balance:", wallet.get_balance(), "\n")

  def multi_deposit(self, asset, entries):
    print("-- Multi Deposit (", self.name, "):", asset, entries)
    if asset not in self.wallets:
      self.wallets[asset] = Wallet()
    wallet = self.wallets[asset]
    wallet.multi_deposit(entries)
    print("-- End Deposit Balance:", wallet.get_balance(), "\n")

  def withdrawal(self, asset, amount):
    print("-- Withdrawal (", self.name, "):", amount, asset)
    if asset not in self.wallets:
      self.wallets[asset] = Wallet()
    wallet = self.wallets[asset]
    wd_entries = wallet.withdrawal(amount)
    print("-- End Withdrawal Balance:", wallet.get_balance(), "\n")
    return wd_entries

  def copy_wallet(self, asset):
    c_entries = []
    # left_amount = amount
    # the amount should normally match ... but anyways, check that is is the same!
    for e in self.wallets[asset].entries:
      # if left_amount = 0:
      #   break

      ce = e.copy()
      # if ce <= left_amount:
      #   left_amount -= ce['amount']
      # else:
      #   ce['amount'] = left_amount
      #   left_amount = 0

      c_entries.append(ce)
    # end entries

    return c_entries
