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
Section 1:  SPXL.  3x Leveraged SPY
'''

class SPXL(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self):

        # SymbolData Parameters
        self.FastPeriod = int(5)
        self.SlowPeriod = int(20)
        self.RSIDeviationRange = range(-3,4)
        self.StatPeriod = timedelta(days=2000)
        self.resolution = Resolution.Daily
        self.SPXL = {}

        # Variables
        self.Lag = Zero
        self.Name = "SPXL Alpha Model"
        
        # Lists
        self.TimeBounds = [time(9,31), time(15,55), time(9,31), time(9,32), time(15,59), time(16,00)]
     
        # Booleans
        self.Reset = True
        self.OnStartUp = True
        self.TradingWindow = False

    '''
    Section 1-A:  SPXL insight generation
    ''' 

##-----------------Update-------------------------------------------------------##     

    def Update(self, algorithm, data):

        insights = []
        RemainingTradingDay = max(datetime.combine(algorithm.Time.today(), self.TimeBounds[4]) - datetime.combine(algorithm.Time.today(), algorithm.Time.time()), timedelta(minutes=1))
        
##-----------------Update various statistics annually----------------------------##
        
        self.AnnualRecalc(algorithm)
        
        
##-----------------Manage the trading window----------------------------------------##

        # Check to make sure we allow the first 30 minutes of price action to play out
        if (self.TimeBounds[0] <= algorithm.Time.time() <= self.TimeBounds[5]) and not self.TradingWindow: 
            self.TradingWindow = True
        else:
            self.TradingWindow = False
            
            

##-----------------Generate insights---------------------------------------------------##   

        for symbol, symbolData in self.SPXL.items():
            
            if self.TimeBounds[2] <= algorithm.Time.time() < self.TimeBounds[3]:
                if not symbolData.Trade:
                    algorithm.Log("{0} trade signal reset".format(symbol))
                    symbolData.Trade = True
                    
            # Check that preliminary criteria are met
            if self.ReadyCheck(symbol, symbolData):
            
                # If the EMA cross value is between -1 and -1.5 STD from the mean    
                if symbolData.Mean - 1.5*symbolData.STD < symbolData.EMACross.Current.Value < symbolData.Mean - symbolData.STD:
                    insights.append(Insight.Price(symbol, OneDay, InsightDirection.Up, float(0.0075), None, None, 1.0))
                    symbolData.Trade = False 
                    algorithm.Log("[SPXL]: EMA cross value is between -1 and -1.5 STD from the mean")
                
                # If the previous day VIX close is less than or equal to 3 standard deviations below its 1-year mean and SPXL RSI is showing upward momentum but not overbought conditions and we are not currently invested in SPXL   
                elif VixHandler.PreviousVixClose.Current.Value <= VixHandler.DeviationVix[0] and symbolData.RSIDeviations[3] < symbolData.RSI.Current.Value < symbolData.RSIDeviations[5] and not algorithm.Portfolio[symbol].Invested:
                    insights.append(Insight.Price(symbol, timedelta(days=2), InsightDirection.Up, float(0.0075), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXL]: The previous day VIX close is less than or equal to 3 standard deviations below its 1-year mean and SPXL RSI is showing upward momentum but not overbought conditions and we are not currently invested in SPXL")
                
                # If the overnight gap is between 1 and 2 STD from the mean 
                elif symbolData.GapSignal[2] >= Global.OpenClose[symbol][2] >= symbolData.GapSignal[1]:
                    insights.append(Insight.Price(symbol, timedelta(hours=1), InsightDirection.Up, float(0.001), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXL]: Overnight gap is between 1 and 2 STD from the mean")
                
                # If the percent change of the VIX over the last 5 trading days has been relatively volatile, but the spot VIX is under 1.5 STD from the mean     
                elif ( int(4) < VixHandler.FiveDayVixPercentMoveSTD < int(5) ) and VixHandler.PreviousVixClose.Current.Value < VixHandler.DeviationVix[2]:
                    insights.append(Insight.Price(symbol, OneDay, InsightDirection.Up, float(0.0075), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXL]: The percent change of the VIX over the last 5 trading days has been relatively volatile, but the spot VIX is under 1.5 STD from the mean")
                
                # If the 5-day average of VIX closes is between -10% and -7%    
                elif -int(10) <= VixHandler.SixDayVixAverage < -int(7) and symbolData.Trade:
                    insights.append(Insight.Price(symbol, timedelta(days=1), InsightDirection.Up, float(0.0075), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXL]: The 5-day average of VIX closes is between -10% and -7%")


##-----------------Extend insights separate from Risk Management Module------------------##

        #insights.extend(self.ManagePosition(algorithm))
                    
        return insights
        

##-----------------Create Alpha specific risk management---------------------------------##

    def ManagePosition(self, algorithm):
        
        SPXS = SymbolCache.GetSymbol("SPXS")
        UVXY = SymbolCache.GetSymbol("UVXY")
        
        RiskInsights = []
        RemainingTradingDay = max(datetime.combine(algorithm.Time.today(), self.TimeBounds[4]) - datetime.combine(algorithm.Time.today(), algorithm.Time.time()), timedelta(minutes=1))
        
        if self.TradingWindow:
            for symbol, symbolData in self.SPXL.items():
    
                # Insert comment here
                if algorithm.Portfolio[symbol].UnrealizedProfitPercent <= -float(0.05) :
                    RiskInsights.append(Insight.Price(symbol, RemainingTradingDay, InsightDirection.Flat, float(0.01), None, None, 0.5))
                    symbolData.Trade = False
                    
        return RiskInsights
        
 
##-----------------Checks that certain criteria are met before trading-------------------##        
    def ReadyCheck(self, symbol, symbolData):
        
        if (symbolData.EMACross.IsReady
        and symbolData.Trade 
        and VixHandler.vixList 
        and self.TradingWindow):
            
            return True
            
        else:
            return False

    '''
    Section 1-B:  Universe changes
    '''            
##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        SPXL = SymbolCache.GetSymbol("SPXL")
        
        for added in changes.AddedSecurities:
            # Only create symbol data for SPXL
            symbolData = self.SPXL.get(added.Symbol)
            
            if symbolData is None and added.Symbol == SPXL:
                # Create indicators
                symbolData = SymbolData(added, self.Name, self.RSIDeviationRange)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.SPXL[added.Symbol] = symbolData
            
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
                for symbol, symbolData in self.SPXL.items():
                    symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                    symbolData.GetGapSignal(algorithm)
            
            self.Reset = False
            self.OnStartUp = False
            
        
        
        
'''
Section 2:  SPXS.  -3x leveraged SPY
'''  

class SPXS(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self):

        # SymbolData Parameters
        self.FastPeriod = int(5)
        self.SlowPeriod = int(20)
        self.RSIDeviationRange = range(-2,4)
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

    '''
    Section 2-A:  SPXS insight generation
    '''
##-----------------Update-------------------------------------------------------##     

    def Update(self, algorithm, data):
        
        SPXL = SymbolCache.GetSymbol("SPXL")
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


        for symbol, symbolData in self.SPXS.items():
            
            if self.TimeBounds[2] <= algorithm.Time.time() < self.TimeBounds[3]:
                if not symbolData.Trade:
                    algorithm.Log("{0} trade signal reset".format(symbol))
                    symbolData.Trade = True
                    
            # Check that preliminary criteria are met
            if self.ReadyCheck(symbol, symbolData):
            
                # If SPXS gapped up a reasonable amount, buy the inverse SPXL as a contrarian play - essentially buying the dip
                if symbolData.GapSignal[2] > Global.OpenClose[symbol][2] > symbolData.GapSignal[1]:
                    insights.append(Insight.Price(SPXL, timedelta(days=1), InsightDirection.Up, float(0.01), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXS]: Gapped up a reasonable amount, buy the inverse SPXL as a contrarian play - essentially buying the dip")
                
                # If SPXS is extremely oversold    
                elif (symbolData.Mean - 3*symbolData.STD) < symbolData.EMACross.Current.Value < (symbolData.Mean - 2*symbolData.STD):
                    insights.append(Insight.Price(symbol, timedelta(hours=3), InsightDirection.Up, float(0.01), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXS]: EMA cross is between -2 and -3 standard deviations from the mean")
                
                # If the standard deviation of the 5-day VIX percent change is extremely low and SPXS price momentum is to the upside
                elif VixHandler.FiveDayVixPercentMoveSTD < int(2) and symbolData.EMACross.Current.Value > (symbolData.Mean - 0*symbolData.STD):
                    insights.append(Insight.Price(symbol, timedelta(days=3), InsightDirection.Up, float(0.01), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXS]: The standard deviation of the 5-day VIX percent change is extremely low and SPXS price momentum is to the upside")
                
                # If SPXS gapped up immensely    
                elif  symbolData.GapSignal[4] > Global.OpenClose[symbol][2] > symbolData.GapSignal[3]:
                    insights.append(Insight.Price(symbol, timedelta(days=2), InsightDirection.Up, float(0.01), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXS]: Gapped up immensely")
                
                # If RSI is elevated and the previous 2 RSI points are rising, SPXS is trending upward, the standard deviation of the 5-day VIX percent change is normal, and there is not currently an open SPXL position  
                elif (symbolData.RSIDeviations[4] > symbolData.RSI.Current.Value > symbolData.RSIDeviations[3] 
                        and symbolData.RSIWindow[0] < symbolData.RSIWindow[1] 
                        and symbolData.EMACross.Current.Value > (symbolData.Mean + 0.5*symbolData.STD) 
                        and  int(3) < VixHandler.FiveDayVixPercentMoveSTD < int(8) 
                        and not algorithm.Portfolio[SPXL].Invested):
                            
                    insights.append(Insight.Price(SPXL, timedelta(days=4), InsightDirection.Up, float(0.01), None, None, 1.0))
                    symbolData.Trade = False
                    algorithm.Log("[SPXS]: RSI is elevated and the previous 2 RSI points are rising, SPXS is trending upward, the standard deviation of the 5-day VIX percent change is normal, and there is not currently an open SPXL position [ Current SPXS RSI: {0} ]".format(symbolData.RSI.Current.Value))
                    


##-----------------Extend insights separate from Risk Management Module------------------##

        #insights.extend(self.ManagePosition(algorithm))
                    
        return insights
        

##-----------------Create Alpha specific risk management---------------------------------##

    def ManagePosition(self, algorithm):
        
        SPXL = SymbolCache.GetSymbol("SPXS")
        UVXY = SymbolCache.GetSymbol("UVXY")
        
        RiskInsights = []
        RemainingTradingDay = max(datetime.combine(algorithm.Time.today(), self.TimeBounds[4]) - datetime.combine(algorithm.Time.today(), algorithm.Time.time()), timedelta(minutes=1))
        
        if self.TradingWindow:
            for symbol, symbolData in self.SPXS.items():
    
                # Insert comment here
                if algorithm.Portfolio[symbol].UnrealizedProfitPercent <= -float(0.04) :
                    RiskInsights.append(Insight.Price(UVXY, RemainingTradingDay, InsightDirection.Down, float(0.01), None, None, 0.5))
                    symbolData.Trade = False
                    
        return RiskInsights
        
        
##-----------------Checks that certain criteria are met before trading-------------------##        
    def ReadyCheck(self, symbol, symbolData):
        
        if (symbolData.EMACross.IsReady
        and symbolData.Trade 
        and VixHandler.vixList 
        and self.TradingWindow):
            
            return True
            
        else:
            return False
            
    '''
    Section 2-B:  Universe changes
    '''            
##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        SPXS = SymbolCache.GetSymbol("SPXS")
        
        for added in changes.AddedSecurities:
            # Only create symbol data for SPXS
            symbolData = self.SPXS.get(added.Symbol)
            
            if symbolData is None and added.Symbol == SPXS:
                # Create indicators
                symbolData = SymbolData(added, self.Name, self.RSIDeviationRange)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.SPXS[added.Symbol] = symbolData
            
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
                for symbol, symbolData in self.SPXS.items():
                    symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                    symbolData.GetGapSignal(algorithm)
            
            self.Reset = False
            self.OnStartUp = False
    
            

'''
Section 3: Class to store security specific indicators and statistics
'''

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
            PositiveDeviations.append(float(round(MeanPositiveGap+i*STDPositiveGap,3)))
        for i in range (-1, -7, -1):
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