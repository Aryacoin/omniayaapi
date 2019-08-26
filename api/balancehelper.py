import json
from sqltools import *
from blockchain_utils import *
from property_service import getpropertyraw
from cacher import *
from common import *
from validator import isvalid

def get_balancedata(address):
    addr = re.sub(r'\W+', '', address) #check alphanumeric
    if isvalid(addr):
      btcdata = bc_getbalance(addr)
      return getBalanceData(address,btcdata)
    else:
      return {'balance':'Error, invalid address'}

def get_bulkbalancedata(addresses):
    btclist=bc_getbulkbalance(addresses)
    retval = {}
    for address in addresses:
      try:
        if address in btclist:
          out = btclist[address]
          err = None
        else:
          out = ''
          err = "Missing"
      except TypeError:
        out = ''
        err = "Missing"
      btcdata={'bal':out,'error':err}
      balance_data=getBalanceData(address,btcdata)
      retval[address]=balance_data
    return retval


def getBalanceData(address,btcdata):
    addr = re.sub(r'\W+', '', address) #check alphanumeric
    rev=raw_revision()
    cblock=rev['last_block']
    ckey="data:baldata:"+str(addr)+":"+str(cblock)
    try:
      #check cache
      balance_data = json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
      out = btcdata['bal']
      err = btcdata['error']     
      if err != None or out == '':
        btc_bal = str(long(0))
        btc_bal_err = True
      else:
        try:
          btc_bal = str(long( out ))
          btc_bal_err = False
        except ValueError:
          btc_bal = str(long(0))
          btc_bal_err = True
      for brow in  balance_data['balance']:
        if brow['id']==0:
          brow['value']=btc_bal
          brow['error']=btc_bal_err
    except:
      print_debug(("cache looked failed",ckey),7)
      ROWS=dbSelect("""select
                       f1.propertyid, sp.propertytype, f1.balanceavailable, f1.pendingpos, f1.pendingneg, f1.balancereserved, f1.balancefrozen
                     from
                       (select
                          COALESCE(s1.propertyid,s2.propertyid) as propertyid, COALESCE(s1.balanceavailable,0) as balanceavailable, COALESCE(s1.balancefrozen,0) as balancefrozen,
                          COALESCE(s2.pendingpos,0) as pendingpos,COALESCE(s2.pendingneg,0) as pendingneg, COALESCE(s1.balancereserved,0) as balancereserved
                        from
                          (select propertyid,balanceavailable,balancereserved,balancefrozen
                           from addressbalances
                           where address=%s) s1
                        full join
                          (SELECT atx.propertyid,
                             sum(CASE WHEN atx.balanceavailablecreditdebit > 0 THEN atx.balanceavailablecreditdebit ELSE 0 END) AS pendingpos,
                             sum(CASE WHEN atx.balanceavailablecreditdebit < 0 THEN atx.balanceavailablecreditdebit ELSE 0 END) AS pendingneg
                           from
                             addressesintxs atx, transactions tx
                           where
                             atx.txdbserialnum=tx.txdbserialnum
                             and tx.txstate='pending'
                             and tx.txdbserialnum<-1
                             and atx.address=%s
                           group by
                             atx.propertyid) s2
                        on s1.propertyid=s2.propertyid) f1
                     inner join smartproperties sp
                     on f1.propertyid=sp.propertyid and (sp.protocol='Omni' or sp.protocol='Bitcoin')
                     order by f1.propertyid""",(addr,addr))
      balance_data = { 'balance': [] }
      out = btcdata['bal']
      err = btcdata['error']
      for balrow in ROWS:
        cID = str(int(balrow[0])) #currency id
        sym_t = ('BTC' if cID == '0' else ('OMNI' if cID == '1' else ('T-OMNI' if cID == '2' else 'SP' + cID) ) ) #symbol template
        #1 = new indivisible property, 2=new divisible property (per spec)
        divi = True if int(balrow[1]) == 2 else False
        res = { 'symbol' : sym_t, 'divisible' : divi, 'id' : cID }
        #inject property details but remove issuanecs
        res['propertyinfo'] = getpropertyraw(cID)
        if 'issuances' in res['propertyinfo']:
          res['propertyinfo'].pop('issuances')
        res['pendingpos'] = str(long(balrow[3]))
        res['pendingneg'] = str(long(balrow[4]))
        res['reserved'] = str(long(balrow[5]))
        res['frozen'] = str(long(balrow[6]))
        if cID == '0':
          #get btc balance from bc api's
          if err != None or out == '':
            #btc_balance[ 'value' ] = str(long(-555))
            btc_balance[ 'value' ] = str(long(0))
            btc_balance[ 'error' ] = True
          else:
            try:
              #if balrow[4] < 0:
              #  res['value'] = str(long( out ) + long(balrow[4]))
              #else:
              res['value'] = str(long( out ))
            except ValueError:
              #btc_balance[ 'value' ] = str(long(-555))
              btc_balance[ 'value' ] = str(long(0))
              btc_balance[ 'error' ] = True
        else:
          #get regular balance from db 
          #if balrow[4] < 0 and not balrow[6] > 0:
          #  #update the 'available' balance immediately when the sender sent something. prevent double spend as long as its not frozen
          #  res['value'] = str(long(balrow[2]+balrow[4]))
          #else:
          res['value'] = str(long(balrow[2]))
        #res['reserved_balance'] = ('%.8f' % float(balrow[5])).rstrip('0').rstrip('.')
        balance_data['balance'].append(res)
      #check if we got BTC data from DB, if not trigger manually add
      addbtc=True
      for x in balance_data['balance']:
        if "BTC" in x['symbol']:
          addbtc=False
      if addbtc:
        btc_balance = { 'symbol': 'BTC', 'divisible': True, 'id' : '0', 'error' : False }
        if err != None or out == '':
          #btc_balance[ 'value' ] = str(long(-555))
          btc_balance[ 'value' ] = str(long(0))
          btc_balance[ 'error' ] = True
        else:
          try:
            #btc_balance[ 'value' ] = str(long( json.loads( out )[0][ 'paid' ]))
            #btc_balance[ 'value' ] = str(long( json.loads( out )['data']['balance']*1e8 ))
            btc_balance[ 'value' ] = str(long( out ))
          except ValueError:
            #btc_balance[ 'value' ] = str(long(-555))
            btc_balance[ 'value' ] = str(long(0))
            btc_balance[ 'error' ] = True
        btc_balance['pendingpos'] = str(long(0))
        btc_balance['pendingneg'] = str(long(0))
        btc_balance['propertyinfo'] = getpropertyraw(btc_balance['id'])
        balance_data['balance'].append(btc_balance)
      #cache result for 1 min
      lSet(ckey,json.dumps(balance_data))
      lExpire(ckey,60)
    return balance_data
