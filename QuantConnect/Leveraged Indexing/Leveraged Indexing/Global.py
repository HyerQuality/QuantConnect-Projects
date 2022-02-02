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
from QuantConnect.Data.Custom.CBOE import *
from QuantConnect.Algorithm.Framework.Selection import *

##-------------------Alpha Files and Objects--------------------------------------------------##

from Global import VixHandler
from Global import Global

import LevSpy
import LevQ
import LevVix

##-------------------Portfolio Construction Files----------------------------------------------##

from SourceModelPortfolioConstruction import SourceModelPortfolioConstructionModel

##-------------------Execution Files---------------------------------------------##

from ImmediateExecution import ImmediateExecutionModel

##-------------------Risk Management Files----------------------------------------------------##

from MaximumDrawdownRiskManagement import ManageDrawdownRisk
from TrailingStopRiskManagement import TrailingStop

##-------------------Global variables---------------------------------------------------------##

Zero = int(0)
One = int(1)
OneDay = timedelta(days=1)
StatPeriod = timedelta(days=365)


class AdvancedIndexing(QCAlgorithm):

    ##-------------------Initialize variables, lists, asset subscriptions, etc--------------------##

    def Initialize(self):
        # Set Start Date so that backtest has 7+ years of data
        self.SetStartDate(2014, 1, 1)
        # self.SetStartDate(self.Time.today() - timedelta(days=365*7))
        #    self.SetEndDate(2020,1,1)

        # Set Cash
        self.SetCash(1000000)

        # Optional Settings
        self.Settings.FreePortfolioValuePercentage = 0.05

        # Variables
        self.Zero = int(0)

        # Lists
        self.TimeBounds = [time(9, 30), time(9, 31)]

        # VIX Data
        self.AddData(CBOE, "VIX")

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

        ManualSymbols = []

        for x in self.Assets:
            ManualSymbols.append(x.Symbol)
            Global.OpenClose[x.Symbol] = [0, -np.inf, 0]

        ##-------------------Construct Alpha Model----------------------------------------------------##

        # Universe Selection
        self.AddUniverseSelection(ManualUniverseSelectionModel(ManualSymbols))

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

        # Risk Management
        #    self.SetRiskManagement(ManageDrawdownRisk())
        self.SetRiskManagement(TrailingStop(DynamicDrawdown=False, Deviations=1))

        # Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        # self.SetBrokerageModel(AlphaStreamsBrokerageModel())

        ##------------------Schedule Events-----------------------------------------------------------##

        self.Schedule.On(self.DateRules.EveryDay("TQQQ"), self.TimeRules.AfterMarketOpen("TQQQ", 1), self.AtOpen)
        self.Schedule.On(self.DateRules.EveryDay("TQQQ"), self.TimeRules.BeforeMarketClose("TQQQ", 1), self.AtClose)
        self.Schedule.On(self.DateRules.MonthStart("TQQQ"), self.TimeRules.AfterMarketOpen("TQQQ", 1), self.AverageVix)

        VIX = SymbolCache.GetSymbol("VIX.CBOE")
        self.AnnualRecalc(VIX)

    ##-------------------On Data------------------------------------------------------------------##

    def OnData(self, data):

        if not self.VixReset:
            if self.Portfolio.TotalPortfolioValue > Global.PortfolioHigh:
                Global.PortfolioHigh = self.Portfolio.TotalPortfolioValue

            else:
                Global.PortfolioDrawdown = round((self.Portfolio.TotalPortfolioValue / Global.PortfolioHigh) - 1, 3)

        ##-------------------Manage and plot VIX data-------------------------------------------------##

        self.QCVix(data)

    ##-------------------Manage symbol overnight gaps---------------------------------------------##
    def AtOpen(self):
        for key in Global.OpenClose:

            if np.isinf(Global.OpenClose[key][1]):
                history = self.History(key, timedelta(days=5), Resolution.Daily)['close'][-1]
                Global.OpenClose[key][0] = self.Securities[key].Open
                Global.OpenClose[key][1] = history
                Global.OpenClose[key][2] = round((Global.OpenClose[key][0] / Global.OpenClose[key][1]) - 1, 2)

                # self.Log(f'{key} gap: {Global.OpenClose[key][2]*100}% at {self.Time.time()}')

            else:
                Global.OpenClose[key][0] = self.Securities[key].Open
                Global.OpenClose[key][2] = round((Global.OpenClose[key][0] / Global.OpenClose[key][1]) - 1, 2)

                # self.Log(f'{key} gap: {Global.OpenClose[key][2]*100}% at {self.Time.time()}')

    def AtClose(self):
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
            # weight = abs(round(-0.5/np.log((np.arctan(VixHandler.PreviousVixClose.Current.Value/37))),3))
            weight = abs(
                round(-0.5 / np.log((1.27 * np.arctan(np.sqrt(VixHandler.PreviousVixClose.Current.Value) / 10))), 3))
            if weight >= 1.5:
                Global.ShortUVXY = 1.5
            elif weight <= 0.4:
                Global.ShortUVXY = 0.4
            else:
                Global.ShortUVXY = weight

            Global.MarginMultiplier = min(1.3, Global.ShortUVXY * np.pi)

            # Charts
            self.Plot('VIX Spot', 'VixPercentMove', VixHandler.vixPercentMove)
            self.Plot('VIX Spot', 'Previous Day Closing VIX', VixHandler.PreviousVixClose.Current.Value)
            self.Plot('VIX 5-Day', '% Move Standard Deviation', VixHandler.FiveDayVixPercentMoveSTD)
            self.Plot('VIX 5-Day', '% Move Average', VixHandler.SixDayVixAverage)
            self.Plot('Weights', 'Short Weights', Global.ShortUVXY * 100)
            # self.Plot('Studies', '% Move STD*AVG', VixHandler.FiveDayVixPercentMoveSTD*VixHandler.SixDayVixAverage)
            self.Plot('Weights', 'Long Weights', Global.MarginMultiplier * 100)

            self.Log(
                "At {0} the VIX list Populated. The current lists are: Spot - {1} | %Change - {2} | FiveDayVixPercentMoveSTD - {3} | SixDayVixAverage - {4} | Short Weight - {5} | Current Drawdown - {6}".format(
                    self.Time, VixHandler.vixList, VixHandler.vixPercentMoveList,
                    round(VixHandler.FiveDayVixPercentMoveSTD, 4), round(VixHandler.SixDayVixAverage, 4),
                    Global.ShortUVXY, Global.PortfolioDrawdown))

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

    def VixHistory(self, Days, symbol):
        startingDays = Days
        history = self.History(symbol, Days, Resolution.Daily)

        while len(history) < Days:
            startingDays = startingDays + 1
            history = self.History(symbol, startingDays, Resolution.Daily)

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

    ##-----------------Handles broker specfic issues--------------------------------------------------##

    def OnBrokerageMessage(self, messageEvent):
        message = messageEvent.Message

        # Adjust maximum weights if brokerage is requiring more than the estimated initial margin
        if (re.search("insufficient to cover the Initial Margin requirement", message, re.IGNORECASE)
                or re.search("PREVIOUS DAY EQUITY WITH LOAN VALUE", message, re.IGNORECASE)
                or re.search("INITIAL MARGIN", message, re.IGNORECASE)):
            self.Log("Initial margin requirements require a reduction in position size. Reducing current order by 3%")
