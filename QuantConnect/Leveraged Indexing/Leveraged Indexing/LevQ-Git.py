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
Section 1:  TQQQ.  3x Leveraged QQQ
'''

class TQQQ(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self):

        # SymbolData Parameters
        self.FastPeriod = int(1)
        self.SlowPeriod = int(2)
        self.RSIDeviationRange = range(-5,5)
        self.StatPeriod = timedelta(days=2)
        self.resolution = Resolution.Daily
        self.TQQQ = {}
        self.OpenOrders = []

        # Variables
        self.Lag = Zero
        self.Name = "TQQQ Alpha Model"

        # Lists
        self.TimeBounds = [time(9,31), time(15,55), time(9,31), time(9,32), time(15,59), time(16,00)]

        # Booleans
        self.Reset = True
        self.OnStartUp = True

    '''
    Section 1-A:  TQQQ insight generation
    '''

##-----------------Update-------------------------------------------------------##

    def Update(self, algorithm, data):

        SQQQ = SymbolCache.GetSymbol("SQQQ")

        insights = []


##-----------------Update various statistics annually----------------------------##

        self.AnnualRecalc(algorithm)



##-----------------Generate insights---------------------------------------------------##

        for symbol, symbolData in self.TQQQ.items():

            # Check that preliminary criteria are met
            if self.ReadyCheck(algorithm, symbol, symbolData):
                'Insights are intellectual property'
                pass


##-----------------Extend insights separate from Risk Management Module------------------##

        insights.extend(self.ManagePosition(algorithm))

        return insights


##-----------------Create Alpha specific risk management---------------------------------##

    def ManagePosition(self, algorithm):

        SQQQ = SymbolCache.GetSymbol("SQQQ")
        SPXS = SymbolCache.GetSymbol("SPXS")

        RiskInsights = []

        for symbol, symbolData in self.TQQQ.items():
            if Global.MarketIsOpen and not algorithm.Portfolio[SPXS].Invested:
                if algorithm.Portfolio[symbol].UnrealizedProfitPercent <= -float(0.075):
                    RiskInsights.append(Insight.Price(SPXS, timedelta(hours=17.5), InsightDirection.Up, float(0.01), None, None, 0.5))

        return RiskInsights


##-----------------Checks that certain criteria are met before trading-------------------##
    def ReadyCheck(self, algorithm, symbol, symbolData):
        self.OpenOrders = algorithm.Transactions.GetOpenOrders(symbol)

        if (symbolData.EMACross.IsReady
        and Global.TradeTriggers[symbol]
        and VixHandler.vixList
        and Global.MarketIsOpen
        and not self.OpenOrders
        ):

            return True

        else:
            return False

    '''
    Section 1-B:  Universe changes
    '''
##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        TQQQ = SymbolCache.GetSymbol("TQQQ")

        for added in changes.AddedSecurities:
            # Only create symbol data for SPXS
            symbolData = self.TQQQ.get(added.Symbol)

            if symbolData is None and added.Symbol == TQQQ:
                # Create indicators
                symbolData = SymbolData(added, self.Name, self.RSIDeviationRange)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.TQQQ[added.Symbol] = symbolData

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
                for symbol, symbolData in self.TQQQ.items():
                    symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                    symbolData.GetGapSignal(algorithm)

            self.Reset = False
            self.OnStartUp = False


'''
Section 2:  SQQQ.  -3x Leveraged QQQ
'''

class SQQQ(AlphaModel):

##-----------------Initialize variables, lists, etc---------------------------##

    def __init__(self):

        # SymbolData Parameters
        self.FastPeriod = int(1)
        self.SlowPeriod = int(22)
        self.RSIDeviationRange = range(-6,46)
        self.StatPeriod = timedelta(days=2)
        self.resolution = Resolution.Daily
        self.SQQQ = {}
        self.OpenOrders = []

        # Variables
        self.Lag = Zero
        self.Name = "SQQQ Alpha Model"

        # Lists
        self.TimeBounds = [time(9,31), time(15,55), time(9,31), time(9,32), time(15,59), time(16,00)]

        # Booleans
        self.Reset = True
        self.OnStartUp = True

    '''
    Section 2-A:  SQQQ insight generation
    '''

##-----------------Update-------------------------------------------------------##

    def Update(self, algorithm, data):

        TQQQ = SymbolCache.GetSymbol("TQQQ")
        insights = []


##-----------------Update various statistics annually----------------------------##

        self.AnnualRecalc(algorithm)



##-----------------Generate insights---------------------------------------------------##

        for symbol, symbolData in self.SQQQ.items():
            'Insights are intellectual property'
            pass


##-----------------Extend insights separate from Risk Management Module------------------##

        insights.extend(self.ManagePosition(algorithm))

        return insights


##-----------------Create Alpha specific risk management---------------------------------##

    def ManagePosition(self, algorithm):

        TQQQ = SymbolCache.GetSymbol("TQQQ")
        UVXY = SymbolCache.GetSymbol("UVXY")

        RiskInsights = []

        for symbol, symbolData in self.SQQQ.items():
            if (
                Global.MarketIsOpen
                and not algorithm.Portfolio[TQQQ].Invested
                ):

                if algorithm.Portfolio[symbol].UnrealizedProfitPercent <= -float(0.2025):
                    RiskInsights.append(Insight.Price(TQQQ, timedelta(hours=2.5), InsightDirection.Up, float(0.01), None, None, 0.5))
                    # RiskInsights.append(Insight.Price(UVXY, timedelta(hours=1.5), InsightDirection.Up, float(0.01), None, None, 0.5))

        return RiskInsights



##-----------------Checks that certain criteria are met before trading-------------------##

    def ReadyCheck(self, algorithm, symbol, symbolData):
        self.OpenOrders = algorithm.Transactions.GetOpenOrders(symbol)

        if (symbolData.EMACross.IsReady
        and Global.TradeTriggers[symbol]
        and VixHandler.vixList
        and Global.MarketIsOpen
        and not self.OpenOrders
        ):

            return True

        else:
            return False

    '''
    Section 2-B:  Universe changes
    '''

##-----------------Handle asset(s)-specific class on universe changes---------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        SQQQ = SymbolCache.GetSymbol("SQQQ")

        for added in changes.AddedSecurities:
            # Only create symbol data for SPXS
            symbolData = self.SQQQ.get(added.Symbol)

            if symbolData is None and added.Symbol == SQQQ:
                # Create indicators
                symbolData = SymbolData(added, self.Name, self.RSIDeviationRange)
                symbolData.InitializeIndicators(algorithm, self.FastPeriod, self.SlowPeriod, self.resolution)
                symbolData.StatBounds(algorithm, self.FastPeriod, self.SlowPeriod, self.StatPeriod, self.resolution)
                symbolData.GetGapSignal(algorithm)

                self.SQQQ[added.Symbol] = symbolData

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
                for symbol, symbolData in self.SQQQ.items():
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
        self.Trade = False

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
        history = algorithm.History(self.Symbol, timedelta(days=43000), Resolution.Daily)

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

        rsi = algorithm.RSI(self.Symbol, 124, MovingAverageType.Simple, Resolution.Daily)
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



    '''
    Section 4-B:  Takes in the current time and returns the current open, current close, next open, and optionally the current open plus a timedelta offset
    '''
##-----------------Return current open, current close, and next open from specified time------##
    def MarketHours(algorithm, symbol, offset=timedelta(minutes=0)):
        hours = algorithm.Securities[symbol].Exchange.Hours
        CurrentOpen = hours.GetNextMarketOpen(algorithm.Time, False)
        CurrentClose = hours.GetNextMarketClose(CurrentOpen, False)
        NextOpen = hours.GetNextMarketOpen(CurrentClose, False)
        OpenOffset = hours.GetNextMarketOpen(algorithm.Time, False) + offset

        return [CurrentOpen, CurrentClose, NextOpen, OpenOffset]