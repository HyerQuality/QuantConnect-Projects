#!/usr/bin/env python
# coding: utf-8

# ![QuantConnect Logo](https://cdn.quantconnect.com/web/i/icon.png)
# <hr>

# In[1]:


get_ipython().run_line_magic('matplotlib', 'inline')
# Imports
from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Jupyter")
AddReference("QuantConnect.Indicators")
from System import *
from QuantConnect import *
from QuantConnect.Data.Custom import *
from QuantConnect.Data.Market import TradeBar, QuoteBar
from QuantConnect.Securities import Futures
from QuantConnect.Jupyter import *
from QuantConnect.Indicators import *
from datetime import *
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
#from pandas_datareader import data as wb
from scipy.stats import norm
get_ipython().run_line_magic('matplotlib', 'inline')
# Create an instance
qb = QuantBook()
dataPoints = 3000
resolution = Resolution.Daily

# Select asset data
spxl = qb.AddEquity("SPXL")
tvix = qb.AddEquity("TVIX")
spxs = qb.AddEquity("SPXS")
svxy = qb.AddEquity("SVXY")
url = 'http://www.cboe.com/publish/scheduledtask/mktdata/datahouse/vixcurrent.csv'
column_names = ['Open', 'High', 'Low', 'Close']
vix = pd.read_csv(url, names = column_names, skiprows=1, engine='python', sep=',')


# # Historical Data Requests
# We can use the QuantConnect API to make Historical Data Requests. The data will be presented as multi-index pandas.DataFrame where the first index is the Symbol.
# 
# For more information, please follow the link.

# In[2]:


h1 = qb.History(qb.Securities.Keys, dataPoints, resolution)
h2 = vix["Close"][1:].astype('float')

# Plot closing prices from "SPY" 
fig, axs = plt.subplots(1, 3, figsize=(15, 5))

h1.loc["SPXL"]["close"].plot(ax=axs[0])
h1.loc["TVIX"]["close"].plot(ax=axs[1])
h2.plot(ax=axs[2])


# # Indicators
# We can easily get the indicator of a given symbol with QuantBook.
# 
# For all indicators, please checkout QuantConnect Indicators Reference Table

# In[3]:


# Define the indicator
ema_short = ExponentialMovingAverage(2)
ema_long = ExponentialMovingAverage(13)

# Gets historical data of indicator
tvix_short_warm = qb.Indicator(ema_short, "TVIX", dataPoints, resolution)
tvix_long_warm = qb.Indicator(ema_long, "TVIX", dataPoints, resolution)
spxl_short_warm = qb.Indicator(ema_short, "SPXL", dataPoints, resolution)
spxl_long_warm = qb.Indicator(ema_long, "SPXL", dataPoints, resolution)

tvix_ema_signal = tvix_short_warm/tvix_long_warm
spxl_ema_signal = spxl_short_warm/spxl_long_warm

tvix_ema_signal_std = round(np.std(tvix_ema_signal),3)
tvix_ema_signal_avg = round(np.mean(tvix_ema_signal),3)

spxl_ema_signal_std = round(np.std(spxl_ema_signal),3)
spxl_ema_signal_avg = round(np.mean(spxl_ema_signal),3)

#TVIX
plusOneStd = (float(tvix_ema_signal_avg+tvix_ema_signal_std))
minusOneStd = (float(tvix_ema_signal_avg-tvix_ema_signal_std))
plusTwoStd = (float(tvix_ema_signal_avg+2*tvix_ema_signal_std))
minusTwoStd = (float(tvix_ema_signal_avg-2*tvix_ema_signal_std))
plusThreePtFiveStd = (float(tvix_ema_signal_avg+3.5*tvix_ema_signal_std))
minusThreeStd = (float(tvix_ema_signal_avg-3*tvix_ema_signal_std))
plusFourStd = (float(tvix_ema_signal_avg+4*tvix_ema_signal_std))
plusSixStd = (float(tvix_ema_signal_avg+6*tvix_ema_signal_std))
minusSixStd = (float(tvix_ema_signal_avg-6*tvix_ema_signal_std))

#SPXL
spxlplusPtTwoFiveStd = (float(spxl_ema_signal_avg+0.25*spxl_ema_signal_std))
spxlplusPtFiveStd = (float(spxl_ema_signal_avg+0.5*spxl_ema_signal_std))
spxlplusOneStd = (float(spxl_ema_signal_avg+spxl_ema_signal_std))
spxlminusOneStd = (float(spxl_ema_signal_avg-spxl_ema_signal_std))
spxlplusOnePtFiveStd = (float(spxl_ema_signal_avg+1.5*spxl_ema_signal_std))
spxlplusTwoStd = (float(spxl_ema_signal_avg+2*spxl_ema_signal_std))
spxlminusTwoStd = (float(spxl_ema_signal_avg-2*spxl_ema_signal_std))
spxlplusThreeStd = (float(spxl_ema_signal_avg+3*spxl_ema_signal_std))
spxlminusThreeStd = (float(spxl_ema_signal_avg-3*spxl_ema_signal_std))
spxlplusFourStd = (float(spxl_ema_signal_avg+4*spxl_ema_signal_std))
spxlminusFourStd = (float(spxl_ema_signal_avg-4*spxl_ema_signal_std))
spxlplusSixStd = (float(spxl_ema_signal_avg+6*spxl_ema_signal_std))
spxlminusSixStd = (float(spxl_ema_signal_avg-6*spxl_ema_signal_std))

#SPXL
print("SPXL +1:")
print(spxlplusOneStd)
print("SPXL +1.5:")
print(spxlplusOnePtFiveStd)
print("SPXL +2:")
print(spxlplusTwoStd)
print("SPXL +3:")
print(spxlplusThreeStd)
print("SPXL +4:")
print(spxlplusFourStd)
print("SPXL +6:")
print(spxlplusSixStd)
print("SPXL -1:")
print(spxlminusOneStd)
print("SPXL -2:")
print(spxlminusTwoStd)
print("SPXL -3:")
print(spxlminusThreeStd)
print("SPXL -4:")
print(spxlminusFourStd)


#TVIX
print("TVIX +1:")
print(plusOneStd)
print("TVIX +2:")      
print(plusTwoStd)
print("TVIX +3.5:")     
print(plusThreePtFiveStd)
print("TVIX +6:")
print(plusSixStd)
print("TVIX -1:")
print(minusOneStd)
print("TVIX -2:")
print(minusTwoStd)
print("TVIX -3:")
print(minusThreeStd)

tvix_ln_returns = ((round(np.log(h1.loc["TVIX"]["close"])[:-1].values - np.log(h1.loc["TVIX"]["close"])[1:],3))+1)

# Plot    
fig, axs = plt.subplots(1, 2, figsize=(15, 15))


tvix_ema_signal.plot(ax=axs[0],figsize=(10, 10), linewidth=1.0)
spxl_ema_signal.plot(ax=axs[1],figsize=(15, 15), linewidth=1.0)

#SPXL
axs[1].axhline(y=1, color='black', linestyle='--', linewidth=4.0)
axs[1].axhline(spxlplusOneStd,color='red',linestyle='--')
axs[1].axhline(spxlplusOnePtFiveStd,color='purple',linestyle='--')
axs[1].axhline(spxlminusOneStd,color='red',linestyle='--')
axs[1].axhline(spxlplusTwoStd,color='red',linestyle='--')
axs[1].axhline(spxlminusTwoStd,color='red',linestyle='--')
axs[1].axhline(spxlplusThreeStd,color='red',linestyle='--')
axs[1].axhline(spxlminusThreeStd,color='red',linestyle='--')
axs[1].axhline(spxlplusFourStd,color='green',linestyle='--')
axs[1].axhline(spxlminusFourStd,color='green',linestyle='--')
axs[1].axhline(spxlplusSixStd,color='red',linestyle='--')

#TVIX
axs[0].axhline(y=1, color='black', linestyle='--', linewidth=4.0)
axs[0].axhline(plusOneStd, color='red',linestyle='--')
axs[0].axhline(minusOneStd,color='red',linestyle='--')
axs[0].axhline(plusTwoStd,color='red',linestyle='--')
axs[0].axhline(minusTwoStd,color='red',linestyle='--')
axs[0].axhline(plusThreePtFiveStd,color='purple',linestyle='--')
axs[0].axhline(minusThreeStd,color='red',linestyle='--')
axs[0].axhline(plusSixStd,color='red',linestyle='--')


#ema_short_warm.plot(ax=axs[0])
#tvix_ema_ln.plot(ax=axs[0])
#spxl_ema_ln.plot(ax=axs[0])

#tvix_ema_signal.plot(ax=axs[0])
#ax2 = axs[0].twinx()
#((round(np.log(h1.loc["TVIX"]["close"])[:-1].values - np.log(h1.loc["TVIX"]["close"])[1:],3))+1).plot(ax=axs[0], color='orange', linestyle='--', linewidth=3.0)
#plt.axhline(y=1, color='black', linestyle='--')
#plt.axhline(plusOneStd,color='red',linestyle='--')
#plt.axhline(minusOneStd,color='red',linestyle='--')
#plt.axhline(plusTwoStd,color='red',linestyle='--')
#plt.axhline(minusTwoStd,color='red',linestyle='--')
#plt.axhline(plusThreeStd,color='red',linestyle='--')
#plt.axhline(minusThreeStd,color='red',linestyle='--')
#plt.axhline(plusSixStd,color='red',linestyle='--')
#plt.axhline(minusSixStd,color='red',linestyle='--')


# # Monte Carlo Regression Research
# Attempting to predict future stock price movement by iterating random outcomes many times

# In[20]:


SPXL_Log_Returns = np.log(1+h1.loc["SPXL"]["close"].pct_change())
SPXL_Log_Returns.tail(5)


# In[5]:


#Operations on returns
Average_SPXL_Log_Returns = SPXL_Log_Returns.mean()
Variance_SPXL_Log_Returns = SPXL_Log_Returns.var()
STDEV_SPXL_Log_Returns = SPXL_Log_Returns.std()
drift = Average_SPXL_Log_Returns -(0.5*Variance_SPXL_Log_Returns)


# In[18]:


#Brownian motion construction variables
t_intervals = 30
iterations = 1000000

drift = np.array(drift)
std = np.array(STDEV_SPXL_Log_Returns)
random_matrix = np.random.rand(t_intervals,iterations)
Z = norm.ppf(random_matrix) 

# In[19]:


#Brownian motion regression
SPXL_Daily_Returns = np.exp(drift + std*Z)

Initial_Price = h1.loc["SPXL"]["close"][-1]

price_list = np.zeros_like(SPXL_Daily_Returns) #creates an array of exact size of a previously defined arrary
price_list[0] = Initial_Price

for t in range(1,t_intervals):
    price_list[t] = price_list[t-1]*SPXL_Daily_Returns[t]

'''fig, axs = plt.subplots(1, 2, figsize=(10, 10))
#plt.figure(figsize=(10,6))
plt.plot(price_list)
u = price_list.mean()
v = price_list.std()
plt.axhline(u, color='black', linestyle='--', linewidth=4.0)
plt.axhline(u+v, color='red',linestyle='--', linewidth=4.0)
plt.axhline(u-v, color='red', linestyle='--', linewidth=4.0)'''

average_enddate_price = []
price_list.item((t_intervals-1, iterations-1))

for i in range(0, t_intervals-1):
    average_enddate_price.append(price_list.item((i, iterations-1)))
    
print(np.mean(average_enddate_price))
print(np.std(average_enddate_price))


# In[ ]:





# In[ ]:





# In[ ]:




