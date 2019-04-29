import csv
import sys
import decimal
from uuid import uuid4
from datetime import datetime
from datetime import timedelta
from exchange import Exchange
from price_api import request_price

# {
#   exchange,
#   origin_asset,
#   fork_datetime,
#   target_asset,
#   fork_amount
# }
hardfork_wallet_snappshot_requests = []

# {
#   exchange,
#   origin_asset,
#   fork_datetime,
#   target_asset,
#   fork_amount,
#   wallet
# }
hardfork_wallet_snappshots = []

exchanges = {}

"""
Manages the import process
"""
def import_txs():
  txs = read_csv()

  # sort by date
  txs = sorted(txs, key=lambda tx: tx['trade_date'])

  # set ids
  set_tx_ids(txs)

  # integrity check for withdrawl/deposit
  check_transfers(txs)

  # prepare hardfork snapshot requests
  # tx['widthdrawal_ref_id'] = f"{origin_asset}-{fork_datetime}"
  for tx in txs:
    if tx['clarification'] == 'Hardfork':
      [origin_asset, fork_datetime] = tx['widthdrawal_ref_id'].split('-')
      hardfork_wallet_snappshot_requests.append({
        'exchange_account': tx['exchange_account'],
        'origin_asset': origin_asset,
        'fork_datetime': datetime.strptime(fork_datetime, '%d.%m.%Y %H:%M:%S'),
        'target_asset': tx['buy_asset'],
        'fork_amount': tx['buy_amount']
      })
    # end if Hardfork
  # end loop txs

  # process transactions
  process_transactions(txs)

"""
Assigns to all new transactions an ID if they do not already have one
"""
def set_tx_ids(txs):
  nid = 1
  for tx in txs:
    if 'id' in tx and len(tx['id']) > 0 and int(tx['id']) >= nid:
      nid = int(tx['id']) + 1

  print('Lastest ID:', nid)

  changed = False
  for tx in txs:
    if not 'id' in tx or not tx['id']:
      # print "not id?"
      # tx['id'] = uuid.uuidv4()[:6]
      tx['id'] = nid
      nid += 1
      changed = True

  if changed:
    print('Import changed')
    write_csv(txs)

"""
Checks and tracks withdrawals with deposits.
Asks the user for more information if required.
"""
def check_transfers(txs):
  withdrawals_txs = []
  changed = False
  stop = False

  for tx in txs:
    if stop: break

    if tx['transaction_type'] == 'withdrawal':
      # just append for now
      # withdrawals which will not be connected to deposits can be edited at the end
      if tx['clarification'] == 'Staking':
        continue
      if tx['clarification'] == 'Expense':
        continue
      if tx['clarification'] == 'Transfer':
        continue
      if tx['clarification'] == 'Bank':
        continue
      if tx['clarification'] == 'InterpretAsSold':
        continue
      if tx['clarification'] == 'Fees': # e.g. through margin trading on Bitfinex
        continue
      if tx['clarification'] == 'Loss': # e.g. through margin trading on Bitfinex
        continue
      if tx['clarification'] == 'ICO' and 'widthdrawal_ref_id' in tx and len(tx['widthdrawal_ref_id']) > 0:
        continue

      withdrawals_txs.append(tx)

    if tx['transaction_type'] == 'deposit':

      # TODO: use clarification for the type and ref id only two connect to transactions

      if tx['clarification'] == 'Bank':
        continue
      if tx['clarification'] == 'Staking':
        continue
      if tx['clarification'] == 'ICO' and 'widthdrawal_ref_id' in tx and len(tx['widthdrawal_ref_id']) > 0:
        continue
      if tx['clarification'] == 'InterpretAsBought':
        continue
      if tx['clarification'] == 'Profit': # e.g. from margin trading on Bitfinex
        continue

      if not tx['widthdrawal_ref_id']:
        # itereate withdrawal list to find matching items
        no_widthrawal_found = True
        for wd in withdrawals_txs:
          timedelta = tx['trade_date'] - wd['trade_date']
          print("wd", wd['id'])
          if wd['sell_amount'] == tx['buy_amount'] and timedelta.total_seconds() < 3600 * 24 * 7: # 7 tage
            # found potentialy matching withdrawal
            # print("wd", wd['sell_amount'])
            feedback = input(f"""
              Should be
              deposit     {tx['buy_amount']} {tx['buy_asset']} to '{tx['exchange_account']}' (ID: {tx['id']}) be automatically connected to
              widthdrawal {wd['sell_amount']} {wd['sell_asset']} to '{wd['exchange_account']} (ID: {wd['id']})'?
              y/n or something else to stop here:
            """)
            if feedback == 'y':
              ref_id = uuid4()
              # TODO: just use the id?
              wd['widthdrawal_ref_id'] = ref_id
              wd['clarification'] = 'Transfer'
              tx['widthdrawal_ref_id'] = ref_id
              tx['clarification'] = 'Transfer'
              withdrawals_txs[:] = [x for x in withdrawals_txs if x['id'] != wd['id']]
              # TODO: helper für das löschen bauen
              changed = True
              no_widthrawal_found = False
            elif feedback == 'n':
              print('Well then I stop here, please resolve the issue manually')
              stop = True
            else:
              stop = True

        # if no withdrawal has been found, provide more options
        if no_widthrawal_found:
          selection = input(f"""
            Deposit of (ID: {tx['id']}) {tx['buy_amount']} {tx['buy_asset']} to exchange '{tx['exchange_account']}'': Could not find a withdrawal counterpart
            Press 1 for fiat deposit from a bank
            Press 2 for Staking Income
            Press 3 for ICO and to select the according withdrawal
            Press 4 for Hardfork
            Press 5 to mark it as a buy at the price given at the deposit
            Press 6 to mark it as Profit (e.g. from margin trading)
            Press 7 to stop here
            Your Answer:
          """)
          if selection == '1':
            # set as bank deposited via bank
            tx['clarification'] = 'Bank'
            changed = True
          if selection == '2':
            # set as staking
            tx['clarification'] = 'Staking'
            changed = True
          if selection == '3':
            # ICO
            withdrawals_string = "Choose one of the following withdrawal options"
            index = 1

            selection = input("Do you want to specify a price or a related withdrawal\nPress 1 for price\nPress 2 for withdrawal")

            if selection == '1':
              price = decimal.Decimal(input("Please specify a price"))
              tx['clarification'] = 'ICO'
              tx['widthdrawal_ref_id'] = f"price:{price}"
              changed = True
              continue

            for wd in withdrawals_txs:
              withdrawals_string += f"\nPress {index} to select WD-ID-{wd['id']} {wd['sell_amount']} {wd['sell_asset']} from platform {wd['exchange_account']}"
              index += 1
            selection = int(input(withdrawals_string))
            while selection <= 0 or selection >= index:
              print('What are you doing?')
              selection = int(input(withdrawals_string))

            selected_wd = withdrawals_txs[selection - 1]
            new_ref_id = uuid4()
            tx['clarification'] = 'ICO'
            selected_wd['clarification'] = 'ICO'
            tx['widthdrawal_ref_id'] = new_ref_id
            selected_wd['widthdrawal_ref_id'] = new_ref_id
            withdrawals_txs[:] = [x for x in withdrawals_txs if x['id'] != selected_wd['id']]
            changed = True
          if selection == '4':
            # hard fork
            tx['clarification'] = 'Hardfork'
            origin_asset = input("Please name the origin asset")
            fork_datetime = input("Please provide the exact date and time of the hard fork (Format: DD.MM.YYYY hh:mm:ss")
            fork_dt = datetime.strptime(fork_datetime, '%d.%m.%Y %H:%M:%S')
            tx['widthdrawal_ref_id'] = f"{origin_asset}-{fork_datetime}"

            changed = True
          if selection == '5':
            tx['clarification'] = 'InterpretAsBought'
            changed = True
          if selection == '6':
            tx['clarification'] = 'Profit'
            changed = True
          if selection == '7':
            stop = True

  # check left withdrawals which have not been connected to deposits
  for wd in withdrawals_txs:
    if stop == True: break

    print("At least one WD has not been assigned yet")

    selection = input(f"""
      Widthdrawal has not been clarified yet
      ID: {wd['id']}
      Amount: {wd['sell_amount']} {wd['sell_asset']}
      Exchange: {wd['exchange_account']}
      Press 1 to mark it as a voting/staking expense
      Press 2 to mark it as a withdrawal to a bank
      Press 3 to mark it as a general expense which is not relevant for tax
      Press 4 to mark this as fees (e.g. through margin trading)
      Press 5 to mark this as a loss (e.g. through margin trading)
      Press 6 to mark this withdrawal as a sell to the price at that time
      Press 7 to stop here
    """)

    if selection == '1':
      changed = True
      wd['clarification'] = 'Staking'
    if selection == '2':
      changed = True
      wd['clarification'] = 'Bank'
    if selection == '3':
      changed = True
      wd['clarification'] = 'Expense'
    if selection == '4':
      changed = True
      wd['clarification'] = 'Fees'
    if selection == '5':
      changed = True
      wd['clarification'] = 'Loss' # e.g. through margin trading on Bitfinex
    if selection == '6':
      changed = True
      wd['clarification'] = 'InterpretAsSold'
    if selection == '7':
      stop = True

    # Press 4 to mark it as a tax irrelevant expenditure
    # - voting expenses
    # - withdrawal via bank
    # - other expenses, nicht versteuerbar

  if changed:
    print('Import changed')
    write_csv(txs)


def check_fork_request(tx):
  for snapr in hardfork_wallet_snappshot_requests:
    if snapr['fork_datetime'] < tx['trade_date']:
      print("-------... Should snapshot")
      # just passed the fork time, snapshot the wallet of the fork exchange
      snapr['wallet'] = exchanges[snapr['exchange_account']].copy_wallet(snapr['origin_asset']) #, snapr['fork_amount'])
      # exchanges[snapr['exchange']].multi_deposit(snapr['target_asset'], wallet_copy)
      hardfork_wallet_snappshots.append(snapr)
      hardfork_wallet_snappshot_requests[:] = [x for x in hardfork_wallet_snappshot_requests if x != snapr]
      # hardfork_wallet_snappshot_requests[:] = [x for x in hardfork_wallet_snappshot_requests if x['exchange'] != snapr['exchange'] and x['fork_datetime'] != snapr['fork_datetime'] and x['target_asset'] != snapr['target_asset']]

"""
Processes the transactions. The integrity check of the withdrawals and deposits have to
be done before. Expects the transactions to be in a chronological order.
"""
def process_transactions(txs):
  # exchanges = {}
  withdrawals = {}

  for tx in txs:
    print('Processsing transaction ID', tx['id'])

    # if exchange does not exists, create it
    if not tx['exchange_account'] in exchanges:
      exchanges[tx['exchange_account']] = Exchange(tx['exchange_name'])
    exchange = exchanges[tx['exchange_account']]

    tx['fee_eur'] = decimal.Decimal(0)
    tx['trade_profit'] = decimal.Decimal(0)
    tx['total_profit'] = decimal.Decimal(0)
    tx['trade_profit_taxable'] = decimal.Decimal(0)
    tx['total_profit_taxable'] = decimal.Decimal(0)

    # if withdrawal === vom wallet abziehen und in withdrawals packen
    if tx['transaction_type'] == 'withdrawal':
      check_fork_request(tx)

      wd_entries = exchange.withdrawal(tx['sell_asset'], tx['sell_amount'])

      # wd_entries is an array of withdrawals amount with their according buy_date
      if not tx['clarification'] == 'Staking' and not tx['clarification'] == 'Bank' and not tx['clarification'] == 'Expense' and not tx['clarification'] == 'InterpretAsSold' and not tx['clarification'] == 'Fees' and not tx['clarification'] == 'Loss':
        withdrawals[tx['widthdrawal_ref_id']] = {
          'tx': tx,
          'wds': wd_entries
        }

      if tx['clarification'] == 'InterpretAsSold':
        # already withdrawn, but list the profits
        price = request_price(tx['trade_date'], tx['sell_asset'], 'EUR')
        profit = decimal.Decimal(0)
        taxable_profit = decimal.Decimal(0)
        for wd in wd_entries:
          # wd: { buy_date, buy_price, amount }
          delta = tx['trade_date'] - wd['buy_date']
          tax_free = False
          if delta.total_seconds() > 3600 * 24 * 365:
            tax_free = True
          profit += wd['amount'] * (price - wd['buy_price'])
          if not tax_free:
            taxable_profit += wd['amount'] * (price - wd['buy_price'])

        tx['trade_profit'] += profit
        tx['total_profit'] += profit
        tx['trade_profit_taxable'] += taxable_profit
        tx['total_profit_taxable'] += taxable_profit

      if tx['clarification'] == 'Fees':
        # already withdrawn, but list the costs

        # a bit hacky as some entries use the fee and some sell_amount columns ...
        # TODO: make sure that all rows use the sell_amount coumns?!
        total_costs = decimal.Decimal(0)
        if tx['fee'] > 0:
          fee_cost = tx['fee']
          if tx['fee_asset'] != 'EUR':
            price = request_price(tx['trade_date'], tx['fee_asset'], 'EUR')
            fee_cost = tx['sell_amount'] * price
          total_costs += fee_cost

        if tx['sell_amount'] > 0:
          sell_cost = tx['sell_amount']
          if tx['sell_asset'] != 'EUR':
            price = request_price(tx['trade_date'], tx['sell_asset'], 'EUR')
            sell_cost = tx['sell_amount'] * price
          total_costs += sell_cost

        tx['fee_eur'] += total_costs
        tx['total_profit'] -= total_costs
        tx['total_profit_taxable'] -= total_costs
        continue

      if tx['clarification'] == 'Loss':
        # already withdrawn, but list the costs
        total_loss = tx['sell_amount']
        if tx['sell_asset'] != 'EUR':
          price = request_price(tx['trade_date'], tx['sell_asset'], 'EUR')
          total_loss = tx['sell_amount'] * price
        tx['total_profit'] -= total_loss
        tx['total_profit_taxable'] -= total_loss
        continue

      if tx['fee'] > 0:
        exchange.withdrawal(tx['fee_asset'], tx['fee'])
        fee_eur = decimal.Decimal(0)
        if tx['fee_asset'] == 'EUR':
          fee_eur = tx['fee']
        else:
          price = request_price(tx['trade_date'], tx['fee_asset'], 'EUR')
          fee_eur = price * tx['fee']

        tx['fee_eur'] += fee_eur
        tx['total_profit'] -= fee_eur
        tx['total_profit_taxable'] -= fee_eur
      # end fee

      # ico => treat as selling to EUR
      if tx['clarification'] == 'ICO' and not tx['sell_asset'] == 'EUR':
        sell_price = request_price(tx['trade_date'], tx['sell_asset'], 'EUR')

        profit = decimal.Decimal(0)
        taxable_profit = decimal.Decimal(0)

        for wd in wd_entries:
          # calculate profits
          # wd: { buy_date, buy_price, amount }
          delta = tx['trade_date'] - wd['buy_date']
          tax_free = False
          if delta.total_seconds() > 3600 * 24 * 365:
            tax_free = True
          profit += wd['amount'] * (sell_price - wd['buy_price'])
          if not tax_free:
            taxable_profit += wd['amount'] * (sell_price - wd['buy_price'])

        tx['trade_profit'] += profit
        tx['total_profit'] += profit
        tx['trade_profit_taxable'] += taxable_profit
        tx['total_profit_taxable'] += taxable_profit
      # end ICO

      continue

    # if deposit === bank: just add to wallet
    if tx['transaction_type'] == 'deposit' and tx['clarification'] == 'Bank':
      check_fork_request(tx)
      exchange.deposit(tx['buy_asset'], tx['trade_date'], decimal.Decimal(1.0), tx['buy_amount'])
      # TODO: what if not EUR but USD?
      continue

    # if deposit === InterpretAsBought
    if tx['transaction_type'] == 'deposit' and tx['clarification'] == 'InterpretAsBought':
      check_fork_request(tx)
      # exchange.deposit(tx['buy_asset'], tx['trade_date'], 1.0, tx['buy_amount'])
      # TODO: interpret this as a buy call, deposit the crypto, get current price and save the profit
      #       but ignore the euros?
      deposit_netto = tx['buy_amount']
      if tx['fee'] > 0:
        deposit_netto -= tx['fee']
      price = request_price(tx['trade_date'], tx['buy_asset'], 'EUR')
      exchange.deposit(tx['buy_asset'], tx['trade_date'], price, deposit_netto)
      continue

    # if deposit === InterpretAsBought
    if tx['transaction_type'] == 'deposit' and tx['clarification'] == 'Profit':
      check_fork_request(tx)
      # exchange.deposit(tx['buy_asset'], tx['trade_date'], 1.0, tx['buy_amount'])
      # TODO: profit through margin trading, add the USD to the wallet
      #       and save the profit
      price = request_price(tx['trade_date'], tx['buy_asset'], 'EUR')
      total = tx['buy_amount'] * price
      # tx['fee_eur'] = decimal.Decimal(0)
      tx['trade_profit'] += total
      tx['total_profit'] += total
      tx['trade_profit_taxable'] += total
      tx['total_profit_taxable'] += total
      continue

    # if deposit === withdrawal match: find in withdrawals, deposit with according buy_date, aus withdrawals löschen
    if tx['transaction_type'] == 'deposit' and tx['clarification'] == 'Transfer':
      check_fork_request(tx)
      if not tx['widthdrawal_ref_id'] in withdrawals:
        print("Witdrawal not found. This should not happen! Stopping prorgramm")
        sys.exit()
      wd_entries = withdrawals[tx['widthdrawal_ref_id']]['wds']
      exchange.multi_deposit(tx['buy_asset'], wd_entries)
      continue

    # interpret as buy for a price of 0€
    if tx['transaction_type'] == 'deposit' and tx['clarification'] == 'Staking':
      check_fork_request(tx)
      # TODO get price of the coin at this time and specify the amount ...
      price = request_price(tx['trade_date'], tx['buy_asset'], 'EUR')
      exchange.deposit(tx['buy_asset'], tx['trade_date'], price, tx['buy_amount'])
      continue

    # hardfork
    if tx['transaction_type'] == 'deposit' and tx['clarification'] == 'Hardfork':
      check_fork_request(tx)
      snapshot = False

      # deposit and use date of other crypto
      for f in hardfork_wallet_snappshots:
        # tx['widthdrawal_ref_id'] = f"{origin_asset}-{fork_datetime}"
        [origin_asset, fork_datetime] = tx['widthdrawal_ref_id'].split("-")
        fork_dt = datetime.strptime(fork_datetime, '%d.%m.%Y %H:%M:%S')
        if f['origin_asset'] == origin_asset and f['fork_datetime'] == fork_dt:
          snapshot = f
          break

      if not snapshot:
        print("Snapshot for hardfork not found. Stopping here")
        print("hardfork_wallet_snappshots", hardfork_wallet_snappshots)
        print("hardfork_wallet_snappshot_requests", hardfork_wallet_snappshot_requests)
        sys.exit()

      amount_left = snapshot['fork_amount']
      for x in snapshot['wallet']:
        if x['amount'] <= amount_left:
          amount_left -= x['amount']
          exchange.deposit(snapshot['target_asset'], x['buy_date'], x['buy_price'], x['amount'])
        else:
          amount_left = decimal.Decimal(0)
          exchange.deposit(snapshot['target_asset'], x['buy_date'], x['buy_price'], amount_left)
          break
    # end hardfork

    # if deposit === ico => als Kauf betrachten
    if tx['transaction_type'] == 'deposit' and tx['clarification'] == 'ICO':
      check_fork_request(tx)

      buy_price = False

      if tx['widthdrawal_ref_id'].startswith("price"):
        buy_price = decimal.Decimal(tx['widthdrawal_ref_id'].split(':')[1])

      if not buy_price:
        # similar to crypto to crypto trade, but rely on cost of send ETH, BTC or whatever
        if not tx['widthdrawal_ref_id'] in withdrawals:
          print("Witdrawal not found (ICO). This should not happen! Stopping programm")
          sys.exit()

        # TODO wd is an array ....
        wdtx = withdrawals[tx['widthdrawal_ref_id']]['tx']

        # first, sell sell_asset to EUR
        sell_price = request_price(wdtx['trade_date'], wdtx['sell_asset'], 'EUR')
        buy_price = (wdtx['sell_amount'] * sell_price) / tx['buy_amount']

      # withdrawal (including fees and profit) part should have already been processed

      # deposit buy_asset, use trade_date of withdrawal
      exchange.deposit(tx['buy_asset'], wdtx['trade_date'], buy_price, tx['buy_amount'])
    # end ICO


    # Fee handling in CryptoTax:
    # Beim import scheint folgnedes zu gelten:
    #  - wenn fee in sell_asset => fee exklusive
    #  - wenn fee in buy_asset => fee inclusive also abziehen

    if tx['transaction_type'] == 'trade':
      check_fork_request(tx)

      if tx['sell_asset'] == 'EUR':
        # bought crypto for EUR
        price = tx['sell_amount']/tx['buy_amount']
        exchange.withdrawal('EUR', tx['sell_amount'])

        fee_eur = decimal.Decimal(0)

        netto_deposit_amount = tx['buy_amount']
        if tx['fee_asset'] == tx['buy_asset']:
          netto_deposit_amount -= tx['fee']
          fee_eur = tx['fee'] * price
        exchange.deposit(tx['buy_asset'], tx['trade_date'], price, netto_deposit_amount)

        # fee is most probabily == buy_asset, which means it is
        # already included in the buy_amount, don't have to substract fee extra
        # but

        if tx['fee_asset'] == tx['sell_asset']:
          # this is normally not the case, but substract extra
          exchange.withdrawal('EUR', tx['fee'])
          fee_eur = tx['fee']

        # add fee and negative costs to this tx
        tx['fee_eur'] += fee_eur
        tx['total_profit'] -= fee_eur
        tx['total_profit_taxable'] -= -fee_eur

        continue

      if tx['buy_asset'] == 'EUR':
        # sold crypto for EUR
        price = tx['buy_amount']/tx['sell_amount']
        netto_deposit_amount = tx['buy_amount']
        if tx['fee_asset'] == tx['buy_asset']:
          netto_deposit_amount -= tx['fee']
          fee_eur = tx['fee']
        exchange.deposit('EUR', tx['trade_date'], 1.0, netto_deposit_amount) # incl. fees when fee_asset == buy_aset
        wd_entries = exchange.withdrawal(tx['sell_asset'], tx['sell_amount'])
        profit = decimal.Decimal(0)
        taxable_profit = decimal.Decimal(0)
        for wd in wd_entries:
          # wd: { buy_date, buy_price, amount }
          delta = tx['trade_date'] - wd['buy_date']
          tax_free = False
          if delta.total_seconds() > 3600 * 24 * 365:
            tax_free = True
          profit += wd['amount'] * (price - wd['buy_price'])
          if not tax_free:
            taxable_profit += wd['amount'] * (price - wd['buy_price'])


        if tx['fee_asset'] == tx['sell_asset']:
          # this is normally not the case, but substract extra
          exchange.withdrawal(tx['fee_asset'], tx['fee'])
          fee_eur = tx['fee'] * price

        tx['fee_eur'] += fee_eur
        tx['trade_profit'] += profit
        tx['total_profit'] += profit - fee_eur
        tx['trade_profit_taxable'] += taxable_profit
        tx['total_profit_taxable'] += taxable_profit - fee_eur

        continue

      # else treat it as crypto to crypto
      # always treat as sell sell_asset to EUR
      #             and buy buy_asset for the same amount of EUR

      # first, sell sell_asset to EUR
      sell_price = request_price(tx['trade_date'], tx['sell_asset'], 'EUR')
      buy_price = request_price(tx['trade_date'], tx['buy_asset'], 'EUR')
      # fee_price = request_price(tx['trade_date'], tx['fee_asset'], 'EUR') # or just use sell/buy price

      # calculate mean price ...
      # following should hold:
      # tx['sell_amount'] * sell_price = buy_price * tx['buy_amount']
      # approximate ...
      # fix sell_price
      fix_buy_price = (tx['sell_amount'] * sell_price) / tx['buy_amount']
      # average
      avg_buy_price = (fix_buy_price + buy_price) / 2
      buy_price = avg_buy_price
      sell_price = (tx['buy_amount'] * avg_buy_price) / tx['sell_amount']

      fee_eur = decimal.Decimal(0)

      # withdrawal sell_asset
      # calculate profit based on withdrawals
      wd_entries = exchange.withdrawal(tx['sell_asset'], tx['sell_amount'])
      profit = decimal.Decimal(0)
      taxable_profit = decimal.Decimal(0)

      for wd in wd_entries:
        # calculate profits
        # wd: { buy_date, buy_price, amount }
        delta = tx['trade_date'] - wd['buy_date']
        tax_free = False
        if delta.total_seconds() > 3600 * 24 * 365:
          tax_free = True
        profit += wd['amount'] * (sell_price - wd['buy_price'])
        if not tax_free:
          taxable_profit += wd['amount'] * (sell_price - wd['buy_price'])

      # consider tax if tx['fee_asset'] == tx['sell_asset']
      if tx['fee_asset'] == tx['sell_asset']:
        exchange.withdrawal(tx['sell_asset'], tx['fee'])
        fee_eur = sell_price * tx['fee']

      # deposit buy_asset, exclude fees if fee_asset == buy_asset
      netto_deposit_amount = tx['buy_amount']
      if tx['fee_asset'] == tx['buy_asset']:
        netto_deposit_amount -= tx['fee']
        fee_eur = tx['fee'] * buy_price
      exchange.deposit(tx['buy_asset'], tx['trade_date'], buy_price, netto_deposit_amount)

      tx['fee_eur'] += fee_eur
      tx['trade_profit'] += profit
      tx['total_profit'] += profit - fee_eur
      tx['trade_profit_taxable'] += taxable_profit
      tx['total_profit_taxable'] += taxable_profit - fee_eur

    # if trade:
    #  - Bei Kauf EUR/Crypto:
    #     - Preis ermitteln: EUR/Crypto
    #     - Euro von wallet abziehen
    #     - Crypto Wallet hinzufügen mit aktuellen Datum als buy_date
    #     - Global Trade mit fee erstellen
    #  - Bei Verkauf CRYPTO/EUR:
    #     - Euro dem Wallet hinzufügen
    #     - Crypto vom Wallet abziehen
    #     - Über wallet enträge interieren bis Sell amount erreicht
    #     - Wenn buy_date > 1 Jahr her, dann als steuerfrei markieren
    #     - Fee in Euro umrechnen und als Verlust angeben
    #     - Globalen Trade erstellen mit Angabe zum Gewinn + Fee Kosten (vorher in EUR umrechnen)
    #  - Bei Crypto(USDT)/Crypto
    #     - Preise der beiden Crypto zu EUR herausfinden
    #     - Preis wählen so dass der erhaltene Mittelwert in EUR Sinn ergibt (gewichtung aus beiden)
    #     - EUR wallet wird ignoriert
    #     - Crypto 1 aus wallet etfernen (FIFO beachten) (wie sell)
    #     - Crypto 2 dem wallet hinzufügen (buy_date angeben!) (wie buy)
    #     - entsprechend globale transaktion festlegen mit gewinnt und fees
    #     - fees werden geteilt?

  # end for tx in txs:

  # calculate overall profit for 2017
  profit = decimal.Decimal(0)
  profit_taxable = decimal.Decimal(0)
  for tx in txs:
    if tx['trade_date'].year == 2017 and 'total_profit' in tx:
      profit += tx['total_profit']
      profit_taxable += tx['total_profit_taxable']

  print("Profit", "{0:.2f}".format(profit))
  print("Taxable Profit", "{0:.2f}".format(profit_taxable))

  # calculate overall profit for 2018
  profit = decimal.Decimal(0)
  profit_taxable = decimal.Decimal(0)
  for tx in txs:
    if tx['trade_date'].year == 2018 and 'total_profit' in tx:
      profit += tx['total_profit']
      profit_taxable += tx['total_profit_taxable']

  print("Profit", "{0:.2f}".format(profit))
  print("Taxable Profit", "{0:.2f}".format(profit_taxable))

  # save transactions in csv
  write_profit_txs_csv(txs)

"""
Read the transactions_steuer_2018.csv and returns an array of the contained items as dict's
"""
def read_csv():
  txs = []
  with open('transactions_steuer_2018.csv', mode='r') as csv_file:
    txs_reader = csv.DictReader(csv_file)
    for tx in txs_reader:
      # tx['id'] = int(tx['id'])
      tx['exchange_account'] = f"{tx['exchange_name']}-{tx['account_name']}"
      tx['trade_date'] = datetime.strptime(tx['trade_date'], '%d.%m.%Y %H:%M:%S')
      tx['buy_amount'] = decimal.Decimal(tx['buy_amount'] or '0')
      tx['sell_amount'] = decimal.Decimal(tx['sell_amount'] or '0')
      tx['fee'] = decimal.Decimal(tx['fee'] or '0')
      # if tx['exchange_name'] == 'Lisk Wallet':
      #   tx['trade_date'] = tx['trade_date'] + timedelta(hours=6)
      txs.append(tx)
  return txs

"""
Overrides the transactions_steuer_2018.csv with the provided transactions
"""
def write_csv(txs):
  with open('transactions_steuer_2018.csv', mode='w') as csv_file:
    fieldnames = [
      'id',   # will be generated by this tool
      'exchange_name',
      'account_name',
      'trade_date',
      'buy_asset',
      'sell_asset',
      'buy_amount',
      'sell_amount',
      'exchange_order_id',
      'fee',
      'fee_asset',
      'transaction_type',
      'clarification',
      'widthdrawal_ref_id'  # e.g. for deposits the source withdrawal
    ]

    # print('fieldnames', fieldnames)
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for tx in txs:
      wtx = tx.copy()
      wtx['trade_date'] = tx['trade_date'].strftime('%d.%m.%Y %H:%M:%S')
      wtx['buy_amount'] = tx['buy_amount']
      wtx['sell_amount'] = tx['sell_amount']
      wtx['fee'] = tx['fee']
      writer.writerow(wtx)

"""
Overrides the transactions_steuer_2018.csv with the provided transactions
"""
def write_profit_txs_csv(txs):
  with open('transactions_steuer_2018_profits.csv', mode='w') as csv_file:
    fieldnames = [
      'id',   # will be generated by this tool
      'exchange_name',
      'account_name',
      'trade_date',
      'buy_asset',
      'sell_asset',
      'buy_amount',
      'sell_amount',
      'exchange_order_id',
      'fee',
      'fee_asset',
      'transaction_type',
      'clarification',
      'widthdrawal_ref_id',  # e.g. for deposits the source withdrawal
      'fee_eur',
      'trade_profit',
      'total_profit',
      'trade_profit_taxable',
      'total_profit_taxable',
    ]

    # print('fieldnames', fieldnames)
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for tx in txs:
      if 'fee_eur' in tx:
        tx['fee_eur'] = "{0:.2f}".format(tx['fee_eur'])
      if 'trade_profit' in tx:
        tx['trade_profit'] = "{0:.2f}".format(tx['trade_profit'])
      if 'total_profit' in tx:
        tx['total_profit'] = "{0:.2f}".format(tx['total_profit'])
      if 'trade_profit_taxable' in tx:
        tx['trade_profit_taxable'] = "{0:.2f}".format(tx['trade_profit_taxable'])
      if 'total_profit_taxable' in tx:
        tx['total_profit_taxable'] = "{0:.2f}".format(tx['total_profit_taxable'])
      tx['trade_date'] = tx['trade_date'].strftime('%d.%m.%Y %H:%M:%S')
      writer.writerow(tx)


# create a new context for this task
ctx = decimal.Context()
ctx.prec = 8

import_txs()
