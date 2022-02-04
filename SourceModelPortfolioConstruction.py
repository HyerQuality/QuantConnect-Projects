##-----------------Imports----------------------------------------------------------------------------------------##
import numpy as np
from datetime import *

from clr import AddReference

AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Algorithm.Framework")

from QuantConnect import Resolution, Extensions
from QuantConnect.Algorithm.Framework.Alphas import *
from QuantConnect.Algorithm.Framework.Portfolio import *
from itertools import groupby
from datetime import datetime, timedelta
from pytz import utc

from Global import Global

##-----------------Global variables-------------------------------------------------------------------------------##

Zero = int(0)
UTCMIN = datetime.min.replace(tzinfo=utc)
SpecialResolutions = {
    "Long UVXY Alpha Model": Resolution.Hour,
    "Debug Alpha Model": Resolution.Daily}


class SourceModelPortfolioConstructionModel(PortfolioConstructionModel):

    ##-----------------Initialize variables, lists, etc---------------------------------------------------------------##

    def __init__(self):

        # Static Variables
        self.CummulativeInsightCollection = InsightCollection()
        self.FlatInsightCollection = InsightCollection()
        self.ShortWeight = Global.ShortUVXY
        self.RemovedSymbols = []
        self.DictCleanUp = []
        self.ErrorSymbols = {}
        self.Percents = {}
        self.SourceModels = {}

    ##-----------------Creates target weights---------------------------------------------------------------------------##

    def DetermineTargetPercent(self, algorithm, insights):

        # Add every insight to a cummulative insight collection
        for insight in insights:
            self.CummulativeInsightCollection.Add(insight)

        # Screen out all insights that are no longer active and have expired
        ActiveInsights = self.CummulativeInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the most recent insight for each asset with an active insighta
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key=lambda x: x.GeneratedTimeUtc)[-1])

        # Give equal weighting to each asset
        count = sum(x.Direction != InsightDirection.Flat for x in LastActiveInsights)
        percent = Zero if count == Zero else (Global.MarginMultiplier / count)

        # Assign a weight to the insight based on trade direction
        for insight in LastActiveInsights:

            if insight.Direction == InsightDirection.Down:
                self.Percents[insight] = insight.Direction * Global.ShortUVXY / count

            elif insight.Direction == InsightDirection.Up:
                self.Percents[insight] = insight.Direction * percent

            else:
                self.Percents[insight] = Zero

    ##-----------------Creates and returns Portfolio Targets------------------------------------------------------------##

    def CreateTargets(self, algorithm, insights):

        self.ErrorSymbols = {}
        targets = []

        # Only generate targets during market hours
        if not (time(9, 30) <= algorithm.Time.time() < time(16, 00)): return targets

        # Separate alpha models to handling insights from each model uniquely, if desired
        for insight in insights:
            if insight.SourceModel not in self.SourceModels:

                if insight.SourceModel in SpecialResolutions:
                    AlphaInsights = DynamicTargets(insight.Symbol, insight.SourceModel,
                                                   SpecialResolutions[insight.SourceModel])
                    self.SourceModels[insight.SourceModel] = AlphaInsights

                else:
                    AlphaInsights = DynamicTargets(insight.Symbol, insight.SourceModel)
                    self.SourceModels[insight.SourceModel] = AlphaInsights

        # Determine the weights for active insights
        self.DetermineTargetPercent(algorithm, insights)

        # Create a target for each alpha model
        for SourceModel, AlphaInsights in self.SourceModels.items():
            results = AlphaInsights.CreatePositions(algorithm, insights, self.Percents, self.RemovedSymbols)
            targets.extend(results)

        # Create flatten target for each security that was removed from the universe
        if self.RemovedSymbols is not None:
            universeDeselectionTargets = [PortfolioTarget(symbol, Zero) for symbol in self.RemovedSymbols]
            targets.extend(universeDeselectionTargets)
            self.RemovedSymbols = None

        # Remove expired insights
        self.CummulativeInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)

        # Clear the weights dictionary so that active insight weights are re-calculated at each time step. Particulalry useful when using a dynamic weight based on risk models that may change frequently.
        self.Percents = {}

        return targets

    ##-----------------Handles changes to the universe------------------------------------------------------------------##

    def OnSecuritiesChanged(self, algorithm, changes):

        # Get removed symbol and invalidate them in the insight collections
        self.RemovedSymbols = [x.Symbol for x in changes.RemovedSecurities]

        # Pop removed securities from the source model dictionary.  Any alpha model using a removed security will be deleted.
        for SourceModel, AlphaInsights in self.SourceModels.items():
            if AlphaInsights.Symbol in self.RemovedSymbols:
                self.SourceModels.pop(AlphaInsights.SourceModel)


##-----------------Class to manage different alpha models------------------------------------##

class DynamicTargets:

    def __init__(self, Symbol, SourceModel, res=Resolution.Daily):
        self.Symbol = Symbol
        self.SourceModel = SourceModel
        self.insightCollection = InsightCollection()
        self.NextExpiryTime = UTCMIN
        self.RebalancingTime = UTCMIN
        self.RebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(res) * 2
        self.ErrorSymbols = {}

    def CreatePositions(self, algorithm, insights, Percents, RemovedSymbols):

        Targets = []

        # Simultaneously the current time must be less than the next expiration time and next rebalancing time as well as no new insights and no changes to the universe.  If so, do nothing.
        if (algorithm.UtcTime <= self.NextExpiryTime and algorithm.UtcTime <= self.RebalancingTime and len(
                insights) == Zero and RemovedSymbols is None):
            return Targets

        else:
            # Collect source model specific insights
            for insight in insights:
                if insight.SourceModel == self.SourceModel:
                    self.insightCollection.Add(insight)

            # Get expired insights and create flatten targets for each symbol
            ExpiredTargets = []
            ExpiredInsights = self.insightCollection.RemoveExpiredInsights(algorithm.UtcTime)

            for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
                if not self.insightCollection.HasActiveInsights(symbol,
                                                                algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                    ExpiredTargets.append(PortfolioTarget(symbol, Zero))

            Targets.extend(ExpiredTargets)

            # Get insights that haven't expired for each symbol that is still in the universe
            ActiveInsights = self.insightCollection.GetActiveInsights(algorithm.UtcTime)

            # Get the last generated active insight
            LastActiveInsights = []
            for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
                LastActiveInsights.append(sorted(g, key=lambda x: x.GeneratedTimeUtc)[-1])

            # Create a target for the insight. Errors are stored in a dictionary to avoid crashing.  The dictionary is cleared each time new targets are generated.
            self.ErrorSymbols = {}
            for insight in LastActiveInsights:
                if insight in Percents:
                    symbol = insight.Symbol
                    target = PortfolioTarget.Percent(algorithm, symbol, Percents[insight])

                    if not target is None:
                        Targets.append(target)

                    else:
                        self.ErrorSymbols[symbol] = symbol
                        # algorithm.Log(f'{self.Symbol} had an error when generating a target for {insight}.')

                else:
                    self.ErrorSymbols[symbol] = symbol
                    # algorithm.Log(f'{insight} not in Active Insights.')

            # Capture the next expiration time and rebalancing time then return source model targets
            self.NextExpiryTime = self.insightCollection.GetNextExpiryTime()

            if self.NextExpiryTime is None:
                self.NextExpiryTime = UTCMIN

            # # Set the next rebalance time
            if algorithm.UtcTime >= self.RebalancingTime:
                self.RebalancingTime = self.RebalancingFunc(algorithm.UtcTime)
                # algorithm.Log(f'{self.SourceModel} rebalance time created at: {algorithm.UtcTime}. || Next rebalance time: {self.RebalancingTime}')

        return Targets