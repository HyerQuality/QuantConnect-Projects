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

class ThetaArb(QCAlgorithm):
    '''Day trades.  Buy and hold leveraged SPY.  Fluctuate risk using volatitly ETNs. Tesla discriminately used as a Beta hedge.'''

    def Initialize(self):
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialize.'''

        # Chart - Master Containers for the Charts:
        stockPlot_1 = Chart('RSI')
        stockPlot_2 = Chart('MFI')
        stockPlot_3 = Chart('EMADiff')
        stockPlot_4 = Chart('Margin Remaining')
        stockPlot_5 = Chart('Triggers')
        stockPlot_6 = Chart('VIX Close')
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = Resolution.Daily
        self.UniverseSettings.Leverage = 2

        #Initial investment and backtest period
        self.SetStartDate(2011,11,1)                                 #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1))       #Set End Date
        self.SetCash(400000)                                      #Set Strategy Cash

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
        self.AddData(Vix, "VIX", Resolution.Daily)
        
        #Variables for SpyFunc
        self.emaFast = self.EMA("SPY", 8, Resolution.Daily)
        self.emaSlow = self.EMA("SPY", 29, Resolution.Daily)
        self.spyRsi = self.RSI("SPY", 14, MovingAverageType.Simple, Resolution.Daily)
        self.indexEMADiff = IndicatorExtensions.Over(self.emaFast, self.emaSlow)
        self.spyTrigger = 0
        
        #Variables for TvixFunc
        self.vixEmaFast = self.EMA("TVIX", 2, Resolution.Daily)
        self.vixEmaSlow = self.EMA("TVIX", 16, Resolution.Daily)
        self.vixRsi = self.RSI("TVIX", 14, Resolution.Daily)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
        self.trigger = 0
        self.tvixSplitTrigger = 0
        self.MaxProportion = 0.32
        
        #Variables for TslaFunc
        self.tslaRsi = self.RSI("TSLA", 14, MovingAverageType.Simple, Resolution.Daily)
        self.tslaMfi = self.MFI("TSLA", 14, Resolution.Daily)
        self.tslaEmaFast = self.EMA("TSLA", 5, Resolution.Daily)
        self.tslaEmaSlow = self.EMA("TSLA", 29, Resolution.Daily)
        self.tslaEMADiff = IndicatorExtensions.Over(self.tslaEmaFast,self.tslaEmaSlow)

        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        
        '''Schedule Function Here'''
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.CheckLiveTrading)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.Charts)        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.CheckDailyLosses)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.UpdatePortValues)
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 7), self.SpyFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", 11), self.TslaFunc)        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TVIX", 13), self.TvixFunc)
        
        for x in range (97,390,97):
            self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", x), self.UpdatePortValues)
            
        for y in range (98,390,98):    
            self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", y), self.CheckDailyLosses) 
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("TVIX", 3), self.TvixFunc)        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 1), self.CapturePortfolioValue)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 1), self.ClearOpenOrders)        

        '''Set Warmup Here'''
        
        self.SetWarmup(TimeSpan.FromDays(30))

#OnData        
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.'''
        '''Arguments:
            data: Slice object keyed by symbol containing the stock data'''
        
        #Verify all indicators have warmed up, the VIX data has loaded, and the market is open before anything happens
        if not data.ContainsKey("VIX"): return
        if (not self.IsMarketOpen("SPY")): return
    
        self.ClosingVix = data["VIX"].Close
        self.MaxProportion = (round(np.minimum(float(100/((37/self.ClosingVix) +1))/100, 0.32),0))       
            
#Charts

    def Charts(self):
        
        #Convert plot values to numbers
        
        #Plot any relevant portfolio metrics
        self.Plot('Margin Remaining', 'Margin Remaining', self.marginRemaining)
        self.Plot('Triggers', 'SPY Trigger', self.spyTrigger)
        self.Plot('Triggers', 'TVIX Trigger', self.trigger)        
        self.PlotIndicator('RSI', self.tslaRsi, self.vixRsi, self.spyRsi)
        self.PlotIndicator('EMADiff', self.tslaEMADiff, self.EMADiff, self.indexEMADiff)
        self.PlotIndicator('MFI', self.tslaMfi)
        
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
        self.MarginCall()
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
        if self.Gap >= 10.00:
            self.Log("Huge gap up today! {0}%!".format(self.Gap))
            self.OhShit()        
            
        if self.Gap <= -4.25:
            self.Log("Huge gap down today! {0}%!".format(self.Gap))
            self.OhShit()             
            
        self.Log("Trading Live! || Yesterday's Closing Value: ${0}|| Opening Value: {1}% gap".format(self.ClosingPortValue, self.Gap))
        
        return
        
#CaputureValue
    #Capture the closing value of the portfolio and cancel any open orders
    def CapturePortfolioValue(self):
        
        self.OpenOrders = self.Transactions.GetOpenOrders()
        self.ClosingPortValue = self.Portfolio.TotalPortfolioValue
        self.ClosingHoldValue = self.Portfolio.TotalHoldingsValue
        
        self.Log("End Of Day Portfolio Values Have Been Captured")
        
        return
        
#ClearOrders        
    #Clear open orders if there are 30 or more    
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
        
        if(self.IsMarketOpen("SPY")):
                
            self.marginRemaining = self.Portfolio.MarginRemaining
            self.CurrentPortValue = self.Portfolio.TotalPortfolioValue
            self.CurrentHoldValue = self.Portfolio.TotalHoldingsValue
    
            self.Log("Portfolio Values Have Been Updated")            
            
#CheckLosses            
    #Check intraday losses and run defensive function if a 5.6% drop is recognized        
    def CheckDailyLosses(self):
        
        if(self.IsMarketOpen("SPY")): 
            
            self.CurrentPerformance = round( ((float(self.CurrentPortValue)/float(self.ClosingPortValue))-1)*100,2)
            
            if (self.CurrentPortValue <= self.ClosingPortValue*0.944):
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
        
        #The portfolio has received a margin call. Rebalance to free up capital
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
        
        self.Log("SPY Function Has Fired.  || Relevant Metrics: EMADIff: {0}, SPY Trigger: {1}, SPY RSI: {2}".format(
            round(self.indexEMADiff.Current.Value,3), self.spyTrigger, round(self.spyRsi.Current.Value),3))
        
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
                self.SetHoldings("SPXL", 0.50)
            if self.Securities["UVXY"] not in self.OpenOrders:
                self.SetHoldings("UVXY", 0.19)            
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
        
        self.Log("TSLA Function Has Fired.  || Relevant Metrics: EMADIff: {0}, TSLA MFI: {1}, TSLA RSI: {2}".format(
            round(self.tslaEMADiff.Current.Value,3), round(self.tslaMfi.Current.Value,3), round(self.tslaRsi.Current.Value,3)))
        
        #Refresh open orders
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Under these criteria go overweight.
        if self.tslaMfi.Current.Value < 17 or 0.73 <= self.tslaEMADiff.Current.Value <= 0.87:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0)
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.80)                    
        
        #Under this criteria close all open positions.
        elif self.tslaRsi.Current.Value >= 63:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0) 
        
        #Under this criteria go long or rebalance accordingly.
        elif self.tslaEMADiff.Current.Value >= 1.09:
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0.33)
                    
        elif self.tslaEMADiff.Current.Value <= 0.725:
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0)
            if self.Securities["TSLA"] not in self.OpenOrders:
                self.SetHoldings("TSLA", 0)           
    
        return  
    
#TVIX
    def TvixFunc(self):
        
        self.Log("TVIX Function Has Fired.  || Relevant Metrics: EMADIff: {0}, TVIX Trigger: {1}, TVIX RSI: {2}, Max Proportion: {3}".format(
            round(self.EMADiff.Current.Value,3), self.trigger, round(self.vixRsi.Current.Value,3), self.MaxProportion))
        
        #Get open orders. Used to prevent inappropriate use of leverage
        self.OpenOrders = self.Transactions.GetOpenOrders()

        #If the indicator value is within this range go max short        
        if ( (1.71 >= self.EMADiff.Current.Value >= 1.572) and self.vixRsi.Current.Value > 78):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -0.41)
            if self.Securities["SPXL"] not in self.OpenOrders:
                self.SetHoldings("SPXL", 0.50)
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
                self.SetHoldings("TVIX", -self.MaxProportion)
                
                self.trigger = 0                
                
        #If the indicator value is within this range slightly reduce short holdings      
        elif ( (0.77 >= self.EMADiff.Current.Value > 0.72) and self.vixRsi.Current.Value < 20 and self.trigger != 1):
            if self.Securities["TVIX"] not in self.OpenOrders:
                self.SetHoldings("TVIX", -(self.MaxProportion*0.05))
                
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
    
class Vix(PythonData):
    '''Custom Data Type'''

    def GetSource(self, config, date, isLiveMode):
        #if isLiveMode:
        return SubscriptionDataSource("http://www.cboe.com/publish/scheduledtask/mktdata/datahouse/vixcurrent.csv", SubscriptionTransportMedium.RemoteFile);

    def Reader(self, config, line, date, isLiveMode):
        
        # New VIX object
        index = Vix()
        index.Symbol = config.Symbol   
        
        #if isLiveMode:
        if not (line.strip() and line[0].isdigit()): return None


        try:
            # Example File Format:
            # Date,       Open       High        Low       Close     Volume      Turnover
            # 1/1/2008  7792.9    7799.9     7722.65    7748.7    116534670    6107.78
            data = line.split(',')
            index.Time = datetime.strptime(data[0], "%m/%d/%Y")
            index.Value = data[4]
            index["Open"] = float(data[1])
            index["High"] = float(data[2])
            index["Low"] = float(data[3])
            index["Close"] = float(data[4])


        except ValueError:
                # Do nothing
                return None

        return index