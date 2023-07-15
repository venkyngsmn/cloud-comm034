import os, logging, time 
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from pandas_datareader import data as pdr
import random, math
from flask import Flask, request, render_template
from statistics import mean, stdev
import boto3, json, http.client
from concurrent.futures import ThreadPoolExecutor

yf.pdr_override()
lambda_url =  "https://hs02ojgqx9.execute-api.us-east-1.amazonaws.com/default/simulate"
app = Flask(__name__)

def doRender(tname, values={}):
	if not os.path.isfile(os.path.join(os.getcwd(), 'templates/'+tname)):
		return render_template('index.htm')
	return render_template(tname, **values)

def aws_lambda(data, h, d, t, r):
	def getpage(id):
		if request.method == 'POST':
			conn = http.client.HTTPSConnection("hs02ojgqx9.execute-api.us-east-1.amazonaws.com")
			json = '{"key1":"'+str(data['Date'])+'","key2":"'+str(data['Close'])+'","key3":"'+str(data['Buy'])+'","key4":"'+str(data['Sell'])+'","key5":"'+str(h)+'","key6":"'+str(d)+'","key7":"'+str(t)+'","key8":"'+str(r)+'"}'
			conn.request("POST", "/default/simulate", json)
			response = conn.getresponse()
			vals = response.read().decode('utf-8')
			return eval(vals)
	runs = list(range(int(r)))
	def getpages():
		with ThreadPoolExecutor() as executor:
			results = executor.map(getpage, runs)
		return results
	start = time.time()
	vals = getpages()
	end = time.time() - start
	print(end, 'seconds')
	return doRender('index.htm', {'note': vals})
def monte_carlo(s, r, h, d, t, p):
	
	# override yfinance with pandas – seems to be a common step
	yf.pdr_override()

	# Get stock data from Yahoo Finance – here, asking for about 3 years
	today = date.today()
	decadeAgo = today - timedelta(days=1095)

	# Get stock data from Yahoo Finance – here, Gamestop which had an interesting 
	#time in 2021: https://en.wikipedia.org/wiki/GameStop_short_squeeze 

	data = pdr.get_data_yahoo('BP.L', start=decadeAgo, end=today)

	# Other symbols: TSLA – Tesla, AMZN – Amazon, ZM – Zoom, ETH-USD – Ethereum-Dollar etc.

	# Add two columns to this to allow for Buy and Sell signals
	# fill with zero
	data['Buy']=0
	data['Sell']=0


	# Find the signals – uncomment print statements if you want to 
	# look at the data these pick out in some another way
	# e.g. check that the date given is the end of the pattern claimed

	for i in range(2, len(data)): 

	    body = 0.01

	       # Three Soldiers
	    if (data.Close[i] - data.Open[i]) >= body  \
	and data.Close[i] > data.Close[i-1]  \
	and (data.Close[i-1] - data.Open[i-1]) >= body  \
	and data.Close[i-1] > data.Close[i-2]  \
	and (data.Close[i-2] - data.Open[i-2]) >= body:
	    	data.at[data.index[i], 'Buy'] = 1
		# print("Buy at ", data.index[i])

	       # Three Crows
	    if (data.Open[i] - data.Close[i]) >= body  \
	and data.Close[i] < data.Close[i-1] \
	and (data.Open[i-1] - data.Close[i-1]) >= body  \
	and data.Close[i-1] < data.Close[i-2]  \
	and (data.Open[i-2] - data.Close[i-2]) >= body:
	    	data.at[data.index[i], 'Sell'] = 1
		# print("Sell at ", data.index[i])
	
	# Converting to dictionary because Lambda hates Pandas
	data = data.reset_index()
	data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
	dict_data = data.to_dict(orient='list') 
	
	return aws_lambda(dict_data, h, d, t, r) 

@app.route('/calculate', methods=['POST'])
def calculateHandler():
	if request.method == 'POST':
		ls = ['s', 'r', 'h', 'd', 't', 'p']
		s, r, h, d, t, p  = [request.form.get(i) for i in ls]
		
		return monte_carlo(s, r, h, d, t, p)

		
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def mainPage(path):
	return doRender(path)

if __name__ == '__main__':
	app.run(host='127.0.0.1', port=8080, debug=True)
	
