#from flask import Flask, request, jsonify, abort, json
from flask_rate_limit import *
from sqltools import *
import commands
from properties_service import rawecolist
from values_service import getCurrentPriceRaw
from cacher import *

app = Flask(__name__)
app.debug = True

@app.route('/status')
@ratelimit(limit=20, per=60)
def status():
  rev=revision().get_data()
  #print rev
  try:
    rev=json.loads(rev)
  except:
    rev={'revision':rev}

  st=stats().get_data()
  #print st
  try:
    st=json.loads(st)
  except:
    st={'stats':st}

  coms=commits().get_data()
  #print coms
  try:
    coms=json.loads(coms)
  except:
    coms={'commits':coms}

  #print rev, st, coms
  merged_response = {key: value for (key, value) in (rev.items() + st.items() + coms.items())}
  return jsonify(merged_response)


def raw_revision():
  ckey="info:stats:revision"
  try:
    response = json.loads(lGet(ckey))
  except:
    ROWS=dbSelect("select blocknumber, blocktime from blocks order by blocknumber desc limit 1")
    response = {'last_block': ROWS[0][0], 'last_parsed': str(ROWS[0][1])}
    #cache 1 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,60)
  return response

@app.route('/revision')
@ratelimit(limit=20, per=60)
def revision():
  return jsonify(raw_revision())


@app.route('/stats')
@ratelimit(limit=20, per=60)
def stats():
  ckey="info:stats:stats"
  try:
    response=json.loads(lGet(ckey))
  except:
    ROWS=dbSelect("select count(walletid) from wallets where walletstate='Active'")
    wallets=ROWS[0][0]

    ROWS=dbSelect("select count(*) from transactions where txrecvtime >= NOW() - '1 day'::INTERVAL")
    txs=ROWS[0][0]

    opc=len(rawecolist(1)['properties'])
    topc=len(rawecolist(2)['properties'])

    obtc = getCurrentPriceRaw('OMNI')['price']
    ousd = getCurrentPriceRaw('BTC')['price'] * obtc

    response = {'amount_of_wallets': wallets, 'txcount_24hr':txs, 'properties_count':opc, 'test_properties_count':topc, 'omni_btc':obtc, 'omni_usd':ousd}
    #cache 20min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,1200)

  json_response = jsonify(response)
  return json_response


@app.route('/commits')
@ratelimit(limit=20, per=60)
def commits():
  ckey="info:stats:commits"
  try:
    json_response = json.loads(lGet(ckey))
  except:  
    owlog=commands.getoutput('git --git-dir=../.git log --pretty=tformat:"%cd | %h | %H | %s" --date=short -n 12 --no-merges')
    response=[]
    for x in owlog.split('\n'):
      y=x.split('|', 3)
      response.append({
        'date': str(y[0]),
        'commitshort': str(y[1].strip()),
        'commitlong': str(y[2].strip()),
        'msg': str(y[3].strip())
      })
    json_response = {'commits': response}
    #cache 60 min
    lSet(ckey,json.dumps(json_response))
    lExpire(ckey,3600)

  return jsonify(json_response)
