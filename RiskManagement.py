# Imports
from datetime import datetime, timedelta

from clr import AddReference

AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Algorithm.Framework")

from QuantConnect import Resolution, Extensions
from QuantConnect.Algorithm.Framework.Portfolio import *
from QuantConnect.Algorithm.Framework.Risk import *

# Global variables
Zero = int(0)


class TrailingStop(RiskManagementModel):

    def __init__(self, DynamicDrawdown=False, Deviations=0, MinimumRiskTolerance=0.05):
        '''
        Initialization variables

            DynamicDrawdown: When True this will calculate asset specific drawdowns based on the previous year of intraday movements
            Deviations: How many deviations from the mean intraday move from open price you wish to tolerate.

        '''

        # Long Position Variables
        self.LongTrail = {}
        self.LongTrailingDrawdown = float(0.20)

        # Short Position Variables
        self.ShortTrail = {}
        self.ShortTrailingDrawdown = float(0.20)

        # Asset specific metrics
        self.DynamicDrawdown = DynamicDrawdown
        self.Deviations = Deviations
        self.MinimumRisk = MinimumRiskTolerance
        self.AssetData = {}

        # Other variables
        self.timer = None

    def ManageRisk(self, algorithm, targets):
        '''
        Main risk management handler. Passes algorithm and targets

        '''
        RiskAdjustedTargets = []

        for asset in algorithm.Securities.Keys:
            if not algorithm.Portfolio[asset].Invested:
                self.LongTrail[asset] = [algorithm.Securities[asset].Price, 0]
                self.ShortTrail[asset] = [algorithm.Securities[asset].Price, 0]

            if asset in self.AssetData and self.DynamicDrawdown:
                self.AssetData[asset].AnnualRecalc(asset, algorithm)

        invested = [x.Key for x in algorithm.Portfolio if x.Value.Invested]

        if invested:
            for asset in invested:

                if self.DynamicDrawdown:
                    self.CalculatedStop(algorithm, asset, RiskAdjustedTargets)

                else:
                    if not self.timer == algorithm.Time.day:
                        for asset in invested:
                            self.AssetData[asset].GetPerformanceData(algorithm)
                        self.timer = algorithm.Time.day

                    self.SpecificStop(algorithm, asset, RiskAdjustedTargets)

        return RiskAdjustedTargets

    def SpecificStop(self, algorithm, asset, RiskAdjustedTargets):
        '''
        Uses a static drawdown set by the user for all assets
        '''

        if algorithm.Portfolio[asset].IsLong:
            if asset not in self.LongTrail or self.LongTrail[asset][1] == 0:
                self.LongTrail[asset] = [algorithm.Portfolio[asset].Price, algorithm.Portfolio[asset].Quantity]

            elif algorithm.Portfolio[asset].Price > self.LongTrail[asset][0]:
                self.LongTrail[asset][0] = algorithm.Portfolio[asset].Price

            elif algorithm.Portfolio[asset].Price / self.LongTrail[asset][0] < min(1 - self.MinimumRisk,
                                                                                   (1 - self.LongTrailingDrawdown)):
                RiskAdjustedTargets.append(PortfolioTarget(asset, 0))
                algorithm.Log(
                    f'Long trailing Stop Triggered for {asset}.  Current Price: {algorithm.Portfolio[asset].Price} | Highest Price: {self.LongTrail[asset][0]} | Loss: {abs(round((algorithm.Portfolio[asset].Price / self.LongTrail[asset][0]) - 1, 3)) * 100}% | Date: {algorithm.Time}')
                self.LongTrail.pop(asset)


        elif algorithm.Portfolio[asset].IsShort:
            if asset not in self.ShortTrail or self.ShortTrail[asset][1] == 0:
                self.ShortTrail[asset] = [algorithm.Portfolio[asset].Price, algorithm.Portfolio[asset].Quantity]

            elif algorithm.Portfolio[asset].Price < self.ShortTrail[asset][0]:
                self.ShortTrail[asset][0] = algorithm.Portfolio[asset].Price

            elif algorithm.Portfolio[asset].Price / self.ShortTrail[asset][0] > max(1 + self.MinimumRisk,
                                                                                    (1 + self.ShortTrailingDrawdown)):
                RiskAdjustedTargets.append(PortfolioTarget(asset, 0))
                algorithm.Log(
                    f'Short trailing Stop Triggered for {asset}. Current Price: {algorithm.Portfolio[asset].Price} | Lowest Price: {self.ShortTrail[asset][0]} | Loss: {abs(round((algorithm.Portfolio[asset].Price / self.ShortTrail[asset][0]) - 1, 3)) * 100}% | Date: {algorithm.Time}')
                self.ShortTrail.pop(asset)

    def CalculatedStop(self, algorithm, asset, RiskAdjustedTargets):
        '''
        Uses a derived drawdown set by the user for each asset
        '''

        if algorithm.Portfolio[asset].IsLong:
            if asset not in self.LongTrail or self.LongTrail[asset][1] == 0:
                self.LongTrail[asset] = [algorithm.Portfolio[asset].Price, algorithm.Portfolio[asset].Quantity]

            elif algorithm.Portfolio[asset].Price > self.LongTrail[asset][0]:
                self.LongTrail[asset][0] = algorithm.Portfolio[asset].Price

            elif algorithm.Portfolio[asset].Price / self.LongTrail[asset][0] < (
                    1 - self.AssetData[asset].TrailingDrawdown):
                RiskAdjustedTargets.append(PortfolioTarget(asset, 0))
                algorithm.Log(
                    f'Long trailing Stop Triggered for {asset}.  Current Price: {algorithm.Portfolio[asset].Price} | Highest Price: {self.LongTrail[asset][0]} | Loss: {abs(round((algorithm.Portfolio[asset].Price / self.LongTrail[asset][0]) - 1, 3)) * 100}% | Date: {algorithm.Time}')
                self.LongTrail.pop(asset)


        elif algorithm.Portfolio[asset].IsShort:
            if asset not in self.ShortTrail or self.ShortTrail[asset][1] == 0:
                self.ShortTrail[asset] = [algorithm.Portfolio[asset].Price, algorithm.Portfolio[asset].Quantity]

            elif algorithm.Portfolio[asset].Price < self.ShortTrail[asset][0]:
                self.ShortTrail[asset][0] = algorithm.Portfolio[asset].Price

            elif algorithm.Portfolio[asset].Price / self.ShortTrail[asset][0] > (
                    1 + self.AssetData[asset].TrailingDrawdown):
                RiskAdjustedTargets.append(PortfolioTarget(asset, 0))
                algorithm.Log(
                    f'Short trailing Stop Triggered for {asset}. Current Price: {algorithm.Portfolio[asset].Price} | Lowest Price: {self.ShortTrail[asset][0]} | Loss: {abs(round((algorithm.Portfolio[asset].Price / self.ShortTrail[asset][0]) - 1, 3)) * 100}% | Date: {algorithm.Time}')
                self.ShortTrail.pop(asset)

    def OnSecuritiesChanged(self, algorithm, changes):

        for added in changes.AddedSecurities:
            # Get performance data and derive risk boundaries
            symbolData = SymbolData(added, self.Deviations, self.MinimumRisk)
            symbolData.GetPerformanceData(algorithm)

            self.AssetData[added.Symbol] = symbolData


class ManageDrawdownRisk(RiskManagementModel):

    def __init__(self):
        '''
        Initialization variables

        '''

        # Long Position Variables
        self.LongDrawdownLimit = -float(0.15)

        # Short Position Variables
        self.ShortDrawdownLimit = -float(0.15)

    def ManageRisk(self, algorithm, targets):
        '''
        Main risk management handler. Passes algorithm and targets

        '''

        RiskAdjustedTargets = []

        invested = [x.Key for x in algorithm.Portfolio if x.Value.Invested]

        if invested:
            for asset in invested:

                if algorithm.Portfolio[asset].IsLong:
                    self.LongPositions(algorithm, asset, RiskAdjustedTargets)

                elif algorithm.Portfolio[asset].IsShort:
                    self.ShortPositions(algorithm, asset, RiskAdjustedTargets)

        return RiskAdjustedTargets

    def LongPositions(self, algorithm, asset, RiskAdjustedTargets):
        '''
        Separates long positions to allow for separate risk management parameters if desired

        '''

        pnl = algorithm.Portfolio[asset].UnrealizedProfitPercent

        if pnl <= self.LongDrawdownLimit:
            RiskAdjustedTargets.append(PortfolioTarget(asset, Zero))

        return RiskAdjustedTargets

    def ShortPositions(self, algorithm, asset, RiskAdjustedTargets):
        '''
        Separates short positions to allow for separate risk management parameters if desired

        '''

        pnl = algorithm.Portfolio[asset].UnrealizedProfitPercent

        if pnl <= self.ShortDrawdownLimit:
            RiskAdjustedTargets.append(PortfolioTarget(asset, Zero))

        return RiskAdjustedTargets


class SymbolData:

    def __init__(self, security, Deviations, MinimumRisk):
        self.Reset = False
        self.Symbol = security.Symbol
        self.Deviations = Deviations
        self.TrailingDrawdown = float(1.0)
        self.MinimumRisk = MinimumRisk

    def AnnualRecalc(self, symbol, algorithm):
        '''
        Adjusts the annual statistics once per year on the first trading day of the year
        '''

        # Once per year update the VIX statistics with the previuos 4000 days data
        firstTradingDay = date(algorithm.Time.year, 1, 3)
        if algorithm.Time.date() == self.GetNextWeekday(firstTradingDay):
            self.Reset = True

        if (self.Reset and algorithm.Time.date() == self.GetNextWeekday(firstTradingDay) + timedelta(days=1)):
            self.GetPerformanceData(algorithm)
            self.Reset = False

    def GetPerformanceData(self, algorithm):
        '''
        Defines asset specific drawdowns based on historic price data. Looks at the percent change from day high to day low individusally.
        '''

        History = algorithm.History(self.Symbol, timedelta(days=365), Resolution.Daily)
        IntradayHighLow = abs(History['high'] / History['low'] - 1)

        MeanIntradayHighLow = round(IntradayHighLow.mean(), 3)
        STDIntradayHighLow = round(IntradayHighLow.std(), 3)

        self.TrailingDrawdown = max(self.MinimumRisk,
                                    float(round(MeanIntradayHighLow + self.Deviations * STDIntradayHighLow, 3)))
        algorithm.Log(
            f'{self.Symbol} | Mean: {MeanIntradayHighLow} | STD: {STDIntradayHighLow} | Drawdown: {self.TrailingDrawdown}')

    def GetNextWeekday(self, RandomDate):
        RandomDate += timedelta(days=1)

        while RandomDate.weekday() > int(4):  # Mon-Fri are 0-4
            RandomDate += timedelta(days=1)

        return RandomDate
