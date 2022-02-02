import numpy as np
import pandas as pd
from QuantConnect.Data.Custom.CBOE import *

from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Common")

from datetime import *
from System import *
from QuantConnect import *
from QuantConnect.Algorithm import *
from QuantConnect.Data.Market import TradeBar
import json
import math
from QuantConnect.Data import SubscriptionDataSource
from QuantConnect.Python import PythonData

resolution = Resolution.Minute

class LeveragedIndexPairs(QCAlgorithm):
    '''SPXL-TVIX pairs trade. '''

    def Initialize(self):
  
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialize.'''
        
        # Chart - Master Containers for the Charts:
        stockPlot_1 = Chart('Margin Remaining')
        stockPlot_2 = Chart('Proportions')
        stockPlot_3 = Chart('VIX Spot')
        stockPlot_4 = Chart('VIX Standard Dev')
        stockPlot_5 = Chart('Moving Averages')
        
        #Establish universe-wide settings
        self.UniverseSettings.Resolution = resolution
        self.UniverseSettings.Leverage = int(2)
        
        #Initial investment and backtest period
        self.SetStartDate(2014,1,1)                                 #Set Start Date
        #self.SetEndDate(datetime.now().date() - timedelta(1))        #Set End Date
        #self.SetEndDate(2019,11,30)
        self.SetCash(111040.20)                                       #Set Strategy Cash
        
        #Capture initial investment for risk off purposes
        self.marginRemaining = self.Portfolio.MarginRemaining/self.Portfolio.TotalPortfolioValue
        
        #Universe
        self.AddEquity("TVIX", resolution).SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.AddEquity("SPXL", resolution)
        self.AddEquity("UVXY", resolution)
        self.AddEquity("SPXS", resolution)
        
        # Add Quandl VIX price (daily)
        self.AddData(CBOE, "VIX")
        
        #Variables
        self.Zero = int(0)
        self.TvixDamp = float(1.00) 
        self.SpxlDamp = float(0.60)
        self.fastPeriod = int(2)
        self.slowPeriod = int(13)
        self.MaxShortProportion = float(0.25)
        self.MaxLongSPXL = round((self.MaxShortProportion*0.885),3)
        self.MaxShortSPXL = np.minimum( float(0.40), np.maximum( round(float(1.75-(3.26*0.50)),2), round(float(2-(3.26*self.MaxShortProportion)),2)) )
        self.MaxList = int(6)
        self.ClosingVix = Identity("CBOE/VIX")
        self.vixPercentMove = self.Zero
        self.SixDayVixSpotSTD = self.Zero
        self.SixDayVixPercentMoveSTD = self.Zero
        
        #Indicators
        self.vixEmaFast = self.EMA("TVIX", self.fastPeriod, resolution)
        self.vixEmaSlow = self.EMA("TVIX", self.slowPeriod, resolution)
        self.spxlEmaFast = self.EMA("SPXL", self.fastPeriod, Resolution.Daily)
        self.spxlEmaSlow = self.EMA("SPXL", self.slowPeriod, Resolution.Daily)
        self.EMADiff = IndicatorExtensions.Over(self.vixEmaFast,self.vixEmaSlow)
        self.SpxlEMADiff = IndicatorExtensions.Over(self.spxlEmaFast,self.spxlEmaSlow)

        #Lists
        self.vixList = []
        self.vixPercentMoveList = []
        self.pnlPoints = [float(0.10), float(0.03), -float(0.025), -float(0.05)]
        self.percentMoveBounds = [int(21), int(31), int(100)]
        self.HourBounds = [time(10,00), time(16,0)]
        
        #Booleans
        self.Trade = True
        self.longvol = False
        self.shortvol = False
        self.uvxy = False
        self.spxs = False
        self.Split = False
        
        #Minute-based standard deviations
        self.EMALongBounds = [float(1.006),float(1.012),float(1.018), float(1.036)] #[ +1, +2, +3, +4]
        self.EMAShortBounds = [float(0.994), float(0.988), float(0.982)] #[-1, -2, -3]
        
        #Day-based standard deviations
        self.SpxlEMABounds = [float(0.974), float(0.942), float(0.91), float(1.0265), float(1.038), float(1.054), float(1.07)] #[-1, -2, -3, +1, +2, +3, +4]

        #Schedule
        self.Schedule.On(self.DateRules.EveryDay("TVIX"), self.TimeRules.BeforeMarketClose("TVIX", int(2)), self.JustBeforeClose)
        self.Schedule.On(self.DateRules.EveryDay("TVIX"), self.TimeRules.Every(timedelta(minutes=60)), self.ManagePositions)
        self.Schedule.On(self.DateRules.EveryDay("TVIX"), self.TimeRules.Every(timedelta(minutes=5)), self.CheckLargeLosses)
        
        #Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        #self.SetBrokerageModel(AlphaStreamsBrokerageModel())
        
        #Warmup
        self.SetWarmUp(14)
        
    def CheckLargeLosses(self):

        if not self.IsWarmingUp and self.HourBounds[0] <= self.Time.time() < self.HourBounds[1]:
            
            for x in self.Portfolio:

                if self.Portfolio[x.Key].UnrealizedProfitPercent <= self.pnlPoints[3]*1.25:
                    self.Liquidate(x.Key)
                    self.Trade = False
        return
    
    def ManagePositions(self):
        if not self.IsWarmingUp and self.HourBounds[0] <= self.Time.time() < self.HourBounds[1]:
            
            for x in self.Portfolio:
                
                if self.Portfolio[x.Key].UnrealizedProfitPercent >= self.pnlPoints[0]:
                    self.Liquidate(x.Key)
                    self.Trade = False
                
                elif self.pnlPoints[0] > self.Portfolio[x.Key].UnrealizedProfitPercent >= self.pnlPoints[1]:
                    self.Liquidate(x.Key)
                    
                elif self.Portfolio[x.Key].UnrealizedProfitPercent < self.pnlPoints[3]:
                    self.Liquidate(x.Key)
                    self.Trade = False
        return

    def JustBeforeClose(self):
        
        if not self.IsWarmingUp and len(self.vixList) == self.MaxList:

            for x in self.Portfolio:
                
                if self.Portfolio[x.Key].UnrealizedProfitPercent < self.pnlPoints[2]:
                    self.Liquidate(x.Key)
                    self.Trade = False
                    
        self.TvixDamp = float(1.0) 
        
    def OnData(self, data):
        
        if self.IsWarmingUp: return

        if data.Splits.ContainsKey("TVIX"):
            self.Log("TVIX Split")
            self.Debug("TVIX Split")
            self.Split = True
                
        if len(self.vixList) != self.MaxList:
            days = 6
            VIXHistory = self.History(CBOE, "VIX", days, Resolution.Daily)
            
            while len(VIXHistory) < 6:
                days += 1
                VIXHistory = self.History(CBOE, "VIX", days, Resolution.Daily)
                
            for row in VIXHistory.loc["VIX.CBOE"].iterrows():
                self.vixList.append(row[1]["close"])
            self.Log("{0}".format(self.vixList))  
        
        if data.ContainsKey("VIX.CBOE") and len(self.vixList) == self.MaxList:
                    
            self.ClosingVix.Update(self.Time, self.Securities["VIX.CBOE"].Close)
            self.Log("At {0} the VIX list updated. Previous close was {1}".format(self.Time, self.ClosingVix.Current.Value))

            self.vixList[0] = self.vixList[1]
            self.vixList[1] = self.vixList[2]
            self.vixList[2] = self.vixList[3]
            self.vixList[3] = self.vixList[4]
            self.vixList[4] = self.vixList[5]
            self.vixList[5] = self.ClosingVix.Current.Value

            self.MaxShortProportion = round(np.minimum(float(100/((37/self.ClosingVix.Current.Value) +1))/100, 0.50),3)
            self.MaxLongSPXL = round((self.MaxShortProportion*0.885),3)
            self.MaxShortSPXL = np.minimum( float(0.55), np.maximum( round(float(1.75-(3.26*0.50)),2), round(float(2-(3.26*self.MaxShortProportion)),2)) )
            self.vixPercentMove = round(float( ((self.vixList[5]/self.vixList[4])-1)*100 ),2)
            self.SixDayVixSpotSTD = np.std(self.vixList)
                        
            if len(self.vixPercentMoveList) == self.MaxList:
                self.vixPercentMoveList[0] = self.vixPercentMoveList[1]
                self.vixPercentMoveList[1] = self.vixPercentMoveList[2]
                self.vixPercentMoveList[2] = self.vixPercentMoveList[3]
                self.vixPercentMoveList[3] = self.vixPercentMoveList[4]
                self.vixPercentMoveList[4] = self.vixPercentMoveList[5]
                self.vixPercentMoveList[5] = self.vixPercentMove
                
                self.SixDayVixPercentMoveSTD = np.std(self.vixPercentMoveList)
                
                self.Plot('Proportions', 'Max TVIX Proportion', self.MaxShortProportion*100)
                self.Plot('Proportions', 'SPXL Long Proportion as %', self.MaxLongSPXL*100)
                self.Plot('Proportions', 'SPXL Short Proportion as %', self.MaxShortSPXL*100)
                #self.Plot('Moving Averages', 'TVIX Moving Average xOver', self.EMADiff.Current.Value)
                self.Plot('VIX Spot', 'VixPercentMove', round(self.vixPercentMove,1))
                self.Plot('VIX Spot', 'Closing VIX', self.vixList[5])
                self.Plot('VIX Standard Dev', 'SixDayVixSpotSTD', self.SixDayVixSpotSTD)
                self.Plot('VIX Standard Dev', 'SixDayVixPercentMoveSTD', self.SixDayVixPercentMoveSTD)

            else:
                self.vixPercentMoveList.append(round(float( ((self.vixList[1]/self.vixList[0])-1)*100 ),2))
                self.vixPercentMoveList.append(round(float( ((self.vixList[2]/self.vixList[1])-1)*100 ),2))
                self.vixPercentMoveList.append(round(float( ((self.vixList[3]/self.vixList[2])-1)*100 ),2))
                self.vixPercentMoveList.append(round(float( ((self.vixList[4]/self.vixList[3])-1)*100 ),2))
                self.vixPercentMoveList.append(round(float( ((self.vixList[5]/self.vixList[4])-1)*100 ),2))
                self.vixPercentMoveList.append(self.vixPercentMove)
                self.Log("{0}".format(self.vixPercentMoveList))
                
        if not self.IsWarmingUp and self.HourBounds[0] <= self.Time.time() <= self.HourBounds[1] and len(self.vixList) == self.MaxList: 
            
            if ( self.percentMoveBounds[0] <= round(self.vixPercentMove,2) < self.percentMoveBounds[1] ) or ( round(self.vixPercentMove,2) >= self.percentMoveBounds[2] ): 
                if self.Trade: self.LongVol()
                
            elif self.SpxlEMABounds[5] <= self.SpxlEMADiff.Current.Value or self.SixDayVixPercentMoveSTD >= int(25):
                if self.Trade: self.LongVol() 
                
            elif self.ClosingVix.Current.Value > int(30) and self.vixList[4] <= self.vixList[5]:
                if self.Trade: self.LongVol() 
                
            elif self.vixList[2] <= self.vixList[3] <= self.vixList[4] <= self.vixList[5] and self.ClosingVix.Current.Value > int(20):
                if self.Trade: self.LongVol()

            elif self.EMADiff.Current.Value > self.EMAShortBounds[1] and self.SixDayVixPercentMoveSTD < int(11) and self.vixPercentMove > -int(14):    
                if self.Trade: self.ShortVol()

            elif self.SpxlEMABounds[0] >= self.SpxlEMADiff.Current.Value >= self.SpxlEMABounds[2] or self.SixDayVixSpotSTD >= int(3): 
                if self.Trade: self.ShortVol()

    def LongVol(self):
        
        self.longvol = True
        self.shortvol = False
        
        if self.uvxy == False and self.spxs == False:    
            if not self.Portfolio["TVIX"].Invested:
                
                if self.EMALongBounds[0] >= self.EMADiff.Current.Value:
                    
                    self.SetHoldings("TVIX", self.MaxShortProportion*self.TvixDamp)
                    self.Transactions.CancelOpenOrders("SPXL")
                    self.SetHoldings("SPXL", -self.MaxShortSPXL*self.SpxlDamp)            

            
        if self.uvxy == True and self.spxs == False:    
            if not self.Portfolio["UVXY"].Invested:
                
                if self.EMALongBounds[0] <= self.EMADiff.Current.Value:
                    
                    self.SetHoldings("UVXY", self.MaxShortProportion*self.TvixDamp)
                    self.Transactions.CancelOpenOrders("SPXL")
                    self.SetHoldings("SPXL", -self.MaxShortSPXL*self.SpxlDamp)            

        
        if self.uvxy == False and self.spxs == True:
            if not self.Portfolio["TVIX"].Invested:
                
                if self.EMALongBounds[0] <= self.EMADiff.Current.Value:
                    
                    self.SetHoldings("TVIX", self.MaxShortProportion*self.TvixDamp)
                    self.Transactions.CancelOpenOrders("SPXL")
                    self.SetHoldings("SPXS", self.MaxShortSPXL*self.SpxlDamp)            
          
            
        if self.uvxy == True and self.spxs == True:
            if not self.Portfolio["UVXY"].Invested:
                
                if self.EMALongBounds[0] <= self.EMADiff.Current.Value:
                    
                    self.SetHoldings("UVXY", self.MaxShortProportion*self.TvixDamp)
                    self.Transactions.CancelOpenOrders("SPXL")
                    self.SetHoldings("SPXS", self.MaxShortSPXL*self.SpxlDamp)            
                
            
    def ShortVol(self):
        
        self.longvol = False
        self.shortvol = True  

        if self.Portfolio["TVIX"].Quantity > self.Zero or self.Portfolio["SPXL"].Quantity < self.Zero or self.Portfolio["UVXY"].Quantity > self.Zero or self.Portfolio["SPXS"].Quantity > self.Zero:
            self.Liquidate()
        
        if self.uvxy == False and self.spxs == False:
            
            if not self.Portfolio["TVIX"].Invested:
                
                self.SetHoldings("TVIX", -self.MaxShortProportion*self.TvixDamp)
                self.Transactions.CancelOpenOrders("SPXL")
                self.SetHoldings("SPXL", self.MaxLongSPXL*self.SpxlDamp)             
 
            
        if self.uvxy == True and self.spxs == False:
            
            if not self.Portfolio["UVXY"].Invested:
                
                self.SetHoldings("UVXY", -self.MaxShortProportion*self.TvixDamp)
                self.Transactions.CancelOpenOrders("SPXL")
                self.SetHoldings("SPXL", self.MaxLongSPXL*self.SpxlDamp)             
           
       
        if self.uvxy == False and self.spxs == True:
            
            if not self.Portfolio["TVIX"].Invested:
                
                self.SetHoldings("TVIX", -self.MaxShortProportion*self.TvixDamp)
                self.Transactions.CancelOpenOrders("SPXS")
                self.SetHoldings("SPXS", -self.MaxLongSPXL*self.SpxlDamp)             
 
            
        if self.uvxy == True and self.spxs == True:
            
            if not self.Portfolio["UVXY"].Invested:
                
                self.SetHoldings("UVXY", -self.MaxShortProportion*self.TvixDamp)
                self.Transactions.CancelOpenOrders("SPXS")
                self.SetHoldings("SPXS", -self.MaxLongSPXL*self.SpxlDamp)             
            
    
    def OnEndOfDay(self):
        self.Trade = True
        self.longvol = False
        self.shortvol = False 
        self.uvxy = False
        self.spxs = False
        self.Split = False
        
    #On a margin call warning liquidate the majority of positions to free up capital and avoid a margin call       
    def OnMarginCallWarning(self):
        self.Log("Margin Call Warning")
        return
    
    def OnMarginCall(self, requests):
           
        for order in requests:
            
            # liquidate an extra 10% each time we get a margin call to give us more padding
            newQuantity = int(np.sign(order.Quantity) * order.Quantity * float(1.10))
            requests.remove(order)
            requests.append(SubmitOrderRequest(order.OrderType, order.SecurityType, order.Symbol, newQuantity, order.StopPrice, order.LimitPrice, self.Time, "OnMarginCall"))
        
        return requests 
    
    def OnBrokerageMessage(self, messageEvent):
        message = messageEvent.Message
        if re.search("Brokerage Warning: Contract is not available for trading. Origin: IBPlaceOrder: STK TVIX USD Smart", message):
            self.uvxy = True
        if re.search("Brokerage Warning: Contract is not available for trading. Origin: IBPlaceOrder: STK SPXL USD Smart", message):
            self.spxs = True
        if re.search("IN ORDER TO OBTAIN THE DESIRED POSITION", message):
            self.TvixDamp = self.TvixDamp * float(0.95)