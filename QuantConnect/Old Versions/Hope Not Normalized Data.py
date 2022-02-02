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
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialized.'''
        
        # Chart - Master Container for the Chart:
        stockPlot = Chart("Trade Plot")
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = Resolution.Daily
        self.UniverseSettings.Leverage = 2

        #Initial investment and backtest period
        self.SetStartDate(2011,11,1)     #Set Start Date
        self.SetEndDate(2019,1,22)       #Set End Date
        self.SetCash(60000)             #Set Strategy Cash

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
        self.AddEquity("TVIX", Resolution.Daily)
        self.AddEquity("TQQQ", Resolution.Daily)
        self.AddEquity("SPXL", Resolution.Daily)
        self.AddEquity("TSLA", Resolution.Daily)
        
        
        #Variables for SpyFunc
        self.emaFast = self.EMA("SPY", 8, Resolution.Daily)
        self.emaSlow = self.EMA("SPY", 29, Resolution.Daily)
        self.spyRsi = self.RSI("SPY", 14, MovingAverageType.Simple, Resolution.Daily)
        self.indexEMADiff = IndicatorExtensions.Over(self.emaFast, self.emaSlow)
        self.spyTrigger = 0

        #Plot any SPY inidcators
        self.PlotIndicator("SPY Indicator", True, self.indexEMADiff)
        
        #Variables for TvixFunc
        self.vixEmaFast = self.EMA("TVIX", 2, Resolution.Daily)
        self.vixEmaSlow = self.EMA("TVIX", 16, Resolution.Daily)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
        self.trigger = 0
 
        #Plot any TVIX indicators.       
        self.PlotIndicator("VIX Indicator", True, self.EMADiff)
        
        #Variables for TslaFunc
        self.tslaRsi = self.RSI("TSLA", 14, MovingAverageType.Simple, Resolution.Daily)
        self.tslaMfi = self.MFI("TSLA", 14, Resolution.Daily)
        self.tslaEmaFast = self.EMA("TSLA", 5, Resolution.Daily)
        self.tslaEmaSlow = self.EMA("TSLA", 29, Resolution.Daily)
        self.tslaEMADiff = IndicatorExtensions.Over(self.tslaEmaFast,self.tslaEmaSlow)

        #Plot any TSLA indicators
        self.PlotIndicator("TSLA RSI", True, self.tslaRsi)
        self.PlotIndicator("TSLA Indicator", True, self.tslaEMADiff)
        
        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        
        '''Schedule Function Here'''
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.CheckLiveTrading)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 1), self.CapturePortfolioValue)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 1), self.ClearOpenOrders)
        #self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 2), self.CheckDailyLosses) 
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("TVIX", 3), self.TvixFunc)          
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 7), self.SpyFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", 11), self.TslaFunc)        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TVIX", 13), self.TvixFunc)
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.Every(TimeSpan.FromMinutes(10)), self.CheckDailyLosses)        
        
        self.SetWarmup(30)
        
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
            
            round(self.ClosingPortValue,2), round(self.Portfolio.TotalPortfolioValue,2), 
            round( ( (int(self.ClosingPortValue)/int(self.Portfolio.TotalPortfolioValue)) -1)*100,2),
            self.Gap) )        
        
    #Check connection at open and note the value gap
    def CheckLiveTrading(self):
        
        #Capture portfolio metrics at open. Verify live connection. Log previous close and overnight gap up/down
        
        self.OpenOrders = self.Transactions.GetOpenOrders()
        self.OpenPortValue = self.Portfolio.TotalPortfolioValue
        self.OpenHoldValue = self.Portfolio.TotalHoldingsValue
        self.Gap = round( ( ( ( int(self.OpenPortValue)/int(self.ClosingPortValue) ) - 1) * 100),2)
        ##########self.Log("Trading Live! || Yesterday's Closing Value: ${0}".format(self.ClosingPortValue))
        ##########self.Log("Opening Value: {0}% gap".format(round( ( ( ( int(self.OpenPortValue)/int(self.ClosingPortValue) ) - 1) * 100),2) ) )
        

    #Capture the closing value of the portfolio and cancel any open orders
    def CapturePortfolioValue(self):
        
        self.OpenOrders = self.Transactions.GetOpenOrders()
        self.ClosingPortValue = self.Portfolio.TotalPortfolioValue
        self.ClosingHoldValue = self.Portfolio.TotalHoldingsValue
        
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
    def CheckDailyLosses(self):
        
        if (self.CurrentPortValue <= self.ClosingPortValue*0.925):
            self.Log("Rebalancing due to excessive daily losses")            
            self.HighLosses()
            
        else: return
        
    #Liquidate most holdings after a 7.5% drop from previous portfolio close value.
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
        self.Log("WARNING: Day Start Portfolio Value: ${0} | Current Portfolio Value: ${1} | Loss: {2}% | Gap at open: {3}%".format(
            
            round(self.ClosingPortValue,2), round(self.Portfolio.TotalPortfolioValue,2), 
            round( ( (int(self.ClosingPortValue)/int(self.Portfolio.TotalPortfolioValue)) -1)*100,2),
            self.Gap) )
        
        #Reset the reference point to catch any further 7.5% decreases with the new holdings.   
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
        
        #The portfolio value has decreased 7.5% in a single session. Rebalance to this to mitigate further losses
        if self.Securities["TVIX"] not in self.OpenOrders:
            self.SetHoldings("TVIX", -0.18)     #returns are greater when this is -0.176
        if self.Securities["SPXL"] not in self.OpenOrders:
            self.SetHoldings("SPXL", 0.13)      #reference proportion. SPY outperforms QQQ in 2018. Dont short SPY. 0.26 > 0.29
        if self.Securities["TQQQ"] not in self.OpenOrders:    
            self.SetHoldings("TQQQ", -0.11)     #yields better results when miniscully under weight [SPXL 0.13] [TQQQ -0.11]           
        if self.Securities["TSLA"] not in self.OpenOrders:
            self.SetHoldings("TSLA", 0.75)      #should be positive. Better results @ 0.75. Dont exceed for margin purposes        
#MarginCall
    def MarginCall(self):
        
        #The portfolio value has decreased 7.5% in a single session. Rebalance to this to mitigate further losses
        if self.Securities["TVIX"] not in self.OpenOrders:
            self.SetHoldings("TVIX", -0.18)     #returns are greater when this is -0.176
        if self.Securities["SPXL"] not in self.OpenOrders:
            self.SetHoldings("SPXL", 0.13)      #reference proportion. SPY outperforms QQQ in 2018. Dont short SPY. 0.26 > 0.29
        if self.Securities["TQQQ"] not in self.OpenOrders:    
            self.SetHoldings("TQQQ", -0.11)     #yields better results when miniscully under weight [SPXL 0.13] [TQQQ -0.11]           
        if self.Securities["TSLA"] not in self.OpenOrders:
            self.SetHoldings("TSLA", 0.75)      #should be positive. Better results @ 0.75. Dont exceed for margin purposes 
        
#INDEXS       
    def SpyFunc(self):    
        
        #Used to control leverage
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #If the indicator is equal or above this value lighten holdings. Trigger of zero means Block A or B can fire. 
        #Also, run TvixFunc more often during this range
        if self.indexEMADiff.Current.Value >= 1.02:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.15)
            if self.Securities["TQQQ"] not in self.OpenOrders:    
                self.SetHoldings("TQQQ", -0.15)
            self.TvixFunc()                   
            
            self.spyTrigger = 0
            
    #BLOCK A
        #While the indicator is in this range rebalance to this proportion. Sets trigger to 1 to avoid over-balancing. 
        elif  self.indexEMADiff.Current.Value <= 0.995 and self.spyTrigger != 1:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.25)
            if self.Securities["TQQQ"] not in self.OpenOrders:    
                self.SetHoldings("TQQQ", 0.125)
                
            self.spyTrigger = 1
            
    #BLOCK B
        #While the indicator is in this range frequently rebalance overweight. Trigger of zero lets Block A fire again to capture profits on the way up back up.
        elif self.indexEMADiff.Current.Value <= 0.980 and self.spyTrigger == 1:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.35)
            if self.Securities["TQQQ"] not in self.OpenOrders:    
                self.SetHoldings("TQQQ", 0.20)                   

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
        elif self.tslaRsi.Current.Value >= 62:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0) 
        
        #Under this criteria go long or rebalance accordingly.
        elif self.tslaEMADiff.Current.Value >= 1.11:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.40)
                    
        return  
    
#TVIX     
    def TvixFunc(self):
        
        #Get open orders. Used to prevent inappropriate use of leverage
        self.OpenOrders = self.Transactions.GetOpenOrders()

        #If the indicator value is within this range go max short        
        if (1.71 >= self.EMADiff.Current.Value >= 1.572):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.40)
            
        #If the indicator value is within this range position is hedged and buying the SPY dip.
        elif ( (1.57 > self.EMADiff.Current.Value >= 0.972) ):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", 0.30)
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.45) 

        #If the indicator value is within this range go very short
        elif (0.947 > self.EMADiff.Current.Value > 0.77):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.35)
                
        #If the indicator value is within this range slightly reduce short holdings      
        elif (0.77 >= self.EMADiff.Current.Value > 0.72):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.27)
                
        #If the indicator value is within this range significantly reduce short holdings                      
        elif (0.72 >= self.EMADiff.Current.Value):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.17)                
         
        return
    
    
#NOTES    
    '''    elif (0.915 < self.EMADiff.Current.Value <= 0.945 and 1 <= self.trigger <= 2):
            self.trigger = 2
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.55)
            self.Log(self.trigger)
            #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
            
        elif (0.891 < self.EMADiff.Current.Value <= 0.915 and 2 <= self.trigger <= 3):    
            self.trigger = 3
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.225)
            self.Log(self.trigger)
            #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
                            
        elif (self.EMADiff.Current.Value <= 0.891 and 2 <= self.trigger <= 3):
            self.trigger = 3
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", 0)
            self.Log(self.trigger)
            #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
            
        elif (self.EMADiff.Current.Value <= 0.6 and 2 <= self.trigger <= 3):   
            self.trigger = 2
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", 0.3)
            self.Log(self.trigger)
            #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
    '''