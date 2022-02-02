'''
Section 0:  Imports
'''

##-------------------Imports---------------------------------------------------##
import numpy as np
import pandas as pd
from datetime import *

from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Algorithm.Framework")

from QuantConnect import Resolution, Extensions
from QuantConnect.Algorithm.Framework.Alphas import *

from Global import VixHandler
from Global import Global

##-------------------Global variables------------------------------------------##

Zero = int(0)
One = int(1)
OneDay = timedelta(days=1)

'''
Section 1:  UVXY - Long.  1.5x Leveraged VIX near-term futures basket
'''

class LongVol(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self, StatPeriod):

        # SymbolData Parameters
        self.FastPeriod = int(2)
        self.SlowPeriod = int(4)
        self.RSIDeviationRange = np.arange(-1,3,0.5)
        self.StatPeriod = StatPeriod
        self.resolution = Resolution.Hour
        self.LongVIX = {}

        # Variables
        self.Lag = Zero
        self.Name = "Long UVXY Alpha Model"
        
        # Lists
        self.TimeBounds = [time(9,45), time(12,00), time(9,31), time(9,32), time(15,59), time(16,00)]
     
        # Booleans
        self.Reset = True
        self.OnStartUp = True
        self.TradingWindow = False

    '''
    Section 1-A:  UVXY - Long insight generation
    '''
    
##-----------------Update-------------------------------------------------------##     

    def Update(self, algorithm, data):
        
        QQQ = SymbolCache.GetSymbol("QQQ")
        TQQQ = SymbolCache.GetSymbol("TQQQ")
        
        insights = []
        
##-----------------Update various statistics annually----------------------------##
            
        self.AnnualRecalc(algorithm)
        
                
##-----------------Manage the trading window----------------------------------------##

        # Check to make sure we allow the first 30 minutes of price action to play out
        if (self.TimeBounds[0] <= algorithm.Time.time() <= self.TimeBounds[5]) and not self.TradingWindow: 
            self.TradingWindow = True
        else:
            self.TradingWindow = False
                

##-----------------Generate insights---------------------------------------------------##   

        for symbol, symbolData in self.LongVIX.items():
            
            if self.TimeBounds[2] <= algorithm.Time.time() < self.TimeBounds[3]:
                if not symbolData.Trade:
                    algorithm.Log("{0} trade signal reset".format(symbol))
                    symbolData.Trade = True
 
            # Check that preliminary criteria are met
            if self.ReadyCheck(symbol, symbolData, algorithm): 
                
                RemainingTradingDay = datetime.combine(algorithm.Time.today(), self.TimeBounds[4]) - datetime.combine(algorithm.Time.today(), algorithm.Time.time())
                
                # If the previous day VIX % move was between +3 and +4 standard deviations from the mean
                if ( VixHandler.DeviationVixChange[6] <= VixHandler.vixPercentMoveList[-1] < VixHandler.DeviationVixChange[7] ):  
                    
                    # And we are not currently invested and UVXY didn't gap up more than 10%  
                    if (not algorithm.Portfolio[symbol].Invested 
                        and symbolData.GapSignal[0] >= Global.OpenClose[symbol][2] > Zero):
                            
                        insights.append(Insight.Price(symbol, RemainingTradingDay, InsightDirection.Up, float(0.05), None, None, 1.0))
                        symbolData.Trade = False
                        algorithm.Log("[LONG UVXY]: The previous day VIX % move was between +3 and +4 standard deviations from the mean and we are not currently invested and UVXY didn't gap up more than 10%")

                # If UVXY gapped down more than 4 standard deviations from its average gap down
                elif Global.OpenClose[symbol][2] <= symbolData.GapDownSignal[3]: 
                    insights.append(Insight.Price(symbol, RemainingTradingDay, InsightDirection.Up, float(0.05), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[LONG UVXY]: UVXY gapped down more than 4 standard deviations from its average gap down")

                # If the standard deviation of the 5 day rolling percent change of the VIX spot price is near zero and RSI is not extended in either direction
                elif (int(0) < VixHandler.FiveDayVixPercentMoveSTD < int(2) 
                    and not algorithm.Portfolio[symbol].Invested 
                    and symbolData.RSIDeviations[7] >= symbolData.RSI.Current.Value >= symbolData.RSIDeviations[0]
                    ):
                    
                        # If the current portfolio drawdown is less than 12.5%
                        if Global.PortfolioDrawdown > -float(0.125):
                            insights.append(Insight.Price(symbol, timedelta(hours=10), InsightDirection.Up, float(0.05), None, None, 1.0))
                            symbolData.Trade = False
                            algorithm.Log("[LONG UVXY]: The standard deviation of the 5-day rolling percent change of the VIX spot price is near zero, RSI is not extended in either direction and portfolio drawdown is above -12.5% [ Current UVXY RSI: {0} ]".format(symbolData.RSI.Current.Value))
                        
                        # Take a long-short position if the portfolio drawdown is greater than or equal to 12.5% because the market is likely experiencing very frequent high magnitude swings    
                        else:
                            insights.append(Insight.Price(symbol, timedelta(hours=10), InsightDirection.Up, float(0.05), None, None, 0.5))
                            insights.append(Insight.Price(TQQQ, timedelta(hours=10), InsightDirection.Up, float(0.05), None, None, 0.5))
                            symbolData.Trade = False
                            algorithm.Log("[LONG UVXY]: The standard deviation of the 5-day rolling percent change of the VIX spot price is near zero, RSI is not extended in either direction and portfolio drawdown is below -12.5% [ Current UVXY RSI: {0} ]".format(symbolData.RSI.Current.Value))
                            

                # If the moving average cross over is between 4 and 5 standard deviations below its long term average value
                elif symbolData.Mean - (5*symbolData.STD) <= symbolData.EMACross.Current.Value <= symbolData.Mean - (4*symbolData.STD):
                    insights.append(Insight.Price(symbol, timedelta(hours=1.25), InsightDirection.Up, float(0.01), None, None, 1.0))
                            
                    
        
        

##-----------------Extend insights separate from Risk Management Module------------------##

        insights.extend(self.ManagePosition(algorithm))
                    
        return insights
        

##-----------------Create Alpha specific risk management---------------------------------##

    def ManagePosition(self, algorithm):
        
        SPXL = SymbolCache.GetSymbol("SPXL")
        TQQQ = SymbolCache.GetSymbol("TQQQ")
        
        RemainingTradingDay = datetime.combine(algorithm.Time.today(), self.TimeBounds[4]) - datetime.combine(algorithm.Time.today(), algorithm.Time.time())
        
        RiskInsights = []

        if self.TradingWindow:
            for symbol, symbolData in self.LongVIX.items():
    
                # Insert comment here
                if algorithm.Portfolio[symbol].UnrealizedProfitPercent <= -float(0.045) and algorithm.Portfolio[symbol].IsLong and not algorithm.Portfolio[SPXL].Invested and int(0) < VixHandler.FiveDayVixPercentMoveSTD < int(2):
                    RiskInsights.append(Insight.Price(SPXL, timedelta(days=2), InsightDirection.Up, float(0.01), None, None, 0.5))
                    symbolData.Trade = False
                    
        return RiskInsights
        

##-----------------Checks that certain criteria are met before trading-------------------##        
    def ReadyCheck(self, symbol, symbolData, algorithm):
        
        if (
        symbolData.EMACross.IsReady
        and symbolData.Trade 
        and VixHandler.vixList 
        and self.TradingWindow 
        ):
            
            return True
            
        else:
            return False
            
    '''
    Section 1-B:  Universe changes
    '''
    
##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        UVXY = SymbolCache.GetSymbol("UVXY")
        
        for added in changes.AddedSecurities:

            # Only create symbol data for this alpha
            symbolData = self.LongVIX.get(added.Symbol)
            
            if symbolData is None and added.Symbol == UVXY:
                
                # Create indicators
                # symbolData = LongVolSymbolData(added)
                symbolData = SymbolData(added, self.Name, self.RSIDeviationRange)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.LongVIX[added.Symbol] = symbolData
            
            else:
                continue
                

    '''
    Section 1-C:  Recalculates indicator and price statistics annually
    '''

##-----------------Annual recalculation of various statistics----------------------------------##
    
    def AnnualRecalc(self, algorithm):
        
        # Once per year update the VIX statistics with the previuos 4000 days data
        if algorithm.Time.date() == MiscMethods.GetNextWeekday(date(algorithm.Time.year, 1, 3)) and self.TimeBounds[2] <= algorithm.Time.time() <= self.TimeBounds[3]:
            self.Reset = True

        if (self.Reset and algorithm.Time.date() == MiscMethods.GetNextWeekday(date(algorithm.Time.year, 1, 3)) + OneDay) or self.OnStartUp:
            
            if not self.OnStartUp:
                for symbol, symbolData in self.LongVIX.items():
                    symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                    symbolData.GetGapSignal(algorithm)
            
            self.Reset = False
            self.OnStartUp = False
        

'''
Section 2:  UVXY - Short.  -1.5x Leveraged VIX near-term futures basket
'''

class ShortVol(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self, StatPeriod):

        # SymbolData Parameters
        self.FastPeriod = int(5)
        self.SlowPeriod = int(15)
        self.RSIDeviationRange = np.arange(-1,3,0.5)
        self.StatPeriod = StatPeriod
        self.resolution = Resolution.Hour
        self.ShortVIX = {}

        # Variables
        self.Lag = Zero
        self.Name = "Short UVXY Alpha Model"
        
        # Lists
        self.TimeBounds = [time(10,00), time(12,00), time(9,31), time(9,32), time(15,59), time(16,00)]
     
        # Booleans
        self.Reset = True
        self.OnStartUp = True
        self.TradingWindow = False
        self.Daily = False

    '''
    Section 2-A:  UVXY - Short insight generation
    '''
    
##-----------------Update-------------------------------------------------------##

    def Update(self, algorithm, data):
        
        QQQ = SymbolCache.GetSymbol("QQQ")
        TQQQ = SymbolCache.GetSymbol("TQQQ")
        SQQQ = SymbolCache.GetSymbol("SQQQ")
        SPXL = SymbolCache.GetSymbol("SPXL")
        SPXS = SymbolCache.GetSymbol("SPXS")
        
        RemainingTradingTime = max(datetime.combine(algorithm.Time.today(), time(15,59)) - datetime.combine(algorithm.Time.today(), algorithm.Time.time()), timedelta(minutes=10))
        
        insights = []
        
##-----------------Update various statistics annually----------------------------##
            
        self.AnnualRecalc(algorithm)

                
##-----------------Manage the trading window----------------------------------------##

        # Check to make sure we allow the first 30 minutes of price action to play out
        if (self.TimeBounds[0] <= algorithm.Time.time() < self.TimeBounds[5]) and not self.TradingWindow: 
            self.TradingWindow = True
        else:
            self.TradingWindow = False
            

                

##-----------------Generate insights---------------------------------------------------##   

        for symbol, symbolData in self.ShortVIX.items():
            
            if self.TimeBounds[2] <= algorithm.Time.time() < self.TimeBounds[3]:
                if not symbolData.Trade:
                    algorithm.Log("{0} trade signal reset".format(symbol))
                    symbolData.Trade = True
 
            # Check that preliminary criteria are met
            if self.ReadyCheck(symbol, symbolData, algorithm): 
                
                # If EMACross is negative but not extended, RSI is greater than 2 stdev above its mean, UVXY gapped down, but less than 1 STD from the mean gap down, the VIX index isn't fluctuating wildly and there are currently no short UVXY positions
                if (( (symbolData.Mean - 1*symbolData.STD) < symbolData.EMACross.Current.Value < (symbolData.Mean - 0*symbolData.STD) )
                    and (symbolData.RSIDeviations[5] <= symbolData.RSI.Current.Value)
                    and (symbolData.GapDownSignal[0] < Global.OpenClose[symbol][2] < Zero)
                    and round(VixHandler.FiveDayVixPercentMoveSTD,0) < int(15) 
                    and not algorithm.Portfolio[symbol].Invested):
                    

                    insights.append(Insight.Price(symbol, timedelta(days=5), InsightDirection.Down, -float(0.01), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SHORT UVXY]: EMACross is negative but not extended, RSI is trending higher but not extended, UVXY gapped down, but less than 1 STD from the mean gap down, the VIX index isn't fluctuating wildly and there are currently no short UVXY positions")
                
                # If price is trending down, the current price is 3.5% below the average of the open and previous close, RSI is above half the average, and no other assets are being held
                elif ( symbolData.EMACross.Current.Value < (symbolData.Mean - 0.25*symbolData.STD) 
                    and algorithm.Securities[symbol].Price < ((Global.OpenClose[symbol][0] + Global.OpenClose[symbol][1])/2) * 0.975
                    and symbolData.MeanRSI/2 < symbolData.RSI.Current.Value
                    and not algorithm.Portfolio[symbol].Invested
                    ):
                        
                        # If the current portfolio drawdown is less than 12.5%
                        if Global.PortfolioDrawdown > -float(0.125):
                            insights.append(Insight.Price(symbol, RemainingTradingTime, InsightDirection.Down, -float(0.01), None, None, 1.0))
                            symbolData.Trade = False
                            algorithm.Log("[SHORT UVXY]: EMACross is trending under the mean, RSI is above half of the long term mean RSI, the current price is 2.5% less than the mean of the previous close and recent open, the portfolio drawdown is greater than -12.5%, and UVXY is not currently a holding")
                        
                        # Take a long-short position if the portfolio drawdown is greater than or equal to 12.5% because the market is likely experiencing very frequent high magnitude swings    
                        else:
                            insights.append(Insight.Price(symbol, RemainingTradingTime, InsightDirection.Down, -float(0.01), None, None, 0.5))
                            insights.append(Insight.Price(SQQQ, RemainingTradingTime, InsightDirection.Up, float(0.01), None, None, 0.5))
                            symbolData.Trade = False
                            algorithm.Log("[SHORT UVXY]: EMACross is trending under the mean, RSI is above half of the long term mean RSI, the current price is 2.5% less than the mean of the previous close and recent open, the portfolio drawdown is less than -12.5%, and UVXY is not currently a holding")
                        
                    
                        
                        
    
##-----------------Extend insights separate from Risk Management Module------------------##

        insights.extend(self.ManagePosition(algorithm, symbol, symbolData))
                    
        return insights
        

##-----------------Create Alpha specific risk management---------------------------------##

    def ManagePosition(self, algorithm, symbol, symbolData):
        
        TQQQ = SymbolCache.GetSymbol("TQQQ")
        SPXS = SymbolCache.GetSymbol("SPXS")
        
        RemainingTradingTime = max(datetime.combine(algorithm.Time.today(), time(15,59)) - datetime.combine(algorithm.Time.today(), algorithm.Time.time()), timedelta(minutes=10))
            
        RiskInsights = []
            
        if (
            algorithm.Portfolio[symbol].IsShort
            ):

            # If we are short UVXY and the moving average crossover approaches 1 standard deviation from the mean then reposition long UVXY
            if symbolData.EMACross.Current.Value > (symbolData.Mean + 0.75*symbolData.STD):
                RiskInsights.append(Insight.Price(symbol, RemainingTradingTime, InsightDirection.Up, float(0.01), None, None, 1.0))
                symbolData.Trade = False
                algorithm.Log("[SHORT UVXY] Switched to long UVXY due to extended crossover value")

        return RiskInsights
        
     

##-----------------Checks that certain criteria are met before trading-------------------##        
    def ReadyCheck(self, symbol, symbolData, algorithm):
        
        if (
        symbolData.EMACross.IsReady
        and symbolData.Trade 
        and VixHandler.vixList 
        and self.TradingWindow
        and not algorithm.Portfolio[symbol].IsLong
        ):
            
            return True
            
        else:
            return False
            
    '''
    Section 2-B:  Universe changes
    '''
    
##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        UVXY = SymbolCache.GetSymbol("UVXY")
        
        for added in changes.AddedSecurities:

            # Only create symbol data for this alpha
            symbolData = self.ShortVIX.get(added.Symbol)
            
            if symbolData is None and added.Symbol == UVXY:
                # Create indicators
                # symbolData = ShortVolSymbolData(added)
                symbolData = SymbolData(added, self.Name, self.RSIDeviationRange)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.ShortVIX[added.Symbol] = symbolData
            
            else:
                continue
                
    '''
    Section 2-C:  Recalculates indicator and price statistics annually
    ''' 

##-----------------Annual recalculation of various statistics----------------------------------##
    
    def AnnualRecalc(self, algorithm):
        
        # Once per year update the VIX statistics with the previuos 4000 days data
        if algorithm.Time.date() == MiscMethods.GetNextWeekday(date(algorithm.Time.year, 1, 3)) and self.TimeBounds[2] <= algorithm.Time.time() <= self.TimeBounds[3]:
            self.Reset = True

        if (self.Reset and algorithm.Time.date() == MiscMethods.GetNextWeekday(date(algorithm.Time.year, 1, 3)) + OneDay) or self.OnStartUp:
            
            if not self.OnStartUp:
                for symbol, symbolData in self.ShortVIX.items():
                    symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                    symbolData.GetGapSignal(algorithm)
            
            self.Reset = False
            self.OnStartUp = False
        

        
##-----------------Class to manage asset(s) specific information-------------------------------##

class SymbolData:
    def __init__(self, security, Name, DevRange):
        self.Name = Name
        self.Security = security
        self.Symbol = security.Symbol
        self.CrossWindow = RollingWindow[IndicatorDataPoint](3)
        self.RSIWindow = RollingWindow[IndicatorDataPoint](2)
        self.EMACross = None
        self.RSI = None
        self.Mean = float(1.0)
        self.STD = float(0.005)
        self.MeanRSI = float(50)
        self.STDRSI = float(10)
        self.GapSignal = []
        self.GapDownSignal = []
        self.RSIDeviations = []
        self.RSIDevRange = DevRange
        self.Trade = True

    '''
    Section 3-A: Initialize indicators, rolling windows, and warm up all of the above
    '''        
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
        
        RSIWarmupHistory = self.DesiredHistory(algorithm, self.Symbol, 60, Resolution.Daily)
        
        self.RSI = algorithm.RSI(self.Symbol, 14, MovingAverageType.Simple, Resolution.Daily)
        self.RSI.Updated += self.RSIUpdated
        
        for time, row in RSIWarmupHistory.loc[self.Symbol].iterrows():
            self.RSI.Update(time, row["close"])
            
    def EMACrossUpdated(self, sender, updated):
        self.CrossWindow.Add(updated)
    
    def RSIUpdated(self, sender, updated):
        self.RSIWindow.Add(updated)
        

    '''
    Section 3-B: Perform stat analysis on moving average indicators
    '''        

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
        
        algorithm.Log("{2}: Average Cross: {0} || STD Cross: {1}".format(self.Mean, self.STD, self.Name))
    

    '''
    Section 3-C: Perform stat analysis on price data
    '''    

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
            
        self.RSIBounds(algorithm, history)
        
        algorithm.Log("{2}: GapUpSignal: {0} || GapDownSignal: {1}".format(self.GapSignal, self.GapDownSignal, self.Name))
    
    
    '''
    Section 3-D: Perform stat analysis on RSI indicators
    '''
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
        for i in self.RSIDevRange:
            Deviations_RSI_Daily.append(round(Average_RSI_Daily + i*STD_RSI_Daily,4))

        self.MeanRSI = Average_RSI_Daily
        self.STDRSI = STD_RSI_Daily            
        self.RSIDeviations = Deviations_RSI_Daily
        
        algorithm.Log("{2}: Mean RSI: {0} || RSI STD: {1}".format(self.MeanRSI, self.STDRSI, self.Name))
        algorithm.Log(f"{self.Name} RSI Deviations: {self.RSIDeviations}")
    

    '''
    Section 3-E: Modified history call to ensure the exact amount of data is obtained.
    '''        
##-------------------Method to capture the desired amount of history---------------------------##  

    def DesiredHistory(self, algorithm, symbol, Days, resolution):
        startingDays = Days
        history = algorithm.History(symbol, Days, resolution)
        
        while len(history) < Days:
            startingDays = startingDays + 1
            history = algorithm.History(symbol, startingDays, resolution)
        
        return history
        
        
'''
Section 4:  Misc methods
'''
    
class MiscMethods:
    
    def __init__(self):
        pass
    

    '''
    Section 4-A:  Takes a random date and returns the next weekday from that date
    '''    
##-----------------Return the next weekday from specified date--------------------------------##

    def GetNextWeekday(RandomDate):
        RandomDate += OneDay
        
        while RandomDate.weekday() > int(4): # Mon-Fri are 0-4
            RandomDate += OneDay
            
        return RandomDate