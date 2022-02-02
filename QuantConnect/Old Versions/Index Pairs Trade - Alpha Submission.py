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

class LeveragedIndexPairs(QCAlgorithm):
    '''Day trades TVIX. Holds ((200% - TVIX Proportion)*.165) of investment capital in SPXL until VIX exceeds 16.5'''

    def Initialize(self):
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialize.'''

        # Chart - Master Containers for the Charts:
        stockPlot_1 = Chart('SPXL Proportion')
        stockPlot_2 = Chart('Margin Remaining')
        stockPlot_3 = Chart('TVIX Proportion')
        stockPlot_4 = Chart('Moving Averages Difference')
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = Resolution.Minute
        self.UniverseSettings.Leverage = int(2)
        
        #Initial investment and backtest period
        self.SetStartDate(2010,1,1)                                 #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1))        #Set End Date
        #self.SetEndDate(2016,1,1)
        self.SetCash(240000)                                       #Set Strategy Cash
        
        #Capture initial investment for risk off purposes
        self.marginRemaining = self.Portfolio.MarginRemaining
        
        #Universe
        self.AddEquity("TVIX", Resolution.Minute).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("SPXL", Resolution.Minute)
        self.AddData(Vix, "VIX", Resolution.Daily)
        
        #Variables for TvixFunc
        self.fastPeriod = int(2)
        self.slowPeriod = int(15)
        self.vixEmaFast = self.EMA("TVIX", self.fastPeriod, Resolution.Minute)
        self.vixEmaSlow = self.EMA("TVIX", self.slowPeriod, Resolution.Minute)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)

        #Misc Variables
        self.MaxShortProportion = float(0.25)
        self.MaxLongSPXL = round((self.MaxShortProportion*0.885),3)
        self.MaxShortSPXL = float(0.9)
        self.ClosingVix = None
        self.vixDowntrend = True
        self.ClosingVixThreshold = float(16.5)
        self.minEMAThreshold = float(0.985)
        self.maxEMAThreshold = float(1.10)
        self.midEMAThreshold = float(1.007)
        self.vixList = []
        self.MaxList = int(3)
        self.Zero = int(0)
        
        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        
        #Warmup
        self.SetWarmUp(16)
        
    def OnData(self, data):
        
        #Check is the market is open and that indicators have warmed up
        if self.IsMarketOpen("TVIX") and not self.IsWarmingUp:   
        
            #Capture Open Orders to avoid margin problems
            self.OpenOrders = self.Transactions.GetOpenOrders()
            
            #If the previous day closing VIX is above the threshold short the market and long volatility
            if (self.ClosingVix > self.ClosingVixThreshold) or not self.vixDowntrend:
                self.LongVol() 
                
            else: self.ShortVol()
                
        #Capture closing VIX data from the CBOE website and populate a list to monitor VIX trend    
        if not data.ContainsKey("VIX"): return
        else:
            if self.ClosingVix != data["VIX"].Close:
                self.ClosingVix = data["VIX"].Close
                
                if len(self.vixList) == self.MaxList:
                    self.vixList[0] = self.vixList[1]
                    self.vixList[1] = self.vixList[2]
                    self.vixList[2] = self.ClosingVix
                
                else:
                    self.vixList.append(self.ClosingVix)
            
            #Update maximum short vol - long market proportions    
            self.MaxShortProportion = round(np.minimum(float(100/((37/self.ClosingVix) +1))/100, 0.5),3)
            self.MaxLongSPXL = round((self.MaxShortProportion*0.885),3)
            
            #Plot relevant metrics
            self.Plot('TVIX Proportion', 'Max Short Proportion', self.MaxShortProportion*100)
            self.Plot('TVIX Proportion', 'Closing VIX', self.ClosingVix)
            self.Plot('SPXL Proportion', 'SPXL Proportion as %', self.MaxLongSPXL*100)
            self.Plot('Margin Remaining', 'Margin Remaining', self.marginRemaining)
    #        self.PlotIndicator('Moving Averages Difference', self.EMADiff )

            #Monitor VIX trend and liquidate if the VIX is in a downtrend but above the threshold
            if len(self.vixList) == self.MaxList:
                if self.vixList[0] < self.vixList[1] < self.vixList[2]:
                    self.vixDowntrend = False
                else: self.vixDowntrend = True
                
                if (self.vixList[0] < self.vixList[1] < self.vixList[2]) and (self.ClosingVix > self.ClosingVixThreshold):
                    self.Liquidate()
    
        return
    
    def LongVol(self):
        
            #If the VIX has crossed the threshold, liquidate short vol - long market positions
            if  self.Securities["TVIX"].Invested or self.Securities["SPXL"].Invested or self.vixDowntrend:
                if self.Portfolio["TVIX"].Quantity < self.Zero:
                    self.Liquidate("TVIX")
                if self.Portfolio["SPXL"].Quantity > self.Zero:
                    self.Liquidate("SPXL")
                return
            
            #Invest based on the same rules but long vol- short market. No limits as there are liquidation measures built in during high volatility    
            elif self.maxEMAThreshold > self.EMADiff.Current.Value > self.midEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")  
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL") 
                    
                self.SetHoldings("TVIX", self.MaxShortProportion)
                self.SetHoldings("SPXL", -self.MaxShortSPXL)

                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 1.08,2))
                
                self.marginRemaining = self.Portfolio.MarginRemaining 
                
            elif self.EMADiff.Current.Value < self.minEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")   
                    
                self.SetHoldings("TVIX", self.MaxShortProportion) 
                self.SetHoldings("SPXL", -self.MaxShortSPXL)

                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 1.05,2))
                self.marginRemaining = self.Portfolio.MarginRemaining  
                
    def ShortVol(self):
        
            #If the closing vix is below the threshold and we are invested in TVIX then do nothing
            if self.Securities["TVIX"].Invested:
                return
            
            #If the closing vix is below the threshold and we are not invested in TVIX then invest maximum allocations based on IB margin rules into a long market short vol portfolio.
            
            #Volatilty is rising
            elif self.maxEMAThreshold > self.EMADiff.Current.Value > self.midEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX") 
                    
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL")                    
                    
                self.SetHoldings("TVIX", -self.MaxShortProportion)
                self.SetHoldings("SPXL", self.MaxLongSPXL)
                
                holdingPrice = self.Securities["TVIX"].Holdings.AveragePrice
                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice  
                
                #If we enter the positions while volatility is rising set less ambitious exits
                self.LimitOrder("TVIX", -self.Portfolio["TVIX"].Quantity, round( holdingPrice * 0.99,2))
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 0.97,2))
                self.marginRemaining = self.Portfolio.MarginRemaining 
            
            #Volatilty is collapsing    
            elif self.EMADiff.Current.Value < self.minEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")   
                    
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL")   
                    
                self.SetHoldings("TVIX", -self.MaxShortProportion) 
                self.SetHoldings("SPXL", self.MaxLongSPXL)   
                
                holdingPrice = self.Securities["TVIX"].Holdings.AveragePrice
                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                #If we enter the positions while volatility is collapsing set ambitious exits
                self.LimitOrder("TVIX", -self.Portfolio["TVIX"].Quantity, round( holdingPrice * 0.95,2))
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 0.95,2))               
                self.marginRemaining = self.Portfolio.MarginRemaining  
                
    def OnEndOfDay(self):
        #If the VIX is in an uptrend liquidate at the beginning of each trading day
        if not self.vixDowntrend:
            self.Transactions.CancelOpenOrders()
            self.Liquidate()
            
    def OnMarginCallWarning(self):
        #On a margin call warning free up substantial capital based on VIX trend
        if not self.vixDowntrend:
            self.Transactions.CancelOpenOrders()
            self.SetHoldings("SPXL", round(self.MaxLongSPXL*0.10,2))
            self.SetHoldings("TVIX", round(-self.MaxShortProportion*0.25,2))            
        
        else:
            self.Transactions.CancelOpenOrders()
            self.SetHoldings("SPXL", round(-self.MaxLongSPXL*0.10,2))
            self.SetHoldings("TVIX", round(self.MaxShortProportion*0.25,2))             

#Format VIX imported data    
class Vix(PythonData):
    '''New VIX Object'''

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
            index["Close"] = float(data[4])


        except ValueError:
                # Do nothing
                return None

        return index