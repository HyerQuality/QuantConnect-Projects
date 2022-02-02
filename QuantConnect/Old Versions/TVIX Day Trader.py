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
from Risk.TrailingStopRiskManagementModel import TrailingStopRiskManagementModel

class ThetaArb(QCAlgorithm):
    '''Day trades TVIX. Holds (175% - TVIX Proportion) of investment capital in SPXL until VIX exceeds 16.5'''

    def Initialize(self):
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialize.'''

        # Chart - Master Containers for the Charts:
        stockPlot_1 = Chart('SPXL Proportion')
        stockPlot_2 = Chart('Margin Remaining')
        stockPlot_3 = Chart('TVIX Proportion')
        stockPlot_4 = Chart('Moving Averages')
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = Resolution.Minute
        
        #Initial investment and backtest period
        self.SetStartDate(2011,12,1)                                 #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1))        #Set End Date
        #self.SetEndDate(2016,1,1)
        self.SetCash(230000)                                       #Set Strategy Cash
        
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

        self.MaxShortProportion = float(0.25)  #Set to a different value than intended to check that VIX data is loaded and variable is being adjusted
        self.MaxSpxlProportion = round(1.75 - self.MaxShortProportion,2)
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
        
        self.SetWarmUp(16)
        
    def OnData(self, data):
        
        if data.ContainsKey("TVIX") and self.IsMarketOpen("TVIX"):   
        
            self.OpenOrders = self.Transactions.GetOpenOrders()
            
            if self.ClosingVix > self.ClosingVixThreshold:
                self.LongVol()            

            elif  self.Securities["TVIX"].Invested or self.Securities["SPXL"].Invested:
                return
                
            elif self.maxEMAThreshold > self.EMADiff.Current.Value > self.midEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX") 
                    
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL")                    
                    
                self.SetHoldings("TVIX", -self.MaxShortProportion)
                self.SetHoldings("SPXL", self.MaxSpxlProportion)
                
                holdingPrice = self.Securities["TVIX"].Holdings.AveragePrice
                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice  
                
                self.LimitOrder("TVIX", -self.Portfolio["TVIX"].Quantity, round( holdingPrice * 0.97,2))
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 0.92,2))
                self.marginRemaining = self.Portfolio.MarginRemaining 
                
            elif self.EMADiff.Current.Value < self.minEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")   
                    
                if self.Securities["SPXL"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("SPXL")   
                    
                self.SetHoldings("TVIX", -self.MaxShortProportion) 
                self.SetHoldings("SPXL", self.MaxSpxlProportion)   
                
                holdingPrice = self.Securities["TVIX"].Holdings.AveragePrice
                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.LimitOrder("TVIX", -self.Portfolio["TVIX"].Quantity, round( holdingPrice * 0.99,2))
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 0.96,2))               
                self.marginRemaining = self.Portfolio.MarginRemaining
                
            
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
                
            self.MaxShortProportion = round(np.minimum(float(100/((37/self.ClosingVix) +1))/100, 0.5),3)
            self.MaxSpxlProportion = round(1.75 - self.MaxShortProportion,2)
            
            self.Plot('TVIX Proportion', 'Max Short Proportion', self.MaxShortProportion*100)
            self.Plot('TVIX Proportion', 'Closing VIX', self.ClosingVix)
            self.Plot('SPXL Proportion', 'SPXL Proportion as %', self.MaxSpxlProportion*100)
            self.Plot('Margin Remaining', 'Margin Remaining', self.marginRemaining)

            if len(self.vixList) == self.MaxList:
                if self.vixList[0] < self.vixList[1] < self.vixList[2]:
                    self.vixDowntrend = False
                else: self.vixDowntrend = True
    
        return

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
                self.SetHoldings("SPXL", -self.MaxSpxlProportion)

                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 1.08,2))
                
                self.marginRemaining = self.Portfolio.MarginRemaining 
                
            elif self.EMADiff.Current.Value < self.minEMAThreshold:
                
                if self.Securities["TVIX"] in self.OpenOrders:
                    self.Transactions.CancelOpenOrders("TVIX")   
                    
                self.SetHoldings("TVIX", self.MaxShortProportion) 
                self.SetHoldings("SPXL", -self.MaxSpxlProportion)

                spxlHoldingPrice = self.Securities["SPXL"].Holdings.AveragePrice 
                
                self.StopMarketOrder("SPXL", -self.Portfolio["SPXL"].Quantity, round( spxlHoldingPrice * 1.05,2))
                self.marginRemaining = self.Portfolio.MarginRemaining  

    def OnEndOfDay(self):
        if not self.vixDowntrend:
            self.Transactions.CancelOpenOrders()
            self.Liquidate()
            
    def OnMarginCallWarning(self):
        if not self.vixDowntrend:
            self.Transactions.CancelOpenOrders()
            self.SetHoldings("SPXL", round(-self.MaxSpxlProportion*0.10,2))
            self.SetHoldings("TVIX", round(self.MaxShortProportion*0.75,2))            
        
        else:
            self.Transactions.CancelOpenOrders()
            self.SetHoldings("SPXL", round(self.MaxSpxlProportion*0.10,2))
            self.SetHoldings("TVIX", round(-self.MaxShortProportion*0.75,2))             
    
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