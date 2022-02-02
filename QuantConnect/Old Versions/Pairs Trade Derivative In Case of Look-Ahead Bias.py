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
        stockPlot_1 = Chart('Margin Remaining')
        stockPlot_2 = Chart('Proportions')
        stockPlot_3 = Chart('Research')
        stockPlot_4 = Chart('Research 2')
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = Resolution.Minute
        self.UniverseSettings.Leverage = int(2)
        
        #Initial investment and backtest period
        self.SetStartDate(2010,12,1)                                 #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1))        #Set End Date
        #self.SetEndDate(2019,1,1)
        self.SetCash(250000)                                       #Set Strategy Cash
        
        #Capture initial investment for risk off purposes
        self.marginRemaining = self.Portfolio.MarginRemaining/self.Portfolio.TotalPortfolioValue
        
        #Universe
        self.AddEquity("TVIX", Resolution.Minute).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("SPXL", Resolution.Minute)
        
        # Add Quandl VIX price (daily)
        self.AddData(QuandlVix, "CBOE/VIX", Resolution.Minute, TimeZones.Chicago)            
        
        #Variables
        self.Zero = int(0)
        self.Damp = float(1.0) 
        self.fastPeriod = int(2)
        self.slowPeriod = int(13)
        self.vixEmaFast = self.EMA("TVIX", self.fastPeriod, Resolution.Minute)
        self.vixEmaSlow = self.EMA("TVIX", self.slowPeriod, Resolution.Minute)
        self.spxlEmaFast = self.EMA("SPXL", self.fastPeriod, Resolution.Daily)
        self.spxlEmaSlow = self.EMA("SPXL", self.slowPeriod, Resolution.Daily)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
        self.SpxlEMADiff = IndicatorExtensions.Over(self.spxlEmaFast,self.spxlEmaSlow)
        self.MaxShortProportion = float(0.25)
        self.MaxLongSPXL = round((self.MaxShortProportion*0.885),3)
        self.MaxShortSPXL = np.minimum( float(0.90), np.maximum( round(float(1.75-(3.26*0.50)),2), round(float(2-(3.26*self.MaxShortProportion)),2)) )
        self.vixList = []
        self.MaxList = int(6)
        self.ClosingVix = Identity("CBOE/VIX")
        self.vixPercentMove = self.Zero
        self.vixPercentMoveList = []
        self.Trade = True
        self.EMALongBounds = [float(1.006),float(1.012),float(1.018), float(1.036)]
        self.EMAShortBounds = [float(0.994), float(0.988), float(0.982)]
        self.SpxlEMABounds = [float(0.974), float(0.942), float(0.91), float(1.0265), float(1.038), float(1.054), float(1.07)]
        self.pnlPoints = [float(0.12), float(0.03), -float(0.025), -float(0.05)]
        self.percentMoveBounds = [int(21), int(30), int(100)]
        self.HourBounds = [int(10), int(16)]
        self.rollingVixSTD = self.Zero
        self.rollingPercentSTD = self.Zero

        
        #Schedule
        self.Schedule.On(self.DateRules.EveryDay("TVIX"), self.TimeRules.BeforeMarketClose("TVIX", int(2)), self.EndOfDay)
        self.Schedule.On(self.DateRules.EveryDay("TVIX"), self.TimeRules.Every(timedelta(minutes=3)), self.CheckLosses)
        
        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        
        #Warmup
        self.SetWarmUp(14)
    
    def CheckLosses(self):
        if not self.IsWarmingUp and self.HourBounds[0] <= self.Time.hour < self.HourBounds[1]:
            
            for x in self.Portfolio:
                
                if self.Portfolio[x.Key].UnrealizedProfitPercent >= self.pnlPoints[0]:
                    self.Liquidate(x.Key)
                    self.Trade = False
                
                elif self.pnlPoints[0] > self.Portfolio[x.Key].UnrealizedProfitPercent >= self.pnlPoints[1]:
                    self.Liquidate(x.Key)
                    
                elif self.Portfolio[x.Key].UnrealizedProfitPercent < self.pnlPoints[3]:
                    self.Liquidate(x.Key)
                    #self.Plot('Research', 'Previous Close over Last Day close', self.EMADiff.Current.Value )
                    self.Trade = False

        return
        
    def OnData(self, data):
        
        if data.Splits.ContainsKey("TVIX"): self.Log("TVIX Split")
        
        if data.ContainsKey("CBOE/VIX"):
            self.ClosingVix.Update(self.Time, self.Securities["CBOE/VIX"].Price)
     
            if len(self.vixList) == self.MaxList:
                self.vixList[0] = self.vixList[1]
                self.vixList[1] = self.vixList[2]
                self.vixList[2] = self.vixList[3]
                self.vixList[3] = self.vixList[4]
                self.vixList[4] = self.vixList[5]
                self.vixList[5] = self.ClosingVix.Current.Value

                self.MaxShortProportion = round(np.minimum(float(100/((37/self.ClosingVix.Current.Value) +1))/100, 0.50),3)
                self.MaxLongSPXL = round((self.MaxShortProportion*0.885),3)
                self.MaxShortSPXL = np.minimum( float(0.50), np.maximum( round(float(1.75-(3.26*0.50)),2), round(float(2-(3.26*self.MaxShortProportion)),2)) )
                self.vixPercentMove = round(float( ((self.vixList[5]/self.vixList[4])-1)*100 ),2)
                self.rollingVixSTD = np.std(self.vixList)

            if len(self.vixPercentMoveList) == self.MaxList:
                self.vixPercentMoveList[0] = self.vixPercentMoveList[1]
                self.vixPercentMoveList[1] = self.vixPercentMoveList[2]
                self.vixPercentMoveList[2] = self.vixPercentMoveList[3]
                self.vixPercentMoveList[3] = self.vixPercentMoveList[4]
                self.vixPercentMoveList[4] = self.vixPercentMoveList[5]
                self.vixPercentMoveList[5] = self.vixPercentMove                
                
                self.rollingPercentSTD = np.std(self.vixPercentMoveList)
                
                self.Plot('Proportions', 'Max TVIX Proportion', self.MaxShortProportion*100)
                self.Plot('Proportions', 'Closing VIX', self.vixList[5])
                self.Plot('Proportions', 'SPXL Long Proportion as %', self.MaxLongSPXL*100)
                self.Plot('Proportions', 'SPXL Short Proportion as %', self.MaxShortSPXL*100)
                self.Plot('Research', 'Rolling %Change Rounded', round(self.vixPercentMove,1))
                self.Plot('Research 2', 'Rolling Closing VIX STD', self.rollingVixSTD)
                self.Plot('Research 2', 'Rolling %Change STD', self.rollingPercentSTD)
                
            else:
                self.vixList.append(self.ClosingVix.Current.Value)
                self.vixPercentMoveList.append(self.vixPercentMove)
                
        if not self.IsWarmingUp and self.HourBounds[0] <= self.Time.hour <= self.HourBounds[1] and len(self.vixList) == self.MaxList:    
            
            if ( self.percentMoveBounds[0] <= round(self.vixPercentMove,2) < self.percentMoveBounds[1] ) or ( round(self.vixPercentMove,2) >= self.percentMoveBounds[2] ): 
                if self.Trade: self.LongVol()
               
            elif self.SpxlEMABounds[5] <= self.SpxlEMADiff.Current.Value or self.rollingPercentSTD >= int(25):# <= self.SpxlEMABounds[5]:
                if self.Trade: self.LongVol() 
                
            elif self.ClosingVix.Current.Value > 30 and self.vixList[4] <= self.vixList[5]:
                if self.Trade: self.LongVol() 
                
            elif self.vixList[2] <= self.vixList[3] <= self.vixList[4] <= self.vixList[5] and self.ClosingVix.Current.Value > 20:
                if self.Trade: self.LongVol()
                
            elif self.EMAShortBounds[1] < self.EMADiff.Current.Value < self.EMALongBounds[2] and self.rollingPercentSTD < int(9) and self.vixPercentMove > -14:
                if self.Trade: self.ShortVol()

            elif self.rollingVixSTD >= int(3) or self.SpxlEMADiff.Current.Value <= self.SpxlEMABounds[0]: 
                if self.Trade: self.ShortVol()          
        return

    #Long Vol will be long TVIX and short SPXL. TVIX position size dictated by formula, up to 50%. SPXL proportion dictated by separate formula.
    #4% stop loss placed on SPXL. TVIX held until liquidation trigger.
    def LongVol(self):
        
        if self.Portfolio["SPXL"].Quantity > self.Zero:
            self.Liquidate("SPXL")  
            
        if not self.Portfolio["TVIX"].Invested:
            
            if self.EMALongBounds[0] <= self.EMADiff.Current.Value:
                
                self.Transactions.CancelOpenOrders("TVIX")
                self.SetHoldings("TVIX", self.MaxShortProportion)
                self.Transactions.CancelOpenOrders("SPXL")
                self.SetHoldings("SPXL", -self.MaxShortSPXL)            
            return
            
        else:
            return
            
    
    #Short vol will short TVIX and long SPXL.  TVIX position size derived by formula, and SPXL is 15% less than TVIX size. 
    #Limit orders for TVIX at 10% intervals. SPXL stops at 15%           
    def ShortVol(self):
        
        if self.Portfolio["TVIX"].Quantity > self.Zero or self.Portfolio["SPXL"].Quantity < self.Zero:
            self.Liquidate()
        
        if not self.Portfolio["TVIX"].Invested:
            
            self.Transactions.CancelOpenOrders("TVIX")
            self.SetHoldings("TVIX", -self.MaxShortProportion)
            self.Transactions.CancelOpenOrders("SPXL")
            self.SetHoldings("SPXL", self.MaxLongSPXL)             
            return
        
        else:
            return   
    
    def Hedge(self):
        
        self.Transactions.CancelOpenOrders("TVIX")
        self.SetHoldings("TVIX", round(self.MaxShortProportion*0.25,2))
      
            
            
    #At the end of the day if the VIX is in an uptrend place liquidation orders to be filled at open the next trading day            
    def EndOfDay(self):
        
        if not self.IsWarmingUp and len(self.vixList) == self.MaxList:
            
            for x in self.Portfolio:
                
                if self.Portfolio[x.Key].UnrealizedProfitPercent < self.pnlPoints[2]:
                    self.Liquidate(x.Key)
                    self.Trade = False
    
    def OnEndOfDay(self):
        self.Trade = True
        
    #On a margin call warning liquidate the majority of positions to free up capital and avoid a margin call       
    def OnMarginCallWarning(self):
        return
    
    def OnMarginCall(self, requests):
           
        for order in requests:
            
            # liquidate an extra 10% each time we get a margin call to give us more padding
            newQuantity = int(np.sign(order.Quantity) * order.Quantity * float(1.10))
            requests.remove(order)
            requests.append(SubmitOrderRequest(order.OrderType, order.SecurityType, order.Symbol, newQuantity, order.StopPrice, order.LimitPrice, self.Time, "OnMarginCall"))
        
        return requests 
        
class QuandlVix(PythonQuandl):
    def __init__(self):
        self.ValueColumnName = "vix Close"