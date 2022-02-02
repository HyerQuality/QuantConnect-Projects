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


class ManageDrawdownRisk(RiskManagementModel):

    def __init__(self):
        '''
        Initialization variables

        '''

        # Long Position Variables
        self.LongDrawdownLimit = -float(0.10)

        # Short Position Variables
        self.ShortDrawdownLimit = -float(0.10)

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