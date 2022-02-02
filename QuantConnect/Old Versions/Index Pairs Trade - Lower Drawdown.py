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
    '''SPXL-TVIX pairs trade. '''

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
        self.SetStartDate(2016,8,25)                                 #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1))        #Set End Date
        #self.SetEndDate(2018,1,1)
        self.SetCash(250000)                                       #Set Strategy Cash
        
        #Capture initial investment for risk off purposes
        self.marginRemaining = self.Portfolio.MarginRemaining
        
        #Universe
        self.AddEquity("TVIX", Resolution.Minute).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("SPXL", Resolution.Minute)
        self.AddData(Vix, "VIX", Resolution.Daily)
        
        #Variables
        self.fastPeriod = int(2)
        self.slowPeriod = int(15)
        self.vixEmaFast = self.EMA("TVIX", self.fastPeriod, Resolution.Minute)
        self.vixEmaSlow = self.EMA("TVIX", self.slowPeriod, Resolution.Minute)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
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
        
        #If the market is open and the algorithm is not warming up, make trades
        if self.IsMarketOpen("TVIX") and not self.IsWarmingUp:   
        
            #capture open orders to avoid leverage issues
            self.OpenOrders = self.Transactions.GetOpenOrders()
            
            #If the VIX dropped 15% while above threshold, run short vol
            if ( (self.vixList[2] <= (self.vixList[1] * float(0.85)) ) and (self.ClosingVix >= self.ClosingVixThreshold) ):
                self.ShortVol()
            
            #Otherwise if the spot VIX closed above the threshold run long vol    
            elif self.ClosingVix >= self.ClosingVixThreshold:
                self.LongVol()            
            
            #All other conditions run short vol
            else: self.ShortVol()
        
        #If there is no VIX data return        
        if not data.ContainsKey("VIX"): return
    
        #If there is VIX data, populate the VIX list and update position proportions and charts accordingly
        else:
            if self.ClosingVix != data["VIX"].Close:
                self.ClosingVix = data["VIX"].Close
                
                if len(self.vixList) == self.MaxList:
                    self.vixList[0] = self.vixList[1]
                    self.vixList[1] = self.vixList[2]
                    self.vixList[2] = self.ClosingVix
                
                else:
                    self.vixList.append(self.ClosingVix)
                
            self.MaxShortProportion = round(np.minimum(float(100/((37/self.ClosingVix) +1))/100, 0.5),3)
            self.MaxLongSPXL = round((self.MaxShortProportion*0.885),3)
            
            self.Plot('TVIX Proportion', 'Max Short Proportion', self.MaxShortProportion*100)
            self.Plot('TVIX Proportion', 'Closing VIX', self.ClosingVix)
            self.Plot('SPXL Proportion', 'SPXL Proportion as %', self.MaxLongSPXL*100)
            self.Plot('Margin Remaining', 'Margin Remaining', self.marginRemaining)
            self.PlotIndicator('Moving Averages Difference', self.EMADiff )

            #If the list is fully populated, monitor VIX trend
            if len(self.vixList) == self.MaxList:
                
                #If the VIX has risen for two days straight, it is in an uptrend. Otherwise, downtrend
                if self.vixList[0] < self.vixList[1] < self.vixList[2]:
                    self.vixDowntrend = False
                    self.Log("VIX is in an uptrend")
                    
                else: self.vixDowntrend = True
                
                #If the VIX has risen for two days straight while above the treshold, capture profits. Also capture profits any time the VIX rises by 20% or more
                if ( (self.vixList[0] < self.vixList[1] < self.vixList[2]) and (self.ClosingVix >= self.ClosingVixThreshold) ) or self.vixList[2] >= (self.vixList[1] * float(1.2) ):
                    if not self.IsWarmingUp:
                        self.Liquidate()
                        self.Log("Liquidated because the VIX has been down for two days during Long Vol protocol or because the VIX spiked hard yesterday")
        return

    #Long Vol will be long TVIX and short SPXL. TVIX position size dictated by formula, up to 50%. SPXL proportion 90%. 5% stop loss placed on SPXL. TVIX held until liquidation trigger.
    def LongVol(self):
        
            if  self.Securities["TVIX"].Invested or self.Securities["SPXL"].Invested or self.vixDowntrend:
                if self.Portfolio["TVIX"].Quantity < self.Zero:
                    self.Liquidate("TVIX")
                if self.Portfolio["SPXL"].Quantity > self.Zero:
                    self.Liquidate("SPXL")
                return
                
            elif self.maxEMAThreshold > self.EMADiff.Current.Value > self.midEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")  
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL") 
                    
                self.SetHoldings("TVIX", self.MaxShortProportion)
                self.SetHoldings("SPXL", -self.MaxShortSPXL)

                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 1.05,2))
                
                self.marginRemaining = self.Portfolio.MarginRemaining 
                
            elif self.EMADiff.Current.Value < self.minEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")   
                    
                self.SetHoldings("TVIX", self.MaxShortProportion) 
                self.SetHoldings("SPXL", -self.MaxShortSPXL)

                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 1.05,2))
                self.marginRemaining = self.Portfolio.MarginRemaining 
                
    #Short vol will short TVIX and long SPXL.  TVIX position size derived by formula, and SPXL is 15% less than TVIX size.  Limit orders for TVIX at 8% intervals. SPXL stops at 8% or 4% depending on market condition at time of order           
    def ShortVol(self):
        
            if self.Securities["TVIX"].Invested:
                return
                
            elif self.maxEMAThreshold > self.EMADiff.Current.Value > self.midEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX") 
                    
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL")                    
                    
                self.SetHoldings("TVIX", -self.MaxShortProportion)
                self.SetHoldings("SPXL", self.MaxLongSPXL)
                
                holdingPrice = self.Securities["TVIX"].Holdings.AveragePrice
                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice  
                
                self.LimitOrder("TVIX", -self.Portfolio["TVIX"].Quantity, round( holdingPrice * 0.92,2))
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 0.92,2))
                self.marginRemaining = self.Portfolio.MarginRemaining 
                
            elif self.EMADiff.Current.Value < self.minEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")   
                    
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL")   
                    
                self.SetHoldings("TVIX", -self.MaxShortProportion) 
                self.SetHoldings("SPXL", self.MaxLongSPXL)   
                
                holdingPrice = self.Securities["TVIX"].Holdings.AveragePrice
                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.LimitOrder("TVIX", -self.Portfolio["TVIX"].Quantity, round( holdingPrice * 0.92,2))
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 0.96,2))               
                self.marginRemaining = self.Portfolio.MarginRemaining
                
    #At the end of the day if the VIX is in an uptrend place liquidation orders to be filled at open the next trading day            
    def OnEndOfDay(self):
        if not self.vixDowntrend:
            self.Transactions.CancelOpenOrders()
            self.Liquidate()
    
    #On a margin call warning liquidate the majority of positions to free up capital and avoid a margin call       
    def OnMarginCallWarning(self):
        if not self.vixDowntrend and not self.IsWarmingUp:
            self.Transactions.CancelOpenOrders()
            self.SetHoldings("SPXL", round(self.MaxLongSPXL*0.10,2))
            self.SetHoldings("TVIX", round(-self.MaxShortProportion*0.25,2))            
        
        else:
            self.Transactions.CancelOpenOrders()
            self.SetHoldings("SPXL", round(-self.MaxLongSPXL*0.10,2))
            self.SetHoldings("TVIX", round(self.MaxShortProportion*0.25,2))             

#Spot VIX data imported from the CBOE website which updates its spreadsheet daily.    
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