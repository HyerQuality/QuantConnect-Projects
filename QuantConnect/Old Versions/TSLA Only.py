import numpy as np
import pandas as pd

from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Common")

from datetime import datetime, timedelta
from System import *
from QuantConnect import *
from QuantConnect.Algorithm import *
from QuantConnect.Data.Market import TradeBar
import json
import math
from QuantConnect.Data import SubscriptionDataSource
from QuantConnect.Python import PythonData

class TeslaTrade(QCAlgorithm):
    '''Trades only Tesla.  Seeks to use momentum indictors to mitigate drawdown risk while capturing the bulk of the gains'''

    def Initialize(self):
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialize.'''

        # Chart - Master Containers for the Charts:
        stockPlot_1 = Chart('RSI')
        stockPlot_2 = Chart('MFI')
        stockPlot_3 = Chart('EMADiff')
        stockPlot_4 = Chart('Margin Remaining')
        stockPlot_5 = Chart('Gap')
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = Resolution.Daily
        self.UniverseSettings.Leverage = 2

        #Initial investment and backtest period
        self.SetStartDate(2010,7,29)                                 #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1))        #Set End Date
        self.SetCash(47441)                                       #Set Strategy Cash

        #Initialize list of Open Orders
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Capture initial investment for risk off purposes
        self.marginRemaining = self.Portfolio.MarginRemaining
        self.OpenPortValue = self.Portfolio.TotalPortfolioValue
        self.ClosingPortValue = self.Portfolio.TotalPortfolioValue
        self.CurrentPortValue = self.Portfolio.TotalPortfolioValue
        self.CurrentHoldValue = self.Portfolio.TotalHoldingsValue
        self.OpenHoldValue = self.Portfolio.TotalHoldingsValue 
        self.ClosingHoldValue = self.Portfolio.TotalHoldingsValue
        self.Gap = 0
        
        #Universe
        self.AddEquity("TVIX", Resolution.Daily).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("TSLA", Resolution.Daily)
        
        
        #Variables for TvixFunc
        self.vixEmaFast = self.EMA("TVIX", 2, Resolution.Daily)
        self.vixEmaSlow = self.EMA("TVIX", 16, Resolution.Daily)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
        
        #Variables for TSLAFunc
        self.TSLARsi = self.RSI("TSLA", 14, MovingAverageType.Simple, Resolution.Daily)
        self.TSLAMfi = self.MFI("TSLA", 14, Resolution.Daily)
        self.TSLAEmaFast = self.EMA("TSLA", 5, Resolution.Daily)
        self.TSLAEmaSlow = self.EMA("TSLA", 29, Resolution.Daily)
        self.TSLAEMADiff = IndicatorExtensions.Over(self.TSLAEmaFast,self.TSLAEmaSlow)

        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)       
        
        '''Schedule Functions Here'''
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", 1), self.CheckLiveTrading)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", 1), self.Charts)        
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", 5), self.TSLAFunc)        
        
        for x in range (20,390,20):
            self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", x), self.UpdatePortValues)
            
        for y in range (23,390,23):    
            self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", y), self.CheckDailyLosses) 
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("TSLA", 1), self.CapturePortfolioValue)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("TSLA", 1), self.ClearOpenOrders)  
        
        '''Set Warmup Here'''
        self.SetWarmup(TimeSpan.FromDays(30))

#OnData 
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.'''
        '''Arguments:
            data: Slice object keyed by symbol containing the stock data'''
        

#Charts

    def Charts(self):
        
        #Plot any relevant portfolio metrics
        self.Plot('Margin Remaining', 'Margin Remaining', self.Portfolio.MarginRemaining)
        self.Plot('Gap', 'Gap Magnitude', self.Gap)
        self.PlotIndicator('MFI', self.TSLAMfi)
        self.PlotIndicator('RSI', self.TSLARsi)
        self.PlotIndicator('EMADiff', self.TSLAEMADiff, self.EMADiff)
        
#AtClose
    def OnEndOfDay(self):
        
        self.Log("Trading Day Has Ended")
      
#MarginCallWarning                
    def OnMarginCallWarning(self):
        
        #Get a list of open orders to avoid margin issues
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Cancel any open orders.
        if len(self.OpenOrders)> 0:
            for x in self.OpenOrders:
                 self.Transactions.CancelOrder(x.Id) 

        #Rebalance to free up capital
        self.Log("Rebalacing due to tight margin conditions")                 
        self.OhShit()
        self.Log("WARNING: Day Start Portfolio Value: ${0} | Current Portfolio Value: ${1} | Loss: {2}%".format(
            
            round(self.ClosingPortValue,2), 
            round(self.Portfolio.TotalPortfolioValue,2), 
            round( ( (int(self.ClosingPortValue)/int(self.Portfolio.TotalPortfolioValue)) -1)*100,2), ) )        

#CheckLive        
    #Check connection at open and note the value gap
    def CheckLiveTrading(self):
        
        #Capture portfolio metrics at open. Verify live connection. Log previous close and overnight gap up/down
        self.OpenOrders = self.Transactions.GetOpenOrders()
        self.OpenPortValue = self.Portfolio.TotalPortfolioValue
        self.OpenHoldValue = self.Portfolio.TotalHoldingsValue
        self.Gap = round( ( ( ( int(self.OpenPortValue)/int(self.ClosingPortValue) ) - 1) * 100),2)
 
        #Perform actions based on overnight changes in portfolio value
        if self.Gap >= 5.00:
            self.Log("Huge gap up today! {0}%!".format(self.Gap))
            
        if self.Gap <= -2.25:
            self.Log("Huge gap down today! {0}%!".format(self.Gap))
            
        self.Log("Trading Live! || Yesterday's Closing Value: ${0}|| Opening Value: {1}% gap".format(self.ClosingPortValue, self.Gap))
        
        return
        
#CaputureValue
    #Capture the closing value of the portfolio and any open orders
    def CapturePortfolioValue(self):
        
        self.OpenOrders = self.Transactions.GetOpenOrders()
        self.ClosingPortValue = self.Portfolio.TotalPortfolioValue
        self.ClosingHoldValue = self.Portfolio.TotalHoldingsValue
        
        self.Log("End Of Day Portfolio Values Have Been Captured")
        
        return
        
#ClearOrders        
    #Clear open orders if there are 5 or more    
    def ClearOpenOrders(self):
        
            #Get a list of open orders to avoid margin issues
            self.OpenOrders = self.Transactions.GetOpenOrders()
            
            #Cancel any open orders.
            if len(self.OpenOrders)> 5:
                for x in self.OpenOrders:
                     self.Transactions.CancelOrder(x.Id)
                
                self.Log("Open Orders Have Been Closed.")   
                
            else:
                return
            
#Update Portfolio Values    
    def UpdatePortValues(self):
        
        if(self.IsMarketOpen("TSLA")):
                
            self.marginRemaining = self.Portfolio.MarginRemaining
            self.CurrentPortValue = self.Portfolio.TotalPortfolioValue
            self.CurrentHoldValue = self.Portfolio.TotalHoldingsValue
    
            self.Log("Portfolio Values Have Been Updated")            
            
#CheckLosses            
    #Check intraday losses and run a defensive function if a 5.6% drop is recognized at any time      
    def CheckDailyLosses(self):
        
        if(self.IsMarketOpen("TSLA")): 
            
            self.CurrentPerformance = round( ((float(self.CurrentPortValue)/float(self.ClosingPortValue))-1)*100,2)
            
            if (self.CurrentPortValue <= self.ClosingPortValue*0.95):
                    self.HighLosses()
                
            else: self.Log("Current Performance: {0}%".format(self.CurrentPerformance))
            
            return
        
#HighLosses        
    #Liquidate most holdings after a 5.6% drop from previous portfolio close value.
    def HighLosses(self):
            
        #Get a list of open orders to avoid margin issues
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Cancel any open orders.
        if len(self.OpenOrders)> 0:
            for x in self.OpenOrders:
                 self.Transactions.CancelOrder(x.Id)
        
        #Set portfolio to risk averse proportions and log important information
        self.OhShit()
        
        #Log important portfolio information when this function fires    
        self.Log("WARNING: Rebalancing due to excessive daily losses || Day Start Portfolio Value: ${0} || Current Portfolio Value: ${1} || Loss: {2}% || Gap at open: {3}%".format(
            
            round(self.ClosingPortValue,2), 
            round(self.Portfolio.TotalPortfolioValue,2), 
            round( ( (int(self.ClosingPortValue)/int(self.Portfolio.TotalPortfolioValue)) -1)*100,2),
            self.Gap) )
        
        #Reset the reference point to catch any further 5.6% decreases with the new holdings.   
        self.ClosingPortValue = self.Portfolio.TotalPortfolioValue 
        
        #If there were any open orders left this will log how many.  We cancelled them all, so this would be on the broker or connectivity
        if (len(self.OpenOrders)> 0):
            self.Log("Number of open orders: {0}".format( len(self.OpenOrders ))) 
        
        #Reset triggers so that function blocks can act freely at the next scheduled event    
        self.trigger = 0
        self.TSLATrigger = 0
       
        return
    
#Ohshit        
    def OhShit(self):
        
        #The portfolio value has decreased 5.6% in a single session or gapped up 10% or more. Rebalance to mitigate further losses or capture large gains

        if self.TSLARsi.Current.Value >= 65.1:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.80)
                
        elif 37 < self.TSLARsi.Current.Value < 65.1:                
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.33)
        
        else:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", -0.65)            
#TSLA       
    def TSLAFunc(self):
        
        self.Log("TSLA Function Has Fired.  || Relevant Metrics: EMADIff: {0}, TSLA MFI: {1}, TSLA RSI: {2}".format(
            round(self.TSLAEMADiff.Current.Value,3), round(self.TSLAMfi.Current.Value,3), round(self.TSLARsi.Current.Value,3)))
        
        #Refresh open orders
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Under these criteria go overweight.
        if (self.TSLAMfi.Current.Value < 17 or 0.86 <= self.TSLAEMADiff.Current.Value <= 0.91) and self.EMADiff.Current.Value < 1.572:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.80)
        
        #When TSLA momentum has peaked, heavily short.
        if self.TSLAMfi.Current.Value > 75 and self.TSLAEMADiff.Current.Value >= 1.1 and self.TSLARsi.Current.Value >= 78:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", -0.33)                
        
        #Under this criteria close all open positions.
        elif 65 >= self.TSLARsi.Current.Value >= 62.5 or (1.08 >=self.TSLAEMADiff.Current.Value >= 1.05):
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0) 
        
        #Under this criteria go long or rebalance accordingly.
        elif self.TSLAEMADiff.Current.Value >= 1.09:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.80)
                    
        elif self.TSLAEMADiff.Current.Value <= 0.795:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0)
            
    
        return