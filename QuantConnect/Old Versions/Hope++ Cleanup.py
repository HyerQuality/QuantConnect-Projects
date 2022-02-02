import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from System import *
from QuantConnect import *
from QuantConnect.Algorithm import *
from QuantConnect.Data.Market import TradeBar

class BasicTemplateAlgorithm(QCAlgorithm):
    '''High beta strategy'''

    def Initialize(self):
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialize.'''
        
        # Chart - Master Container for the Chart:
        stockPlot = Chart("Trade Plot")
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = Resolution.Daily
        self.UniverseSettings.Leverage = 2

        #Initial investment and backtest period
        self.SetStartDate(2013,9,1)     #Set Start Date
        self.SetEndDate(2019,1,24)       #Set End Date
        self.SetCash(450000)             #Set Strategy Cash

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
        
        #Universe
        self.AddEquity("SPY",  Resolution.Daily)
        self.AddEquity("TVIX", Resolution.Daily).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("TQQQ", Resolution.Daily)
        self.AddEquity("SPXL", Resolution.Daily)
        self.AddEquity("TSLA", Resolution.Daily)
        self.AddEquity("UVXY", Resolution.Daily)
        
        #Variables for SpyFunc
        self.emaFast = self.EMA("SPY", 8, Resolution.Daily)
        self.emaSlow = self.EMA("SPY", 29, Resolution.Daily)
        self.spyRsi = self.RSI("SPY", 14, MovingAverageType.Simple, Resolution.Daily)
        self.indexEMADiff = IndicatorExtensions.Over(self.emaFast, self.emaSlow)
        self.spyTrigger = 0

        #Plot any SPY inidcators
        self.PlotIndicator("SPY Indicator", True, self.indexEMADiff)
        self.PlotIndicator("SPY RSI", True, self.spyRsi)
        
        #Variables for TvixFunc
        self.vixEmaFast = self.EMA("TVIX", 2, Resolution.Daily)
        self.vixEmaSlow = self.EMA("TVIX", 16, Resolution.Daily)
        self.vixRsi = self.RSI("TVIX", 14, Resolution.Daily)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
        self.trigger = 0
        self.tvixSplitTrigger = 0
 
        #Plot any TVIX indicators.       
        self.PlotIndicator("TVIX Indicator", True, self.EMADiff)
        self.PlotIndicator("TVIX RSI", True, self.vixRsi)        
        
        #Variables for TslaFunc
        self.tslaRsi = self.RSI("TSLA", 14, MovingAverageType.Simple, Resolution.Daily)
        self.tslaMfi = self.MFI("TSLA", 14, Resolution.Daily)
        self.tslaEmaFast = self.EMA("TSLA", 5, Resolution.Daily)
        self.tslaEmaSlow = self.EMA("TSLA", 29, Resolution.Daily)
        self.tslaEMADiff = IndicatorExtensions.Over(self.tslaEmaFast,self.tslaEmaSlow)

        #Plot any TSLA indicators
        self.PlotIndicator("TSLA RSI", True, self.tslaRsi)
        self.PlotIndicator("TSLA MFI", True, self.tslaMfi)        
        self.PlotIndicator("TSLA Indicator", True, self.tslaEMADiff)
        
        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        
        '''Schedule Function Here'''
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.CheckLiveTrading)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 1), self.CapturePortfolioValue)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 1), self.ClearOpenOrders)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.CheckDailyLosses) 
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("TVIX", 3), self.TvixFunc)
        #self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("TVIX", 1), self.TvixSplitFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 7), self.SpyFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", 11), self.TslaFunc)        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TVIX", 13), self.TvixFunc)
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.Every(TimeSpan.FromMinutes(10)), self.CheckDailyLosses)        
        
        self.SetWarmup(30)

#OnData        
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.'''
        '''Arguments:
            data: Slice object keyed by symbol containing the stock data'''
        
        #Verify all indicators have warmed up before anything happens   
        if self.IsWarmingUp: return
    
        #Capture Portfolio Values   
        self.marginRemaining = self.Portfolio.MarginRemaining
        self.CurrentPortValue = self.Portfolio.TotalPortfolioValue
        self.CurrentHoldValue = self.Portfolio.TotalHoldingsValue
        
        #Plot any relevant portfolio metrics
        self.Plot("Margin Remaining", self.marginRemaining)
        self.Plot("Total Portfolio Value","Portfolio Value", self.Portfolio.TotalPortfolioValue)
        self.Plot("Holdings Value", self.Portfolio.TotalHoldingsValue)
        
        #Check for TVIX splits
        if data.Splits.ContainsKey("TVIX"):
            
            ## Log split information
            self.tvixSplit = data.Splits['TVIX']
            if self.tvixSplit.Type == 0:
                self.tvixSplitTrigger = 1
                self.Log('TVIX stock will split next trading day.')
            if self.tvixSplit.Type == 1:
                self.Log("Split type: {0}, Split factor: {1}, Reference price: {2}".format(self.tvixSplit.Type, self.tvixSplit.SplitFactor, self.tvixSplit.ReferencePrice))

#MarginCallWarning                
    def OnMarginCallWarning(self):
        
        #Get a list of open orders to avoid margin issues
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Cancel any open orders.
        if len(self.OpenOrders)> 0:
            for x in self.OpenOrders:
                 self.Transactions.CancelOrder(x.Id) 

        self.Log("Rebalacing due to tight margin conditions")                 
        self.MarginCall()
        self.Log("WARNING: Day Start Portfolio Value: ${0} | Current Portfolio Value: ${1} | Loss: {2}% | Gap at open: {3}%".format(
            
            round(self.ClosingPortValue,2), 
            round(self.Portfolio.TotalPortfolioValue,2), 
            round( ( (int(self.ClosingPortValue)/int(self.Portfolio.TotalPortfolioValue)) -1)*100,2),
            self.Gap) )        

#CheckLive        
    #Check connection at open and note the value gap
    def CheckLiveTrading(self):
        
        #Capture portfolio metrics at open. Verify live connection. Log previous close and overnight gap up/down
        self.OpenOrders = self.Transactions.GetOpenOrders()
        self.OpenPortValue = self.Portfolio.TotalPortfolioValue
        self.OpenHoldValue = self.Portfolio.TotalHoldingsValue
        self.Gap = round( ( ( ( int(self.OpenPortValue)/int(self.ClosingPortValue) ) - 1) * 100),2)
        
        #Perform actions based on overnight changes in portfolio value
        if self.Gap >= 10.00:
            self.Log("Huge gap up today! {0}%!".format(self.Gap))
            self.OhShit()        
            
        if self.Gap <= -4.25:
            self.Log("Huge gap down today! {0}%!".format(self.Gap))
            self.OhShit()             
            
        self.Log("Trading Live! || Yesterday's Closing Value: ${0}|| Opening Value: {1}% gap".format(self.ClosingPortValue, self.Gap))
        
#CaputureValue
    #Capture the closing value of the portfolio and cancel any open orders
    def CapturePortfolioValue(self):
        
        self.OpenOrders = self.Transactions.GetOpenOrders()
        self.ClosingPortValue = self.Portfolio.TotalPortfolioValue
        self.ClosingHoldValue = self.Portfolio.TotalHoldingsValue
        
#ClearOrders        
    #Clear open orders if there are 30 or more    
    def ClearOpenOrders(self):
        
            #Get a list of open orders to avoid margin issues
            self.OpenOrders = self.Transactions.GetOpenOrders()
            
            #Cancel any open orders.
            if len(self.OpenOrders)> 5:
                for x in self.OpenOrders:
                     self.Transactions.CancelOrder(x.Id)
                     
            else:
                return
            
#CheckLosses            
    #Check intraday losses and run defensive function if a 5.6% drop is recognized        
    def CheckDailyLosses(self):
        
        if (self.CurrentPortValue <= self.ClosingPortValue*0.944):
            self.HighLosses()
            
        else: return
    
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
        self.spyTrigger = 0
       
        return
    
        
#Ohshit        
    def OhShit(self):
        
        #The portfolio value has decreased 5.6% in a single session or gapped up 10% or more. Rebalance to mitigate further losses or capture large gains
        if self.Securities["TVIX"] not in self.OpenOrders:
            self.SetHoldings("TVIX", -0.15)
        if self.Securities["SPXL"] not in self.OpenOrders:
            self.SetHoldings("SPXL", 0.07)
        if self.Securities["UVXY"] not in self.OpenOrders:
            self.SetHoldings("UVXY", 0.25)
        if self.Securities["TSLA"] not in self.OpenOrders:
            self.SetHoldings("TSLA", 0.75)
            
            
#MarginCall
    def MarginCall(self):
        
        #The portfolio value has decreased 5.6% in a single session. Rebalance to mitigate further losses
        if self.Securities["TVIX"] not in self.OpenOrders:
            self.SetHoldings("TVIX", -0.15)    
        if self.Securities["SPXL"] not in self.OpenOrders:
            self.SetHoldings("SPXL", 0.07)  
        if self.Securities["UVXY"] not in self.OpenOrders:
            self.SetHoldings("UVXY", 0.25)
        if self.Securities["TSLA"] not in self.OpenOrders:
            self.SetHoldings("TSLA", 0.75)   
            
        
#SPY       
    def SpyFunc(self):    
        
        #Used to control leverage
        self.OpenOrders = self.Transactions.GetOpenOrders()

        #If these criteria are met reduce most index holdings and hedge for downward momentum
        if ( (self.indexEMADiff.Current.Value >= 1.02) and self.spyRsi.Current.Value >= 88):
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.05)
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", 0.30)                 
            
            self.spyTrigger = 2
        
        #If the indicator is equal or above this value lighten holdings. Trigger of zero means Block A or B can fire. 
        elif (self.indexEMADiff.Current.Value >= 1.02 and 88 > self.spyRsi.Current.Value > 78):
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.10)
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", 0.21)                 
            
            self.spyTrigger = 2
            
    #BLOCK A
        #While the indicator is in this range rebalance to this proportion. Sets trigger to 1 to avoid over-balancing. 
        elif  1.015 > self.indexEMADiff.Current.Value >= 1.01 and self.spyTrigger != 0 and self.spyRsi.Current.Value > 45:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.30)
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", 0)
                
            self.spyTrigger = 0
                
    #BLOCK B
        #While the indicator is in this range rebalance to this proportion. Sets trigger to 1 to avoid over-balancing. 
        elif  self.indexEMADiff.Current.Value <= 0.99 and self.spyTrigger != 1:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.175)
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", -0.04)                 
                
            self.spyTrigger = 1
            
    #BLOCK C
        #While the indicator is in this range frequently rebalance overweight. Trigger of zero lets Block B fire again to capture profits on the way up back up.
        elif ( (self.indexEMADiff.Current.Value <= 0.98) and (self.spyTrigger == 1) and (self.spyRsi.Current.Value <= 40) ):
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.35)
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", 0.12)            
            self.spyTrigger = 0
            
    #BLOCK D
        #While the indicator is in this range reduce any long volatilty hedges. Trigger of zero lets Block B fire again to capture profits on the way up back up.
        elif ( (self.spyRsi.Current.Value < 32) and (self.spyTrigger == 0) ):
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", 0)
                
            self.spyTrigger = 0        
    
        return
    
    
#TSLA       
    def TslaFunc(self):
        
        #Refresh open orders
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Under these criteria go overweight.
        if self.tslaMfi.Current.Value < 17 or self.tslaEMADiff.Current.Value <= 0.87:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0)
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.75)                    
        
        #Under this criteria close all open positions.
        elif self.tslaRsi.Current.Value >= 63:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0) 
        
        #Under this criteria go long or rebalance accordingly.
        elif self.tslaEMADiff.Current.Value >= 1.09:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.35)
                    
        return  
    
    
#TVIX
    def TvixFunc(self):
        
        #Get open orders. Used to prevent inappropriate use of leverage
        self.OpenOrders = self.Transactions.GetOpenOrders()

        #If the indicator value is within this range go max short        
        if ( (1.71 >= self.EMADiff.Current.Value >= 1.572) and self.vixRsi.Current.Value > 78):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.30)
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.40)
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", 0)                  
            
        #If the indicator value is within this range position is hedged and buying the SPY dip.
        elif ( (1.57 > self.EMADiff.Current.Value >= 0.972) and self.vixRsi.Current.Value > 40 ):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", 0.125)
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.30)  

        #If the indicator value is within this range go very short
        elif (0.947 > self.EMADiff.Current.Value > 0.77):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.32)
                
                self.trigger = 0                
                
        #If the indicator value is within this range slightly reduce short holdings      
        elif ( (0.77 >= self.EMADiff.Current.Value > 0.72) and self.vixRsi.Current.Value < 20 and self.trigger != 1):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.165)
                
        #If the indicator value is within this range initiate a tiny long vol position                     
        elif (self.vixRsi.Current.Value < 10 and self.trigger != 1):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", 0.05)
                
                self.trigger = 1
        #If RSI is this negative, rebalance long volatility position        
        elif (self.vixRsi.Current.Value < -20 and self.trigger == 1):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", 0.05)
                
                self.trigger = 1                
         
        return
    
#TVIXSplit
    def TvixSplitFunc(self):
        
        #If TVIX is going to split the next day, reduce holdings        
        if self.tvixSplitTrigger != 0:
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.10)
                self.tvixSplitTrigger = 0
        else:
            return