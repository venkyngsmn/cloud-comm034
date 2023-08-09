import os, logging, time 
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from pandas_datareader import data as pdr
import random, math
from flask import Flask, request, render_template
from statistics import mean, stdev 
import json, http.client, requests
from concurrent.futures import ThreadPoolExecutor

os.environ['AWS_SHARED_CREDENTIALS_FILE']='./cred'

import boto3

app = Flask(__name__)
lambda_url =  "https://hs02ojgqx9.execute-api.us-east-1.amazonaws.com/default/simulate"


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

	# Three Crows
	if (data.Open[i] - data.Close[i]) >= body  \
	and data.Close[i] < data.Close[i-1] \
	and (data.Open[i-1] - data.Close[i-1]) >= body  \
	and data.Close[i-1] < data.Close[i-2]  \
	and (data.Open[i-2] - data.Close[i-2]) >= body:
		data.at[data.index[i], 'Sell'] = 1
	# print("Sell at ", data.index[i])

# Converting to dictionary because AWS hates Pandas
data = data.reset_index()
data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
dict_data = data.to_dict(orient='list')

# Rendering template function
def doRender(tname, values={}):
	if not os.path.isfile(os.path.join(os.getcwd(), 'templates/'+tname)):
		return render_template('index.htm')
	return render_template(tname, **values)


# Function of the 'warmup'
@app.route('/calculate', methods=['POST'])
def initHandler():
	if request.method == 'POST':
		
		global s
		global r
		s = request.form.get('s')
		r = request.form.get('r')
		
		# warming up lambda
		if s == 'lambda':
			conn = http.client.HTTPSConnection("hs02ojgqx9.execute-api.us-east-1.amazonaws.com")
			return doRender('form.htm', {'note': "Connected to "+ str(conn)})
			
		# warming up EC2 instances
		elif s == 'ec2':
			ec2 = boto3.resource('ec2', region_name='us-east-1')
			user_data = """#!/bin/bash
					apt update -y
					apt install python3 apache2 -y
					apache2ctl restart

					wget https://gitlab.surrey.ac.uk/vn00197/comm034/-/raw/main/aws_ec2.py -P /var/www/html
					chmod 755 /var/www/html/aws_ec2.py

					wget https://gitlab.surrey.ac.uk/vn00197/comm034/-/raw/main/apache2.conf -O /etc/apache2/apache2.conf

					a2enmod cgi
					service apache2 restart"""
			global st
			st = time.time()
			instances = ec2.create_instances(        
				ImageId = 'ami-001a7d2a632ee2e35',
				MinCount = int(r),
				MaxCount = int(r),
				InstanceType = 't2.micro',
				KeyName = 'us-east-1kp',
				SecurityGroups = ['SSH'],
				UserData = user_data
				)
			global dnss
			dnss = []
			for i in instances:
				i.wait_until_running()
				i.load()
				dnss.append(i.public_dns_name)
			time.sleep(60)
			return doRender('form.htm', {'note': "Currently running "+ str(len(dnss)) + " EC2 instances"})
		
@app.route('/results', methods=['POST'])
def calculateHandler():
	if request.method == 'POST':
		ls = ['h', 'd', 't', 'p']
		h, d, t, p  = [request.form.get(i) for i in ls]
		
		json_inputs = '{"key1":"'+str(dict_data['Date'])+'","key2":"'+str(dict_data['Close'])+'","key3":"'+str(dict_data['Buy'])+'","key4":"'+str(dict_data['Sell'])+'","key5":"'+str(h)+'","key6":"'+str(d)+'","key7":"'+str(t)+'"}'
		
		# AWS Lambda execution
		if s == 'lambda':
			def getpage(id):
				conn = http.client.HTTPSConnection("hs02ojgqx9.execute-api.us-east-1.amazonaws.com")
				conn.request("POST", "/default/simulate", json_inputs)   
				response = conn.getresponse()
				data = response.read().decode('utf-8')
				result = json.loads(data)
				return result
			runs = list(range(int(r)))
			def getpages():
				with ThreadPoolExecutor() as executor:
					results = executor.map(getpage, runs)
				return results
			
			start = time.time()
			results = list(getpages())
			
			time_taken = time.time() - start
			
			cost = "$ "+str(float(r) * 128 / 1024 * time_taken * 0.0000166667)
		
		# AWS EC2 execution
		elif s=='ec2':

			results = []     
			def getpage(url):
				ec2_url = "http://" + url + "/aws_ec2.py"
				json_output = requests.post(ec2_url, headers={"Content-Type":"application/json"}, data=json_inputs)
				output = json.loads(json_output.text)
				
				result= [] 
				result.append(output['dates'])
				result.append(output['var95'])
				result.append(output['var99'])
				
				return result
			def getpages():
				with ThreadPoolExecutor() as executor:
					results = executor.map(getpage, dnss)
				return results
			results = getpages()
			time_taken = time.time() - st
			
			cost = "$" + str(float(r) * 0.0134 * time_taken / 60)
			
		
		# Averaging the results
		pl = []
		dates = []
		var95s = []
		var99s = []
		for vals in results:
			dates = vals[0]
			var95s.append(vals[1])
			var99s.append(vals[2])
		for date in dates:
			idx = dict_data['Date'].index(date)
			new_idx = idx + int(p)
			current_price = dict_data['Close'][idx]
			try:
				profit = dict_data['Close'][new_idx] - current_price
			except:
				pl.append("No data")
				continue
				
			if t =='sell': 
				profit = -1*profit
			pl.append(float(profit))
		
		var95_avgd = []
		var99_avgd = []
		
		var95zip = list(zip(*var95s))
		var99zip = list(zip(*var99s))
		
		var95_avgd = [mean(i) for i in var95zip]
		avg95 = mean(var95_avgd)
		var99_avgd = [mean(i) for i in var99zip]
		avg99 = mean(var99_avgd)
		
		note = list(zip(dates, var95_avgd, var99_avgd, pl))
		
		
		# Creating the charts using the image-charts api
		str_d = '|'.join(dates)
		str_95 = ','.join([str(i) for i in var95_avgd])
		str_avg95 = ','.join([str(avg95) for i in range(len(dates))])
		str_99 = ','.join([str(i) for i in var99_avgd])
		str_avg99 = ','.join([str(avg99) for i in range(len(dates))])
		labels = "95%RiskValue|99%RiskValue|Average95%|Average99%"
		
		chart = f"https://image-charts.com/chart?cht=lc&chs=999x499&chd=a:{str_95}|{str_99}|{str_avg95}|{str_avg99}&chxt=x,y&chdl={labels}&chxl=0:|{str_d}&chxs=0,min90&chco=1984C5,C23728,A7D5ED,E1A692&chls=3|3|3,5,3|3,5,3"

		
		# audit page bucket
		s3 = boto3.client('s3') 
		# retrieving the previous data from the bucket
		previous = s3.get_object(Bucket="hashbang14", Key="audit_data.json")
		pre_data = previous['Body'].read()
		pre = json.loads(pre_data)
		pft = sum([float(i) for i in pl if not isinstance(i, str)])
		print(pft)
		
		pre['s'].append(s)
		pre['r'].append(r)
		pre['h'].append(int(h))
		pre['d'].append(int(d))
		pre['t'].append(t)
		pre['p'].append(int(p))
		pre['avg95'].append(avg95) 
		pre['avg99'].append(avg99)
		pre['profit'].append(pft)
		pre['cost'].append(cost)
		pre['time'].append(time_taken)
		
		str_json = json.dumps(pre)
		
		# sending data to an S3 bucket
		s3.put_object(Body=str_json.encode('utf-8'), Bucket="hashbang14", Key="audit_data.json")
		
		
		return doRender('results.htm', {'note': note, 'chart':chart, 's':s, 'r':r, 'h':h, 'd':d, 't':t, 'p':p, 'avg95':avg95, 'avg99':avg99, 'cost':cost, 'time': time_taken, 'profit':pft})
		
@app.route('/audit')
def auditHandler():	
	s3 = boto3.client('s3')
	data = s3.get_object(Bucket='hashbang14', Key='audit_data.json')
	result = json.loads(data['Body'].read())
	# result = json.loads(result)
	vals = list(zip(result['s'], result['r'], result['h'], result['d'], result['t'], result['p'], result['avg95'], result['avg99'], result['cost'], result['time'], result['profit'])) 
	return doRender('audit.htm', {'note':vals})
		
@app.route('/terminate')
def terminateHandler():
	ec2 = boto3.resource('ec2', region_name="us-east-1")
	filters = [{'Name': 'instance-state-name', 'Values': ['running']}]
	instances = ec2.instances.filter(Filters=filters)
	n = len(list(instances))
	if n:
		response = ec2.instances.filter(InstanceIds = [i.id for i in instances]).terminate()
		return doRender("index.htm", {"note": "Terminated " + str(n) + " instances"})
	else:
		return doRender("index.htm", {"note": "No instances are currently running"})
		
'''
@app.route('/cacheavoid/<name>')
def cacheavoid(name):
	if not os.path.isfile(os.path.join(os.getcwd(), 'static/' + name)):
		return ('No such file ' + os.path.join(os.getcwd(), 'static/' + name))
	f = open(os.path.join(os.getcwd(), 'static/' + name))
	contents = f.read()
	f.close()  
	return contents
'''
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def mainPage(path):
	return doRender(path)

if __name__ == '__main__':
	app.run(host='127.0.0.1', port=8080, debug=True)

