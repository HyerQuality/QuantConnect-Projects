import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from System import *
from QuantConnect import *
from QuantConnect.Algorithm import *
from QuantConnect.Data.Market import TradeBar

### <summary>
### Basic template algorithm simply initializes the date range and cash. This is a skeleton
### framework you can use for designing an algorithm.
### </summary>
class BasicTemplateAlgorithm(QCAlgorithm):
    '''Basic template algorithm simply initializes the date range and cash'''

    def Initialize(self):
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialized.'''
        
        # Chart - Master Container for the Chart:
        stockPlot = Chart("Trade Plot")
        
        self.UniverseSettings.Resolution = Resolution.Daily
        self.UniverseSettings.Leverage = 2

        self.SetStartDate(2011,11,1)     #Set Start Date
        self.SetEndDate(2019,1,15)      #Set End Date
        self.SetCash(475000)             #Set Strategy Cash
        
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        
        #Capture initial investment
        self.portValue = self.Portfolio.TotalHoldingsValue
        self.portValue0 = 0
        
        #Stocks we're looking at
        self.AddEquity("SPY",  Resolution.Daily)
        self.AddEquity("TVIX", Resolution.Daily).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("TQQQ", Resolution.Daily).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("SPXL", Resolution.Daily).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("TSLA", Resolution.Daily)
        #self.AddEquity("UVXY", Resolution.Daily).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("AAPL",  Resolution.Daily)
        
        #Set price type.  Split adjusted or price @ date (raw)
        #self.Securities["TVIX"].SetDataNormalizationMode(DataNormalizationMode.SplitAdjusted)
        #self.Securities["SPXL"].SetDataNormalizationMode(DataNormalizationMode.Raw)
        #self.Securities["TQQQ"].SetDataNormalizationMode(DataNormalizationMode.Raw)
        #self.Securities["TSLA"].SetDataNormalizationMode(DataNormalizationMode.Raw)
        
        #Variables for SpyFunc
        self.emaFast = self.EMA("SPY", 8, Resolution.Daily)
        self.emaSlow = self.EMA("SPY", 29, Resolution.Daily)
        self.spyRsi = self.RSI("SPY", 14, MovingAverageType.Simple, Resolution.Daily)
        self.indexEMADiff = IndicatorExtensions.Over(self.emaFast, self.emaSlow)
        self.spyTrigger = 0
        
        #self.Plot("SPYIndicators", self.emaFast, self.emaSlow)

        
        #Variables for TvixFunc

        self.vixEmaFast = self.EMA("TVIX", 2, Resolution.Daily)
        self.vixEmaSlow = self.EMA("TVIX", 16, Resolution.Daily)
        self.vixRsi = self.RSI("TVIX", 14, MovingAverageType.Simple, Resolution.Daily)
        self.vixRoc = self.ROC("TVIX", 10, Resolution.Daily)
        self.vixATR = self.ATR("TVIX", 14, Resolution.Daily)        
        self.vixSpyEmaFast = self.EMA("SPY", 2, Resolution.Daily)
        self.vixSpyEmaSlow = self.EMA("SPY", 20, Resolution.Daily)
        self.vixSpyRoc = self.ROC("SPY", 5, Resolution.Daily, Field.Volume)
        self.vixSpyMfi = self.MFI("SPY", 14, Resolution.Daily)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
        self.spyEMADiff = IndicatorExtensions.Over(self.vixSpyEmaFast,self.vixSpyEmaSlow)
        self.trigger = 0
        
        self.volumeWindow = RollingWindow[TradeBar](5)
        
        #self.PlotIndicator("EMADiff", True, self.EMADiff)
        #self.PlotIndicator("SpyRoc", True, self.vixSpyRoc)
        #self.PlotIndicator("EMACross", True, self.vixEmaSlow, self.vixEmaFast)
        #self.PlotIndicator("SpyEMACross", True, self.emaFast, self.emaSlow)
        #self.PlotIndicator("SpyEMADiff", True, self.indexEMADiff)
        
        #Variables for TslaFunc
        
        self.tslaRsi = self.RSI("TSLA", 14, MovingAverageType.Simple, Resolution.Daily)
        self.tslaMfi = self.MFI("TSLA", 14, Resolution.Daily)
        self.tslaEmaFast = self.EMA("TSLA", 5, Resolution.Daily)
        self.tslaEmaSlow = self.EMA("TSLA", 29, Resolution.Daily)
        self.tslaEMADiff = IndicatorExtensions.Over(self.tslaEmaFast,self.tslaEmaSlow)
        
        #self.PlotIndicator("TSLA RSI", True, self.tslaRsi)
        #self.PlotIndicator("TSLA MFI", True, self.tslaMfi)
        #self.PlotIndicator("TSLA EMA Diff", True, self.tslaEMADiff)  
        
        
        #Variables for AaplFunc
        
        self.aaplRsi = self.RSI("AAPL", 14, MovingAverageType.Simple, Resolution.Daily)
        self.aaplMfi = self.MFI("AAPL", 14, Resolution.Daily)
        self.aaplEmaFast = self.EMA("AAPL", 5, Resolution.Daily)
        self.aaplEmaSlow = self.EMA("AAPL", 29, Resolution.Daily)
        self.aaplEMADiff = IndicatorExtensions.Over(self.aaplEmaFast,self.aaplEmaSlow)
        
        self.PlotIndicator("AAPL RSI", True, self.aaplRsi)
        self.PlotIndicator("AAPL MFI", True, self.aaplMfi)
        self.PlotIndicator("AAPL EMA Diff", True, self.aaplEMADiff)        
        
        #Generate rolling windows to capture closing prices etc.
        #self.tvixCloseWindow = RollingWindow[TradeBar](4)
        
        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        #self.Securities.MarginModel =  PatternDayTradingMarginModel()
        
        '''Schedule Function Here'''
        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.CheckLiveTrading)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 2), self.CapturePortfolioValue)        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.Every(timedelta(minutes=10)), self.LiquidateUnrealizedLosses)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TVIX", 15), self.TvixFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TVIX", 388), self.TvixFunc)        
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 7), self.SpyFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("TSLA", 11), self.TslaFunc)
        #self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 15), self.AaplFunc)
        
        self.SetWarmup(30)
        
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.'''
        '''Arguments:
            data: Slice object keyed by symbol containing the stock data'''
            
        #data.Splits["TVIX"].SplitFactor
        #self.tvixCloseWindow.Add(data["TVIX"])
        #if not (data.ContainsKey("SPY")): return
        #self.volumeWindow.Add( data["SPY"] )
        #if not (self.volumeWindow.IsReady) or float(self.volumeWindow[4].Volume) == 0 : return
        #self.vRoc = (float(self.volumeWindow[0].Volume)-float(self.volumeWindow[4].Volume))/float(self.volumeWindow[4].Volume)
        self.marginRemaining = self.Portfolio.MarginRemaining
        #self.Plot("vRoc", self.vRoc*100)
        #self.Plot("indexEMADiff", self.indexEMADiff)
        self.Plot("Margin Remaining", self.marginRemaining)
        #self.Plot("SPYIndicators", self.emaFast, self.emaSlow)
        #self.Plot("TVIXIndicators", self.vixEmaFast, self.vixEmaSlow)
        #self.Plot("Held Quantity", self.Portfolio["TVIX"].Quantity)
        #self.Plot("Trigger", self.trigger)        
        #self.Plot("Ratio", self.EMADiff.Current.Value)
#        if self.portValue > 0:
#            if self.Portfolio.TotalPortfolioValue < 0.78*self.portValue:
#                self.SetHoldings("TVIX", 0)


    def CheckLiveTrading(self):
        if (self.LiveMode and self.vixSpyEmaFast.IsReady and self.vixSpyEmaSlow.IsReady and self.spyRsi.IsReady and self.spyEMADiff.IsReady and self.vixSpyRoc.IsReady
            and self.vixSpyMfi.IsReady and self.indexEMADiff.IsReady #SPY Indicators
            
            and self.vixRsi.IsReady and self.vixRoc.IsReady and self.vixEmaFast.IsReady and self.vixEmaSlow.IsReady and self.EMADiff.IsReady): #VIX Indicators
                
            self.Log("Trading Live!")

    def CapturePortfolioValue(self):
        
        self.portValue0 = self.portValue
        self.portValue = self.Portfolio.TotalPortfolioValue
        #self.Log("Day Start Portfolio Value: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity
        
    #Liquidate everything and long TVIX if daily losses approach 15% of initial invested capital
    def LiquidateUnrealizedLosses(self):
        
        openOrders = self.Transactions.GetOpenOrders()
        
        if self.Portfolio.Invested:
            
            if float(self.Portfolio.TotalPortfolioValue) <= float(self.portValue) * 0.925:
                
                self.trigger = 0
                #self.Liquidate()
                
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", -0.18) #returns are greater when this is -0.176
                if self.Securities["SPXL"] not in openOrders:
                    self.SetHoldings("SPXL", 0.13) #reference proportion. SPY outperforms QQQ in 2018. Dont short SPY. 0.26 > 0.29
                if self.Securities["TQQQ"] not in openOrders:    
                    self.SetHoldings("TQQQ", -0.11) #yields better results when miniscully under weight [SPXL 0.13] [TQQQ -0.11]           
                if self.Securities["TSLA"] not in openOrders:
                    self.SetHoldings("TSLA", 0.75) #should be positive. Better results @ 0.75. Dont exceed for margin purposes
                self.Log("Day Start Portfolio Value: {0} | Current Portfolio Value: {1}".format(self.portValue, self.Portfolio.TotalPortfolioValue))
                self.portValue = self.Portfolio.TotalPortfolioValue   
               
                return
            
    def SpyFunc(self):    
        
        #Used to control leverage
        openOrders = self.Transactions.GetOpenOrders()
        
        if (self.vixSpyEmaFast.IsReady and self.vixSpyEmaSlow.IsReady and self.spyRsi.IsReady and self.spyEMADiff.IsReady and self.vixSpyRoc.IsReady
            and self.vixSpyMfi.IsReady and self.indexEMADiff.IsReady #SPY Indicators
            
            and self.vixRsi.IsReady and self.vixRoc.IsReady and self.vixEmaFast.IsReady and self.vixEmaSlow.IsReady and self.EMADiff.IsReady): #Vix Indicators
            
            if self.indexEMADiff.Current.Value >= 1.02:
                if self.Securities["SPXL"] not in openOrders:
                    self.SetHoldings("SPXL", -0.30)
                if self.Securities["TQQQ"] not in openOrders:    
                    self.SetHoldings("TQQQ", -0.17)
                self.TvixFunc()                   
                
                self.spyTrigger = 0
                    
            elif self.indexEMADiff.Current.Value <= 0.995 and self.spyTrigger != 1:
                if self.Securities["SPXL"] not in openOrders:
                    self.SetHoldings("SPXL", 0.25)
                if self.Securities["TQQQ"] not in openOrders:    
                    self.SetHoldings("TQQQ", 0.125)
                    
                self.spyTrigger = 1
                
            elif self.indexEMADiff.Current.Value <= 0.980 and self.spyTrigger == 1:
                if self.Securities["SPXL"] not in openOrders:
                    self.SetHoldings("SPXL", 0.35)
                if self.Securities["TQQQ"] not in openOrders:    
                    self.SetHoldings("TQQQ", 0.20)                   

                self.spyTrigger = 2                
        
            return
        
    def TslaFunc(self):
        
        openOrders = self.Transactions.GetOpenOrders()
        
        if self.tslaRsi.IsReady and self.tslaMfi.IsReady and self.tslaEMADiff.IsReady:
            
            if self.tslaMfi.Current.Value < 17 or self.tslaEMADiff.Current.Value <= 0.87:
                #if self.Securities["TVIX"] not in openOrders:
                    #self.SetHoldings("TVIX", -0.35)                    
                if self.Securities["SPXL"] not in openOrders:
                    self.SetHoldings("SPXL", 0)
                if self.Securities["TSLA"] not in openOrders:
                    self.SetHoldings("TSLA", 0.75)                      
        
            elif self.tslaRsi.Current.Value >= 62:
                if self.Securities["TSLA"] not in openOrders:
                    self.SetHoldings("TSLA", 0) 
            
            elif self.tslaEMADiff.Current.Value >= 1.11:
                #if self.Securities["TVIX"] not in openOrders:
                    #self.SetHoldings("TVIX", -0.33)                    
                #if self.Securities["SPXL"] not in openOrders:
                    #self.SetHoldings("SPXL", 0.37)   
                if self.Securities["TSLA"] not in openOrders:
                    self.SetHoldings("TSLA", 0.40)
                    
        return    
     
     
    def AaplFunc(self):
        
        openOrders = self.Transactions.GetOpenOrders()  
        
        #SELL COVERED CALLS DURING DRAWNDOWN PERIODS
        if self.aaplRsi.IsReady and self.aaplMfi.IsReady and self.aaplEMADiff.IsReady:
            
            if self.aaplEMADiff.Current.Value < 0.947:
                if self.Securities["AAPL"] not in openOrders:
                    self.SetHoldings("AAPL", 0.22) 
            
            elif self.aaplEMADiff.Current.Value >= 1.035:
                if self.Securities["AAPL"] not in openOrders:
                    self.SetHoldings("AAPL", 0.035)         
        return
    
    
    def TvixFunc(self):
        
        #Get open orders. Used to prevent inappropriate use of leverage
        openOrders = self.Transactions.GetOpenOrders()

        #Don't run this function unless every indicator is built and ready
        if (self.vixSpyEmaFast.IsReady and self.vixSpyEmaSlow.IsReady and self.spyRsi.IsReady and self.spyEMADiff.IsReady and self.vixSpyRoc.IsReady
            and self.vixSpyMfi.IsReady and self.indexEMADiff.IsReady #SPY Indicators
            
            and self.vixRsi.IsReady and self.vixRoc.IsReady and self.vixEmaFast.IsReady and self.vixEmaSlow.IsReady and self.EMADiff.IsReady): #Vix Indicators

            #If the current EMA ratio is 3 standard deviations above the mean, MAX SHORT            
            if (1.71 >= self.EMADiff.Current.Value >= 1.572):
                self.trigger = 1
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", -0.40)
                #self.Log(self.trigger) 
                
            #If the EMA ratio is 1 - 3 standard deviations above the mean, 2 standard deviations below the mean, or the SPY vRoc is above a threshold  liquidate. 
            if ( (1.57 > self.EMADiff.Current.Value >= 0.972) or (0.77 > self.EMADiff.Current.Value and 0 <= self.trigger <= 1)):
                self.trigger = 0
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", 0.30)
                if self.Securities["SPXL"] not in openOrders:
                    self.SetHoldings("SPXL", 0.45) 
                #if self.Securities["TSLA"] not in openOrders:
                    #self.SetHoldings("TSLA", 0)                     
                #self.Log(self.trigger)
                #self.Log(self.vRoc*100)
                #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))

            #If the EMA ratio is below the mean, heavy short
            elif (0.947 > self.EMADiff.Current.Value and 0 <= self.trigger <= 1):
                self.trigger = 1
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", -0.35)
    #                stop_price = self.Securities["TVIX"].Price
    #                self.StopMarketOrder("TVIX", -float(self.Portfolio["TVIX"].Quantity), float(stop_price)*0.8)
                #self.Log(self.trigger)
                #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
                
    #        if (self.EMADiff.Current.Value <= 0.8259 and self.trigger >= 1):
    #            self.trigger = 1
    #            if self.Securities["TVIX"] not in openOrders:
    #                self.SetHoldings("TVIX", -0.25)
    #            self.Log(self.trigger)
                #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))    
           
        '''    elif (0.915 < self.EMADiff.Current.Value <= 0.945 and 1 <= self.trigger <= 2):
                self.trigger = 2
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", -0.55)
                self.Log(self.trigger)
                #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
                
            elif (0.891 < self.EMADiff.Current.Value <= 0.915 and 2 <= self.trigger <= 3):    
                self.trigger = 3
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", -0.225)
                self.Log(self.trigger)
                #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
                                
            elif (self.EMADiff.Current.Value <= 0.891 and 2 <= self.trigger <= 3):
                self.trigger = 3
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", 0)
                self.Log(self.trigger)
                #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
                
            elif (self.EMADiff.Current.Value <= 0.6 and 2 <= self.trigger <= 3):   
                self.trigger = 2
                if self.Securities["TVIX"] not in openOrders:
                    self.SetHoldings("TVIX", 0.3)
                self.Log(self.trigger)
                #self.Log("Current TVIX QTY: {0} | Current TVIX Dollars: {1}".format(self.Portfolio["TVIX"].Quantity, round(self.Portfolio["TVIX"].AbsoluteHoldingsCost),2))
        '''
        return