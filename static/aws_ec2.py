import math, random, sys, json
from statistics import mean, stdev


event = json.loads(sys.stdin.read())


dt = event['key1']
close = event['key2']
buy = event['key3']
sell = event['key4']
h = event['key5']
d = event['key6']
t = event['key7']
r = event['key8']
minhistory = h
shots = d
var95_list = []
var99_list = []
dates = []
for i in range(minhistory, len(close)):
	if t == "buy":
	    if buy[i] == 1: # if we’re interested in Buy signals
		close_data = close[i-minhistory:i]
		pct_change = [(close_data[i] - close_data[i-1]) / close_data[i-1] for i in range(1,len(close_data))]
		mn = mean(pct_change)
		std = stdev(pct_change)
		# generate much larger random number series with same broad characteristics 
		simulated = [random.gauss(mn,std) for x in range(shots)]
		# sort and pick 95% and 99%  - not distinguishing long/short risks here
		simulated.sort(reverse=True)
		var95 = simulated[int(len(simulated)*0.95)]
		var99 = simulated[int(len(simulated)*0.99)]
		var95_list.append(var95)
		var99_list.append(var99)
		dates.append(str(dt[i]))
	elif t == "sell":
	    if sell[i] == 1: # if we’re interested in Sell signals
		close_data = close[i-minhistory:i]
		pct_change = [(close_data[i] - close_data[i-1]) / close_data[i-1] for i in range(1,len(close_data))]
		mn = mean(pct_change)
		std = stdev(pct_change)
		# generate much larger random number series with same broad characteristics 
		simulated = [random.gauss(mn,std) for x in range(shots)]
		# sort and pick 95% and 99%  - not distinguishing long/short risks here
		simulated.sort(reverse=True)
		var95 = simulated[int(len(simulated)*0.95)]
		var99 = simulated[int(len(simulated)*0.99)]
		var95_list.append(var95)
		var99_list.append(var99)
		dates.append(str(dt[i]))

output = {"dates" : dates,
	"var95" : var95,
	"var99" : var99
	}

output = json.dumps(output)

print("Content-Type: application/json")
print("")
print(output)

