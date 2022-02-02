##-------------------Imports---------------------------------------------------##

import numpy as np
import pandas as pd
from datetime import *

from clr import AddReference
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm.Framework")

from QuantConnect import Resolution, Extensions
from QuantConnect.Algorithm.Framework.Alphas import *
from QuantConnect.Data.Custom.CBOE import *

from Vix import VixHandler
from DynamicWeight import Weights

##-------------------Global variables------------------------------------------##

Zero = int(0)
One = int(1)
OneDay = timedelta(days=1)


##-------------------Insight Parameters----------------------------------------##

RemainingTradingDay = timedelta(hours=6.15)
IntradayMagnitude = float(0.05)
ShortTermMagnitude = float(0.001)

class Debug(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self, StatPeriod):

        # SymbolData Parameters
        self.FastPeriod = int(2)
        self.SlowPeriod = int(4)
        self.StatPeriod = StatPeriod
        self.resolution = Resolution.Hour
        self.Debugger = {}

        # Variables
        self.Lag = Zero
        self.Name = "Debug Alpha Model"
        
        # Lists
        self.TimeBounds = [time(9,45), time(12,00), time(9,31), time(9,32), time(15,59), time(16,00)]
     
        # Booleans
        self.Reset = True
        self.OnStartUp = True
        self.TradingWindow = False

##-----------------Update-------------------------------------------------------##     

    def Update(self, algorithm, data):

        insights = []
        
##-----------------Update various statistics annually----------------------------##
            
        self.AnnualRecalc(algorithm)
        
                
##-----------------Manage the trading window----------------------------------------##

        # Check to make sure we allow the first 30 minutes of price action to play out
        if (self.TimeBounds[0] <= algorithm.Time.time() <= self.TimeBounds[5]) and not self.TradingWindow: 
            self.TradingWindow = True
        else:
            self.TradingWindow = False
            

##-----------------Capture and store the overnight gap------------------------------##

        # Within the first minute of market open capature the gap change for QQQ
        for symbol, symbolData in self.Debugger.items():
            if self.TimeBounds[2] <= algorithm.Time.time() < self.TimeBounds[3]:
                if not symbolData.Trade:
                    algorithm.Log("{0} trade signal reset".format(symbol))
                    symbolData.Trade = True
                
                if not data.ContainsKey(symbol):
                    symbolData.PriceWindow = RollingWindow[TradeBar](2)
                    algorithm.Log("Price Window reset on : {0}".format(algorithm.Time))
                    continue
                
                else:
                    symbolData.PriceWindow.Add(algorithm.CurrentSlice[symbol])
                
                    if symbolData.PriceWindow.IsReady:
                        Gap = (symbolData.PriceWindow[0].Open/symbolData.PriceWindow[1].Close)-1
                        symbolData.Gap = round(Gap,2)
                        algorithm.Log("QQQ Gap Calculated at {1}: {0}".format(symbolData.Gap, algorithm.Time))
                
                    else:
                        Gap = Zero
                        
            elif self.TimeBounds[4] <= algorithm.Time.time() < self.TimeBounds[5]:
                if data.ContainsKey(symbol):
                    symbolData.PriceWindow.Add(algorithm.CurrentSlice[symbol])
                else:
                    symbolData.PriceWindow = RollingWindow[TradeBar](2)
                    algorithm.Log("Price Window reset on : {0}".format(algorithm.Time))
                    continue
                

##-----------------Generate insights---------------------------------------------------##   

            else:
                    
                if symbolData.EMACross.IsReady and symbolData.Trade:
     
                    # Don't emit any insights until the VIX history data is processed
                    if VixHandler.vixList and self.TradingWindow: 

                        # If the standard deviation of the 5 day rolling percent change of the VIX spot price is near zero and RSI is not extended in either direction
                        if not algorithm.Portfolio[symbol].Invested:
                            insights.append(Insight.Price(symbol, timedelta(hours=10), InsightDirection.Up, IntradayMagnitude))
                            symbolData.Trade = False
                            
                    
        return insights
        
        
##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        QQQ = SymbolCache.GetSymbol("QQQ")
        
        for added in changes.AddedSecurities:

            # Only create symbol data for QQQ
            symbolData = self.Debugger.get(added.Symbol)
            
            if symbolData is None and added.Symbol == QQQ:
                # Create indicators
                symbolData = DebugSymbolData(added)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.Debugger[added.Symbol] = symbolData
            
            else:
                continue
                

   
##-----------------Return the next weekday from specified date--------------------------------##

    def GetNextWeekday(algorithm, RandomDate):
        RandomDate += OneDay
        
        while RandomDate.weekday() > int(4): # Mon-Fri are 0-4
            RandomDate += OneDay
            
        return RandomDate


##-----------------Annual recalculation of various statistics----------------------------------##
    
    def AnnualRecalc(self, algorithm):
        
        # Once per year update the VIX statistics with the previuos 4000 days data
        if algorithm.Time.date() == self.GetNextWeekday(date(algorithm.Time.year, 1, 3)) and self.TimeBounds[2] <= algorithm.Time.time() <= self.TimeBounds[3]:
            self.Reset = True

        if (self.Reset and algorithm.Time.date() == self.GetNextWeekday(date(algorithm.Time.year, 1, 3)) + OneDay) or self.OnStartUp:
            
            if not self.OnStartUp:
                for symbol, symbolData in self.Debugger.items():
                    symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                    symbolData.GetGapSignal(algorithm)
            
            self.Reset = False
            self.OnStartUp = False

            
            
##-----------------Class to manage asset(s) specific information-------------------------------##

class DebugSymbolData:
    def __init__(self, security):
        
        # Security and Symbol
        self.Security = security
        self.Symbol = security.Symbol
        
        # Rolling Windows
        self.PriceWindow = RollingWindow[TradeBar](2)
        self.CrossWindow = RollingWindow[IndicatorDataPoint](3)
        self.RSIWindow = RollingWindow[IndicatorDataPoint](1)
        
        # Indicators
        self.EMACross = None
        self.RSI = None
        
        # Stat Values and Misc.
        self.Mean = float(1.0)
        self.STD = float(0.005)
        self.Gap = Zero
        self.GapSignal = []
        self.GapDownSignal = []
        self.Trade = True
        

##-----------------Indicators Handler----------------------------------------------------------##   

    def InitializeIndicators(self, algorithm, FastPeriod, SlowPeriod, resolution):
        
        EMAWarmupHistory = self.DesiredHistory(algorithm, self.Symbol, SlowPeriod+1, resolution)
        
        EMAFast = algorithm.EMA(self.Symbol, FastPeriod, resolution)
        EMASlow = algorithm.EMA(self.Symbol, SlowPeriod, resolution)
        
        for time, row in EMAWarmupHistory.loc[self.Symbol].iterrows():
            EMAFast.Update(time, row["close"])
            EMASlow.Update(time, row["close"])
        
        self.EMACross = IndicatorExtensions.Over( EMAFast, EMASlow )
        self.EMACross.Updated += self.EMACrossUpdated
        
        RSIWarmupHistory = self.DesiredHistory(algorithm, self.Symbol, 15, Resolution.Daily)
        
        self.RSI = algorithm.RSI(self.Symbol, 14, MovingAverageType.Simple, Resolution.Daily)
        self.RSI.Updated += self.RSIUpdated
        
        for time, row in RSIWarmupHistory.loc[self.Symbol].iterrows():
            self.RSI.Update(time, row["close"])
        
        algorithm.Debug("Indicators warmed up: EMA: {0} | RSI: {1}".format(self.EMACross.IsReady, self.RSI.IsReady))    
        
    def EMACrossUpdated(self, sender, updated):
        self.CrossWindow.Add(updated)
    
    def RSIUpdated(self, sender, updated):
        self.RSIWindow.Add(updated)

##-----------------Updates historical indicator statstics over the StatPeriod------------------##     

    def StatBounds(self, algorithm, FastPeriod, SlowPeriod, StatPeriod, resolution):
        StatHistory = algorithm.History(self.Symbol, StatPeriod, resolution)
        
        FastValues = []
        SlowValues = []
            
        fast = algorithm.EMA(self.Symbol, FastPeriod, resolution)
        slow = algorithm.EMA(self.Symbol, SlowPeriod, resolution)   
        
        for time, row in StatHistory.loc[self.Symbol].iterrows():
            fast.Update(time, row["close"])
            FastValues.append(fast.Current.Value)
            
            slow.Update(time, row["close"])
            SlowValues.append(slow.Current.Value)
            
        self.Mean = round(np.mean(np.array(FastValues)/np.array(SlowValues)),4)
        self.STD = round(np.std(np.array(FastValues)/np.array(SlowValues)),4)
        
        algorithm.Log("Average Cross: {0} || STD Cross: {1} for {2}".format(self.Mean, self.STD, self.Symbol))
    

##-----------------Captures Gap stats for the symbol-------------------------------------------##    

    def GetGapSignal(self, algorithm):
        history = algorithm.History(self.Symbol, timedelta(days=4000), Resolution.Daily)
        
        GapArray = [Zero]
        for i in range(1, len(history)):
            value = round(history['open'][i]/history['close'][i-1]-1,5)
            GapArray.append(value)
            
        GapAnalysis = pd.DataFrame(index=history.index, columns = ['Gap'])
        GapAnalysis['Gap'] = GapArray
        
        ReturnsArray = np.array(GapAnalysis['Gap'])
        
        PositiveReturnsArray = ReturnsArray[ReturnsArray>0]
        NegativeReturnsArray = ReturnsArray[ReturnsArray<0]
                
        MeanPositiveGap = round(np.mean(PositiveReturnsArray),3)
        STDPositiveGap = round(np.std(PositiveReturnsArray),3)
                
        MeanNegativeGap = round(np.mean(NegativeReturnsArray),3)
        STDNegativeGap= round(np.std(NegativeReturnsArray),3)
                
        PositiveDeviations = []
        NegativeDeviations = []
                
        for i in range (1, 7):
            PositiveDeviations.append(float(round(MeanPositiveGap+i*STDPositiveGap,1)))
        for i in range (-3, -7, -1):
            NegativeDeviations.append(float(round(MeanNegativeGap+i*STDNegativeGap,3)))      
        
        self.GapSignal = PositiveDeviations
        self.GapDownSignal = NegativeDeviations
        
        algorithm.Log("GapUpSignal: {0} || GapDownSignal: {1} for {2}".format(self.GapSignal, self.GapDownSignal, self.Symbol))


##-------------------Method to capture the desired amount of history---------------------------## 

    def DesiredHistory(self, algorithm, symbol, Days, resolution):
        startingDays = Days
        history = algorithm.History(symbol, Days, resolution)
        
        while len(history) < Days:
            startingDays = startingDays + 1
            history = algorithm.History(symbol, startingDays, resolution)
        
        return history