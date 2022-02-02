#Imports
from itertools import groupby
from datetime import datetime, timedelta
from pytz import utc

from clr import AddReference
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm.Framework")

from QuantConnect import Resolution, Extensions
from QuantConnect.Algorithm.Framework.Portfolio import *
from QuantConnect.Algorithm.Framework.Risk import *

#Global variables
Zero = int(0)

class ManageRisk(RiskManagementModel):

    def __init__(self):
        
        # Long Position Variables
        self.LongProfitCapture = float(1.00)
        self.LongDrawdownLimit = -float(0.10)
        
        # Short Position Variables
        self.ShortProfitCapture = float(1.0)
        self.ShortDrawdownLimit = -float(1.0)

    def ManageRisk(self, algorithm, targets):

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

        pnl = algorithm.Portfolio[asset].UnrealizedProfitPercent
        
        if pnl >= self.LongProfitCapture or pnl <= self.LongDrawdownLimit:
            RiskAdjustedTargets.append(PortfolioTarget(asset, Zero))


        return RiskAdjustedTargets
        
    def ShortPositions(self, algorithm, asset, RiskAdjustedTargets):
        
        pnl = algorithm.Portfolio[asset].UnrealizedProfitPercent
        
        if pnl >= self.ShortProfitCapture or pnl <= self.ShortDrawdownLimit:
            RiskAdjustedTargets.append(PortfolioTarget(asset, Zero))
            
        return RiskAdjustedTargets