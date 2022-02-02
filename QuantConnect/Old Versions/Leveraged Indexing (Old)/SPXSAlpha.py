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

##-------------------Global variables------------------------------------------##

Zero = int(0)
One = int(1)
OneDay = timedelta(days=1)


##-------------------Insight Parameters----------------------------------------##

RemainingTradingDay = timedelta(hours=6.15)
IntradayMagnitude = float(0.01)
ShortTermMagnitude = float(0.001)

class SPXS(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self):

        # SymbolData Parameters
        self.FastPeriod = int(5)
        self.SlowPeriod = int(20)
        self.StatPeriod = timedelta(days=2000)
        self.resolution = Resolution.Daily
        self.SPXS = {}

        # Variables
        self.Lag = Zero
        self.Name = "SPXS Alpha Model"
        
        # Lists
        self.TimeBounds = [time(9,31), time(15,55), time(9,31), time(9,32), time(15,59), time(16,00)]
     
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

        # Within the first minute of market open capature the gap change for SPXS
        for symbol, symbolData in self.SPXS.items():
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
                        algorithm.Log("SPXS Gap Calculated at {1}: {0}".format(symbolData.Gap, algorithm.Time))
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
                
                SPXL = SymbolCache.GetSymbol("SPXL")
                
                # Don't emit any insights until the VIX history data is processed, the market is open, indicators are ready, and the trade trigger is set to true
                if symbolData.EMACross.IsReady and symbolData.Trade and VixHandler.vixList:
                
                    # If SPXS gapped up a reasonable amount, buy the inverse SPXL as a contrarian play - essentially buying the dip
                    if symbolData.GapSignal[2] > symbolData.Gap > symbolData.GapSignal[1]:
                        insights.append(Insight.Price(SPXL, timedelta(days=1), InsightDirection.Up, IntradayMagnitude))
                        symbolData.Trade = False
                        algorithm.Log("SPXS gapped up a reasonable amount, buy the inverse SPXL as a contrarian play - essentially buying the dip")
                    
                    # If SPXS is extremely oversold    
                    elif (symbolData.Mean - 3*symbolData.STD) < symbolData.EMACross.Current.Value < (symbolData.Mean - 2*symbolData.STD):
                        insights.append(Insight.Price(symbol, timedelta(hours=3), InsightDirection.Up, IntradayMagnitude))
                        symbolData.Trade = False
                        algorithm.Log("SPXS is extremely oversold")
                    
                    # If the standard deviation of the 5-day VIX percent change is extremely low and SPXS price momentum is to the upside
                    elif VixHandler.FiveDayVixPercentMoveSTD < int(2) and symbolData.EMACross.Current.Value > (symbolData.Mean - 0*symbolData.STD):
                        insights.append(Insight.Price(symbol, timedelta(days=3), InsightDirection.Up, IntradayMagnitude))
                        symbolData.Trade = False
                        algorithm.Log("The standard deviation of the 5-day VIX percent change is extremely low and SPXS price momentum is to the upside")
                    
                    # If SPXS gapped up immensely    
                    elif  symbolData.GapSignal[4] > symbolData.Gap > symbolData.GapSignal[3]:
                        insights.append(Insight.Price(symbol, timedelta(days=2), InsightDirection.Up, IntradayMagnitude))
                        symbolData.Trade = False
                        algorithm.Log("SPXS gapped up immensely")
                    
                    # If RSI is elevated and the previous 2 RSI points are rising, SPXS is trending upward, the standard deviation of the 5-day VIX percent change is normal, and there is not currently an open SPXL position  
                    elif (symbolData.RSIDeviations[4] > symbolData.RSI.Current.Value > symbolData.RSIDeviations[3] and symbolData.RSIWindow[0] < symbolData.RSIWindow[1] 
                            and symbolData.EMACross.Current.Value > (symbolData.Mean + 0.5*symbolData.STD) and  int(3) < VixHandler.FiveDayVixPercentMoveSTD < int(8) and not algorithm.Portfolio[SPXL].Invested):
                                
                        insights.append(Insight.Price(SPXL, timedelta(days=4), InsightDirection.Up, IntradayMagnitude))
                        symbolData.Trade = False
                        algorithm.Log("RSI is elevated and the previous 2 RSI points are rising, SPXS is trending upward, the standard deviation of the 5-day VIX percent change is normal, and there is not currently an open SPXL position [ Current SPXS RSI: {0} ]".format(symbolData.RSI.Current.Value))
                        


##-----------------Extend insights separate from Risk Management Module------------------##

        #insights.extend(self.ManagePosition(algorithm))
                    
        return insights
        

##-----------------Create Alpha specific risk management---------------------------------##

    def ManagePosition(self, algorithm):
        
        SPXS = SymbolCache.GetSymbol("SPXS")
        
        RiskInsights = []
        
        for symbol, symbolData in self.SPXS.items():
            if self.TradingWindow and algorithm.Portfolio[symbol].Invested:
                continue
        
        return RiskInsights
        
        
        
##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        SPXS = SymbolCache.GetSymbol("SPXS")
        
        for added in changes.AddedSecurities:
            # Only create symbol data for SPXS
            symbolData = self.SPXS.get(added.Symbol)
            
            if symbolData is None and added.Symbol == SPXS:
                # Create indicators
                symbolData = SPXSSymbolData(added)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.SPXS[added.Symbol] = symbolData
            
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
                for symbol, symbolData in self.SPXS.items():
                    symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                    symbolData.GetGapSignal(algorithm)
            
            self.Reset = False
            self.OnStartUp = False
    
            
            
##-----------------Class to manage asset(s) specific information-------------------------------##

class SPXSSymbolData:
    def __init__(self, security):
        self.Security = security
        self.Symbol = security.Symbol
        self.PriceWindow = RollingWindow[TradeBar](2)
        self.CrossWindow = RollingWindow[IndicatorDataPoint](3)
        self.RSIWindow = RollingWindow[IndicatorDataPoint](2)
        self.EMACross = None
        self.RSI = None
        self.Mean = float(1.0)
        self.STD = float(0.005)
        self.MeanRSI = float(50)
        self.STDRSI = float(10)
        self.Gap = Zero
        self.GapSignal = []
        self.GapDownSignal = []
        self.RSIDeviations = []
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
            PositiveDeviations.append(float(round(MeanPositiveGap+i*STDPositiveGap,3)))
        for i in range (-1, -7, -1):
            NegativeDeviations.append(float(round(MeanNegativeGap+i*STDNegativeGap,3)))      
        
        self.GapSignal = PositiveDeviations
        self.GapDownSignal = NegativeDeviations
        
        self.RSIBounds(algorithm, history)
        
        algorithm.Log("GapUpSignal: {0} || GapDownSignal: {1} for {2}".format(self.GapSignal, self.GapDownSignal, self.Symbol))
    
    

##-----------------Derives RSI boundaries------------------------------------------------------##

    def RSIBounds(self, algorithm, history):
        
        rsi = algorithm.RSI(self.Symbol, 14, MovingAverageType.Simple, Resolution.Daily)
        RSIValues = []
        
        for time, row in history.loc[self.Symbol].iterrows():
            rsi.Update(time, row["close"])
            RSIValues.append(rsi.Current.Value)        
        
        
        Average_RSI_Daily = round(float(np.mean(RSIValues)),4)
        STD_RSI_Daily = round(float(np.std(RSIValues)),4)
        Deviations_RSI_Daily = []

        # Standard Deviations
        for i in range(-2,4):
            Deviations_RSI_Daily.append(Average_RSI_Daily + i*STD_RSI_Daily)

        self.MeanRSI = Average_RSI_Daily
        self.STDRSI = STD_RSI_Daily            
        self.RSIDeviations = Deviations_RSI_Daily
        
        algorithm.Log("Mean RSI: {0} || RSI STD: {1} for {2}".format(self.MeanRSI, self.STDRSI, self.Symbol))
        algorithm.Log("RSI Deviations: {0}, {1}, {2}, {3}, {4}, {5}".format( self.RSIDeviations[0], self.RSIDeviations[1], self.RSIDeviations[2], self.RSIDeviations[3], self.RSIDeviations[4], self.RSIDeviations[5] ))
    
        
##-------------------Method to capture the desired amount of history---------------------------##  

    def DesiredHistory(self, algorithm, symbol, Days, resolution):
        startingDays = Days
        history = algorithm.History(symbol, Days, resolution)
        
        while len(history) < Days:
            startingDays = startingDays + 1
            history = algorithm.History(symbol, startingDays, resolution)
        
        return history