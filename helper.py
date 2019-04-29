def to_decimal_int(string):
  if string and len(string) > 0:
    return int(float(string) * 100000000)
  return 0

def to_currency_string(number, decimals=8):
  if decimals == 8:
    return "{0:.8f}".format(number / 100000000)
  return "{0:.2f}".format(number / 100000000)
