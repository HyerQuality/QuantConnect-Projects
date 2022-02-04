##-------------------Imports-------------------------------------------------------------------##

import numpy as np
import pandas as pd
import re
from datetime import *

from clr import AddReference

AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Algorithm.Framework")
AddReference("QuantConnect.Common")

from System import *
from QuantConnect import *
from QuantConnect import Resolution, Extensions
from QuantConnect.Data.UniverseSelection import *
# from QuantConnect.Data.Custom.CBOE import *
from QuantConnect.Algorithm.Framework.Selection import *

##-------------------Alpha Files and Objects--------------------------------------------------##

from Global import VixHandler
from Global import Global
from Global import DefaultValues

import LevSpy
import LevQ
import LevVix

##-------------------Portfolio Construction Files----------------------------------------------##

from SourceModelPortfolioConstruction import SourceModelPortfolioConstructionModel

##-------------------Execution Files---------------------------------------------##

from ImmediateExecution import ImmediateExecutionModel
from LimitOrderExecutionModel import LimitOrderExecutionModel

##-------------------Risk Management Files----------------------------------------------------##

from RiskManagement import ManageDrawdownRisk, TrailingStop
from ProfitCapture import ProfitCapture

##-------------------Global variables---------------------------------------------------------##

Zero = int(0)
One = int(1)
OneDay = timedelta(days=1)
StatPeriod = timedelta(days=365)


class InteractiveBrokersBrokerageModelWithShortable(InteractiveBrokersBrokerageModel):
    def __init__(self):
        super().__init__()
        self.ShortableProvider = AtreyuShortableProvider(SecurityType.Equity, Market.USA)


class AdvancedIndexing(QCAlgorithm):

    ##-------------------Initialize variables, lists, asset subscriptions, etc--------------------##

    def Initialize(self):
        # Set Start Date so that backtest has 7+ years of data
        self.SetStartDate(2021, 10, 1)
        # self.SetStartDate(self.Time.today() - timedelta(days=365*7))
        #    self.SetEndDate(2020,1,1)

        # Set Cash
        self.SetCash(1000000)

        # Optional Settings
        self.Settings.FreePortfolioValuePercentage = 0.05

        # Variables
        self.Zero = int(0)
        self.InitialPortfolioValue = self.Portfolio.TotalPortfolioValue
        self.ClosingPortfolioValue = self.Portfolio.TotalPortfolioValue
        self.WeightOffset = float(0)

        # Lists
        self.TimeBounds = [time(9, 30), time(9, 31)]

        # VIX Data
        self.AddData(CBOE, "VIX")
        self.vix = self.AddIndex("VIX").Symbol

        # Selected Securitites
        self.Assets = [
            self.AddEquity("UVXY"),
            self.AddEquity("SPXL"),
            self.AddEquity("SPXS"),
            self.AddEquity("TQQQ"),
            self.AddEquity("SQQQ")]

        # Booleans
        self.VixReset = False
        self.OnStartUp = True

        self.ManualSymbols = []

        DefaultValues.ResetGlobal()
        DefaultValues.ResetVixHandler()
        self.FillVixList()

        for x in self.Assets:
            self.ManualSymbols.append(x.Symbol)
            Global.OpenClose[x.Symbol] = [0, -np.inf, 0]
            Global.TradeTriggers[x.Symbol] = True

        ##-------------------Construct Alpha Model----------------------------------------------------##

        # Universe Selection
        self.AddUniverseSelection(ManualUniverseSelectionModel(self.ManualSymbols))

        # Alpha
        self.AddAlpha(LevSpy.SPXL())
        self.AddAlpha(LevSpy.SPXS())
        self.AddAlpha(LevQ.TQQQ())
        self.AddAlpha(LevQ.SQQQ())
        self.AddAlpha(LevVix.ShortVol(StatPeriod))
        self.AddAlpha(LevVix.LongVol(StatPeriod))

        # Portfolio Construction
        self.SetPortfolioConstruction(SourceModelPortfolioConstructionModel())

        # Execution
        self.SetExecution(ImmediateExecutionModel())
        # self.SetExecution(LimitOrderExecutionModel())

        # Risk Management
        self.SetRiskManagement(ManageDrawdownRisk())
        # self.SetRiskManagement(ProfitCapture())
        # self.SetRiskManagement(TrailingStop(DynamicDrawdown = False, Deviations = 1, MinimumRiskTolerance = 0.20))

        # Brokerage Model
        # self.SetBrokerageModel(InteractiveBrokersBrokerageModelWithShortable())
        self.SetBrokerageModel(InteractiveBrokersBrokerageModel())
        # self.SetBrokerageModel(AlphaStreamsBrokerageModel())

        ##------------------Schedule Events-----------------------------------------------------------##

        self.Schedule.On(self.DateRules.EveryDay("TQQQ"), self.TimeRules.AfterMarketOpen("TQQQ", 0), self.MarketOpen)
        self.Schedule.On(self.DateRules.EveryDay("TQQQ"), self.TimeRules.AfterMarketOpen("TQQQ", 1), self.GetOpenPrice)
        self.Schedule.On(self.DateRules.MonthStart("TQQQ"), self.TimeRules.AfterMarketOpen("TQQQ", 1), self.AverageVix)
        self.Schedule.On(self.DateRules.EveryDay("TQQQ"), self.TimeRules.BeforeMarketClose("TQQQ", 1),
                         self.GetClosePrice)
        self.Schedule.On(self.DateRules.EveryDay("TQQQ"), self.TimeRules.BeforeMarketClose("TQQQ", 0), self.MarketClose)

        VIX = SymbolCache.GetSymbol("VIX.CBOE")
        self.AnnualRecalc(VIX)

        # Set Warmup
        self.SetWarmup(5, Resolution.Daily)

    ##-------------------On Data------------------------------------------------------------------##

    def OnData(self, data):
        if self.Portfolio.TotalPortfolioValue > Global.PortfolioHigh:
            Global.PortfolioHigh = self.Portfolio.TotalPortfolioValue

            if round((Global.PortfolioHigh / self.InitialPortfolioValue) - 1, 3) > Global.PortfolioGains:
                new_gains = round((Global.PortfolioHigh / self.InitialPortfolioValue) - 1, 3) - Global.PortfolioGains
                Global.InitialDrawdown = min(0, round(Global.InitialDrawdown + new_gains, 3))
                Global.PortfolioGains = round((Global.PortfolioHigh / self.InitialPortfolioValue) - 1, 3)

        else:
            Global.PortfolioDrawdown = round((self.Portfolio.TotalPortfolioValue / Global.PortfolioHigh) - 1,
                                             3) + Global.InitialDrawdown

        Global.MarginMultiplier = max(1.33, 1.33 * (1 + Global.PortfolioDrawdown))

        ##-------------------Manage and plot VIX data-------------------------------------------------##

        self.QCVix(data)

    def MarketOpen(self):
        Global.MarketIsOpen = True

    def MarketClose(self):
        Global.MarketIsOpen = False

    ##-------------------Manage symbol overnight gaps---------------------------------------------##
    def GetOpenPrice(self):

        self.WeightOffset = round((self.Portfolio.TotalPortfolioValue / self.ClosingPortfolioValue) - 1, 3)
        Global.NoSharesAvailable = False

        for key in Global.TradeTriggers:
            if not Global.TradeTriggers[key]:
                Global.TradeTriggers[key] = True

        if self.LiveMode and self.WeightOffset < -0.9:
            pass
        else:
            Global.ShortUVXY = min(Global.ShortUVXY - self.WeightOffset, 0.78)

        self.Log(
            f'Overnight change in portfolio value: {self.WeightOffset} | Adjusted Short Weight: {Global.ShortUVXY}')
        self.Plot('Weights', 'Adjusted Short Weights', Global.ShortUVXY * 100)

        for key in Global.OpenClose:

            if np.isinf(Global.OpenClose[key][1]):
                history = self.History(key, timedelta(days=5), Resolution.Daily)['close'][-1]
                Global.OpenClose[key][0] = self.Securities[key].Open
                Global.OpenClose[key][1] = history
                Global.OpenClose[key][2] = round((Global.OpenClose[key][0] / Global.OpenClose[key][1]) - 1, 2)

            else:
                Global.OpenClose[key][0] = self.Securities[key].Open
                Global.OpenClose[key][2] = round((Global.OpenClose[key][0] / Global.OpenClose[key][1]) - 1, 2)

    def GetClosePrice(self):

        self.Transactions.CancelOpenOrders()
        self.ClosingPortfolioValue = self.Portfolio.TotalPortfolioValue

        for key in Global.OpenClose:
            if self.Securities[key].Close != Zero:
                Global.OpenClose[key][1] = self.Securities[key].Close
            else:
                Global.OpenClose[key][1] = -np.inf

    ##-----------------Pulls VIX data from the QC Database---------------------------------------##

    def QCVix(self, data):
        VIX = SymbolCache.GetSymbol("VIX.CBOE")
        UVXY = SymbolCache.GetSymbol("UVXY")
        days = 6
        self.AnnualRecalc(VIX)

        if data.ContainsKey(VIX) or not VixHandler.vixList:
            VixHandler.Symbol = VIX

            VixHistory = self.VixHistory(days, VIX)
            VixHandler.vixList = VixHistory.values.flatten().tolist()
            VixHandler.vixPercentMoveList = VixHistory.pct_change().dropna().apply(
                lambda x: x * float(100)).values.flatten().round(3).tolist()
            VixHandler.PreviousVixClose.Update(self.Time, VixHandler.vixList[-1])
            VixHandler.vixPercentMove = VixHandler.vixPercentMoveList[-1]
            VixHandler.FiveDayVixPercentMoveSTD = np.std(VixHandler.vixPercentMoveList)
            VixHandler.SixDayVixAverage = np.mean(VixHandler.vixPercentMoveList)

            # Position weights
            if VixHandler.PreviousVixClose.Current.Value >= VixHandler.DeviationVix[2]:
                Global.ShortUVXY = min(abs(round(
                    -0.5 / np.log((1.225 * np.arctan(np.sqrt(VixHandler.PreviousVixClose.Current.Value) / 10))), 3)),
                                       0.78)

            else:
                Global.ShortUVXY = min(abs(round(
                    -0.44 / np.log((1.225 * np.arctan(np.sqrt(VixHandler.PreviousVixClose.Current.Value) / 10))), 3)),
                                       0.78)

                if Global.ShortUVXY <= 0.4:
                    Global.ShortUVXY = 0.4

            # Charts
            self.Plot('VIX Spot', 'VixPercentMove', VixHandler.vixPercentMove)
            self.Plot('VIX Spot', 'Previous Day Closing VIX', VixHandler.PreviousVixClose.Current.Value)
            self.Plot('VIX 5-Day', '% Move Standard Deviation', VixHandler.FiveDayVixPercentMoveSTD)
            self.Plot('VIX 5-Day', '% Move Average', VixHandler.SixDayVixAverage)
            self.Plot('Weights', 'UnAdjusted Short Weights', Global.ShortUVXY * 100)
            # self.Plot('Studies', '% Move STD*AVG', VixHandler.FiveDayVixPercentMoveSTD*VixHandler.SixDayVixAverage)
            # self.Plot('Weights', 'Long Weights', Global.MarginMultiplier*100)

            self.Log(
                "At {0} the VIX list Populated. The current lists are: Spot - {1} | %Change - {2} | FiveDayVixPercentMoveSTD - {3} | SixDayVixAverage - {4} | Unadjusted Short Weight - {5} | Current Drawdown - {6}".format(
                    self.Time, VixHandler.vixList, VixHandler.vixPercentMoveList,
                    round(VixHandler.FiveDayVixPercentMoveSTD, 4), round(VixHandler.SixDayVixAverage, 4),
                    Global.ShortUVXY, Global.PortfolioDrawdown))

        elif data.ContainsKey(self.vix):

            current_vix = data[self.vix].Close

            # Position weights
            if current_vix >= VixHandler.DeviationVix[2]:
                Global.ShortUVXY = min(abs(round(-0.5 / np.log((1.225 * np.arctan(np.sqrt(current_vix) / 10))), 3)),
                                       0.78)

            else:
                Global.ShortUVXY = min(abs(round(-0.44 / np.log((1.225 * np.arctan(np.sqrt(current_vix) / 10))), 3)),
                                       0.78)

                if Global.ShortUVXY <= 0.4:
                    Global.ShortUVXY = 0.4

    def FillVixList(self):
        VIX = SymbolCache.GetSymbol("VIX.CBOE")
        days = 6
        VixHandler.Symbol = VIX

        VixHistory = self.VixHistory(days, VIX)
        VixHandler.vixList = VixHistory.values.flatten().tolist()
        VixHandler.vixPercentMoveList = VixHistory.pct_change().dropna().apply(
            lambda x: x * float(100)).values.flatten().round(3).tolist()
        VixHandler.PreviousVixClose.Update(self.Time, VixHandler.vixList[-1])
        VixHandler.vixPercentMove = VixHandler.vixPercentMoveList[-1]
        VixHandler.FiveDayVixPercentMoveSTD = np.std(VixHandler.vixPercentMoveList)
        VixHandler.SixDayVixAverage = np.mean(VixHandler.vixPercentMoveList)

        # Charts
        self.Plot('VIX Spot', 'VixPercentMove', VixHandler.vixPercentMove)
        self.Plot('VIX Spot', 'Previous Day Closing VIX', VixHandler.PreviousVixClose.Current.Value)
        self.Plot('VIX 5-Day', '% Move Standard Deviation', VixHandler.FiveDayVixPercentMoveSTD)
        self.Plot('VIX 5-Day', '% Move Average', VixHandler.SixDayVixAverage)
        self.Plot('Weights', 'Short Weights', Global.ShortUVXY * 100)
        # self.Plot('Studies', '% Move STD*AVG', VixHandler.FiveDayVixPercentMoveSTD*VixHandler.SixDayVixAverage)
        # self.Plot('Weights', 'Long Weights', Global.MarginMultiplier*100)

        self.Log(
            "At {0} the VIX list Populated. The current lists are: Spot - {1} | %Change - {2} | FiveDayVixPercentMoveSTD - {3} | SixDayVixAverage - {4} | Short Weight - {5} | Current Drawdown - {6}".format(
                self.Time, VixHandler.vixList, VixHandler.vixPercentMoveList,
                round(VixHandler.FiveDayVixPercentMoveSTD, 4), round(VixHandler.SixDayVixAverage, 4), Global.ShortUVXY,
                Global.PortfolioDrawdown))

    ##-----------------Annual recalculation of various statistics----------------------------------##

    def AnnualRecalc(self, symbol):

        # Once per year update the VIX statistics with the previuos 4000 days data
        if self.Time.date() == self.GetNextWeekday(
                date(self.Time.year, 1, 3)):  # and self.TimeBounds[0] <= self.Time.time() <= self.TimeBounds[1]:
            self.VixReset = True

        if (self.VixReset and self.Time.date() == self.GetNextWeekday(
                date(self.Time.year, 1, 3)) + OneDay) or self.OnStartUp:

            # Base Data
            vix_history = self.History(symbol, 4000, Resolution.Daily).reset_index(level=0, drop=True)
            vix_percent_change = vix_history["close"].pct_change()

            # Stat levels
            AverageVix = np.mean(vix_history["close"])
            STDVix = np.std(vix_history["close"])
            AverageChange = np.mean(vix_percent_change)
            STDChange = np.std(vix_percent_change)

            VixHandler.DeviationVix = []
            VixHandler.DeviationVixChange = []

            for i in np.arange(-1, 4, 0.5):
                VixHandler.DeviationVix.append(round(AverageVix + (STDVix * i), 2))

            for i in range(-3, 5):
                VixHandler.DeviationVixChange.append(round(((AverageChange + (STDChange * i)) * 100), 2))

            self.Log("VOL: VIX Spot Deviations: {0} || VIX Change Deviations: {1} || Year: {2}".format(
                VixHandler.DeviationVix, VixHandler.DeviationVixChange, self.Time.year))

            self.VixReset = False
            self.OnStartUp = False

    ##-------------------Method to capture previous month average VIX spot---------------------------##

    def AverageVix(self):

        VIX = SymbolCache.GetSymbol("VIX.CBOE")
        LastMonthHistory = np.array(self.VixHistory(30, VIX))
        LastMonthHistory = LastMonthHistory[LastMonthHistory <= np.percentile(LastMonthHistory, 99)]
        VixHandler.PreviousMonthAverage = round(np.mean(LastMonthHistory), 2)
        # self.Plot('VIX Spot', 'Previous Month Average VIX', VixHandler.PreviousMonthAverage)

    ##-------------------Method to capture the desired amount of VIX history-------------------------##

    def VixHistory(self, Days, symbol, resolution=Resolution.Daily):
        startingDays = Days
        history = self.History(symbol, Days, resolution)

        while len(history) < Days:
            startingDays = startingDays + 1
            history = self.History(symbol, startingDays, resolution)

        return history["close"]

    ##-----------------Return the next weekday from specified date------------------------------------##

    def GetNextWeekday(self, RandomDate):
        RandomDate += OneDay

        while RandomDate.weekday() > int(4):  # Mon-Fri are 0-4
            RandomDate += OneDay

        return RandomDate

    ##-----------------Handles margin call warnings---------------------------------------------------##

    # On a margin call warning log key charactistics of current positions
    def OnMarginCallWarning(self):
        self.Log("Margin Call Warning")
        return

    ##-----------------Handles margin call events-----------------------------------------------------##

    def OnMarginCall(self, requests):

        for order in requests:
            # Liquidate an extra 10% each time we get a margin call to give us more padding
            newQuantity = int(np.sign(order.Quantity) * order.Quantity * float(1.10))
            requests.remove(order)
            requests.append(
                SubmitOrderRequest(order.OrderType, order.SecurityType, order.Symbol, newQuantity, order.StopPrice,
                                   order.LimitPrice, self.Time, "OnMarginCall"))
            self.Log(f'Margin Call for {order.Symbol}')

        return requests

    # ##-----------------Handles broker specfic issues--------------------------------------------------##

    def OnBrokerageMessage(self, messageEvent):
        message = messageEvent.Message

        # Adjust maximum weights if brokerage is requiring more than the estimated initial margin
        if (re.search("The contract is not available for short sale", message, re.IGNORECASE)
                or re.search("Order held while securities are located", message, re.IGNORECASE)):
            Global.NoSharesAvailable = True
            self.Log(f'No shares of UVXY available to short. Generating similar insight')
