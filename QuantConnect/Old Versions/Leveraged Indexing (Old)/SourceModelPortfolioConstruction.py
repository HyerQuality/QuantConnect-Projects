##-----------------Imports----------------------------------------------------------------------------------------##
import numpy as np

from clr import AddReference
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm.Framework")

from QuantConnect import Resolution, Extensions
from QuantConnect.Algorithm.Framework.Alphas import *
from QuantConnect.Algorithm.Framework.Portfolio import *
from itertools import groupby
from datetime import datetime, timedelta
from pytz import utc

from DynamicWeight import Weights

##-----------------Global variables-------------------------------------------------------------------------------##

Zero = int(0)
OneDay = timedelta(days=1)
UTCMIN = datetime.min.replace(tzinfo=utc)

class SourceModelPortfolioConstructionModel(PortfolioConstructionModel):

##-----------------Initialize variables, lists, etc---------------------------------------------------------------##

    def __init__(self, SymbolList):

        # Static Variables
        self.CummulativeInsightCollection = InsightCollection()
        self.FlatInsightCollection = InsightCollection()
        self.RemovedSymbols = []
        self.DictCleanUp = []
        self.SymbolList = SymbolList
        self.ErrorSymbols = {}
        self.Percents = {}
        
        # LongVol Only Variables
        self.LongVolInsightCollection = InsightCollection()
        self.LongVolNextExpiryTime = UTCMIN
        self.LongVolRebalancingTime = UTCMIN
        self.LongVolRebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(Resolution.Hour)
        self.LongVolSourceModel = "Long UVXY Alpha Model"
        
        # ShortVol Only Variables
        self.ShortVolInsightCollection = InsightCollection()
        self.ShortVolNextExpiryTime = UTCMIN
        self.ShortVolRebalancingTime = UTCMIN
        self.ShortVolRebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(Resolution.Daily)
        self.ShortVolSourceModel = "Short UVXY Alpha Model"
        
        # SPXL Only Variables
        self.SPXLInsightCollection = InsightCollection()
        self.SPXLNextExpiryTime = UTCMIN
        self.SPXLRebalancingTime = UTCMIN
        self.SPXLRebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(Resolution.Daily)
        self.SPXLSourceModel = "SPXL Alpha Model"
        
        # SPXS Only Variables
        self.SPXSInsightCollection = InsightCollection()
        self.SPXSNextExpiryTime = UTCMIN
        self.SPXSRebalancingTime = UTCMIN
        self.SPXSRebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(Resolution.Daily)
        self.SPXSSourceModel = "SPXS Alpha Model"
        
        # TQQQ Only Variables
        self.TQQQInsightCollection = InsightCollection()
        self.TQQQNextExpiryTime = UTCMIN
        self.TQQQRebalancingTime = UTCMIN
        self.TQQQRebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(Resolution.Daily)
        self.TQQQSourceModel = "TQQQ Alpha Model"
        
        # SQQQ Only Variables
        self.SQQQInsightCollection = InsightCollection()
        self.SQQQNextExpiryTime = UTCMIN
        self.SQQQRebalancingTime = UTCMIN
        self.SQQQRebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(Resolution.Daily)
        self.SQQQSourceModel = "SQQQ Alpha Model"
        
        # Debug Only Variables
        self.DebugInsightCollection = InsightCollection()
        self.DebugNextExpiryTime = UTCMIN
        self.DebugRebalancingTime = UTCMIN
        self.DebugRebalancingFunc = lambda dt: dt + Extensions.ToTimeSpan(Resolution.Hour)
        self.DebugSourceModel = "Debug Alpha Model"


##-----------------Creates target weights---------------------------------------------------------------------------##

    def DetermineTargetPercent(self, algorithm, insights):

        for insight in insights:
            self.CummulativeInsightCollection.Add(insight)
        
        ActiveInsights = self.CummulativeInsightCollection.GetActiveInsights(algorithm.UtcTime)
        
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])
        
        # Give equal weighting to each security
        count = sum(x.Direction != InsightDirection.Flat for x in LastActiveInsights)
        percent = Zero if count == Zero else (Weights.MarginMultiplier / count)
        
        for insight in LastActiveInsights:
            
            if insight.Direction == InsightDirection.Down:
                self.Percents[insight] = insight.Direction * np.minimum(percent, Weights.ShortUVXY)
                
            else:
                 self.Percents[insight] = insight.Direction * percent


##-----------------Creates and returns Portfolio Targets------------------------------------------------------------##

    def CreateTargets(self, algorithm, insights):
        
        self.ErrorSymbols = {}    
        targets = []

        self.DetermineTargetPercent(algorithm, insights)
        
        targets.extend(self.CreateLongVolPositions(algorithm, insights))
        targets.extend(self.CreateShortVolPositions(algorithm, insights))
        targets.extend(self.CreateSPXLPositions(algorithm, insights))
        targets.extend(self.CreateSPXSPositions(algorithm, insights))
        targets.extend(self.CreateSQQQPositions(algorithm, insights))
        targets.extend(self.CreateTQQQPositions(algorithm, insights))
        targets.extend(self.CreateFlatPositions(algorithm,  insights))
        
    #    targets.extend(self.CreateDebugPositions(algorithm,  insights))
        
        # Create flatten target for each security that was removed from the universe
        if self.RemovedSymbols is not None:
            universeDeselectionTargets = [ PortfolioTarget(symbol, Zero) for symbol in self.RemovedSymbols ]
            targets.extend(universeDeselectionTargets)
            self.RemovedSymbols = None
            
        self.CummulativeInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)
        
        self.AnnualCleanUp(algorithm)
        
        return targets  

                
##-----------------Generates Long Vol targets separately------------------------------------------------------------##

    def CreateLongVolPositions(self, algorithm, insights):
        
        LongVolTargets = []
        
        if (algorithm.UtcTime <= self.LongVolNextExpiryTime and algorithm.UtcTime <= self.LongVolRebalancingTime and len(insights) == Zero and self.RemovedSymbols is None):
            return LongVolTargets
            
        for insight in insights:
            if insight.SourceModel == self.LongVolSourceModel:
                self.LongVolInsightCollection.Add(insight)
        
        # Get insight that haven't expired of each symbol that is still in the universe
        ActiveInsights = self.LongVolInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the last generated active insight
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])
        
        self.ErrorSymbols = {}
        for insight in LastActiveInsights:
            if insight in self.Percents:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, self.Percents[insight])
                if not target is None:
                    LongVolTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol
                    
            else:
                self.ErrorSymbols[symbol] = symbol

        # Get expired insights and create flatten targets for each symbol
        ExpiredInsights = self.LongVolInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)
        
        for insight in ExpiredInsights:
            self.DictCleanUp.append(insight)

        ExpiredTargets = []
        for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
            if not self.LongVolInsightCollection.HasActiveInsights(symbol, algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                ExpiredTargets.append(PortfolioTarget(symbol, Zero))
                continue

        LongVolTargets.extend(ExpiredTargets)

        self.LongVolNextExpiryTime = self.LongVolInsightCollection.GetNextExpiryTime()
        
        if self.LongVolNextExpiryTime is None:
            self.LongVolNextExpiryTime = UTCMIN

        self.LongVolRebalancingTime = self.LongVolRebalancingFunc(algorithm.UtcTime)  
            
        return LongVolTargets
        
        
        
##-----------------Generates Short Vol targets separately-----------------------------------------------------------##

    def CreateShortVolPositions(self, algorithm, insights):
        
        ShortVolTargets = []
        
        if (algorithm.UtcTime <= self.ShortVolNextExpiryTime and algorithm.UtcTime <= self.ShortVolRebalancingTime and len(insights) == Zero and self.RemovedSymbols is None):
            return ShortVolTargets
        
        for insight in insights:
            if insight.SourceModel == self.ShortVolSourceModel:
                self.ShortVolInsightCollection.Add(insight) 
        
        # Get insight that haven't expired of each symbol that is still in the universe
        ActiveInsights = self.ShortVolInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the last generated active insight
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])

        self.ErrorSymbols = {}
        for insight in LastActiveInsights:
            if insight in self.Percents:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, self.Percents[insight])
                if not target is None:
                    ShortVolTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol
                    
            else:
                self.ErrorSymbols[symbol] = symbol

        # Get expired insights and create flatten targets for each symbol
        ExpiredInsights = self.ShortVolInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)

        for insight in ExpiredInsights:
            self.DictCleanUp.append(insight)
            
        ExpiredTargets = []
        for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
            if not self.ShortVolInsightCollection.HasActiveInsights(symbol, algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                ExpiredTargets.append(PortfolioTarget(symbol, Zero))
                continue

        ShortVolTargets.extend(ExpiredTargets)

        self.ShortVolNextExpiryTime = self.ShortVolInsightCollection.GetNextExpiryTime()
        
        if self.ShortVolNextExpiryTime is None:
            self.ShortVolNextExpiryTime = UTCMIN

        self.ShortVolRebalancingTime = self.ShortVolRebalancingFunc(algorithm.UtcTime)
        
        return ShortVolTargets
        
    
##-----------------Generates SPXL targets separately----------------------------------------------------------------##

    def CreateSPXLPositions(self, algorithm, insights):
        
        SPXLTargets = []
        
        if (algorithm.UtcTime <= self.SPXLNextExpiryTime and algorithm.UtcTime <= self.SPXLRebalancingTime and len(insights) == Zero and self.RemovedSymbols is None):
            return SPXLTargets
        
        for insight in insights:
            if insight.SourceModel == self.SPXLSourceModel:
                self.SPXLInsightCollection.Add(insight) 
        
        # Get insight that haven't expired of each symbol that is still in the universe
        ActiveInsights = self.SPXLInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the last generated active insight
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])

        self.ErrorSymbols = {}
        for insight in LastActiveInsights:
            if insight in self.Percents:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, self.Percents[insight])
                if not target is None:
                    SPXLTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol
                    
            else:
                self.ErrorSymbols[symbol] = symbol

        # Get expired insights and create flatten targets for each symbol
        ExpiredInsights = self.SPXLInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)

        for insight in ExpiredInsights:
            self.DictCleanUp.append(insight)
            
        ExpiredTargets = []
        for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
            if not self.SPXLInsightCollection.HasActiveInsights(symbol, algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                ExpiredTargets.append(PortfolioTarget(symbol, Zero))
                continue

        SPXLTargets.extend(ExpiredTargets)

        self.SPXLNextExpiryTime = self.SPXLInsightCollection.GetNextExpiryTime()
        
        if self.SPXLNextExpiryTime is None:
            self.SPXLNextExpiryTime = UTCMIN

        self.SPXLRebalancingTime = self.SPXLRebalancingFunc(algorithm.UtcTime)
        
        return SPXLTargets
        

##-----------------Generates SPXS targets separately----------------------------------------------------------------##

    def CreateSPXSPositions(self, algorithm, insights):
        
        SPXSTargets = []
        
        if (algorithm.UtcTime <= self.SPXSNextExpiryTime and algorithm.UtcTime <= self.SPXSRebalancingTime and len(insights) == Zero and self.RemovedSymbols is None):
            return SPXSTargets
        
        for insight in insights:
            if insight.SourceModel == self.SPXSSourceModel:
                self.SPXSInsightCollection.Add(insight) 
        
        # Get insight that haven't expired of each symbol that is still in the universe
        ActiveInsights = self.SPXSInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the last generated active insight
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])

        self.ErrorSymbols = {}
        for insight in LastActiveInsights:
            if insight in self.Percents:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, self.Percents[insight])
                if not target is None:
                    SPXSTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol
                    
            else:
                self.ErrorSymbols[symbol] = symbol

        # Get expired insights and create flatten targets for each symbol
        ExpiredInsights = self.SPXSInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)

        for insight in ExpiredInsights:
            self.DictCleanUp.append(insight)
            
        ExpiredTargets = []
        for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
            if not self.SPXSInsightCollection.HasActiveInsights(symbol, algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                ExpiredTargets.append(PortfolioTarget(symbol, Zero))
                continue

        SPXSTargets.extend(ExpiredTargets)

        self.SPXSNextExpiryTime = self.SPXSInsightCollection.GetNextExpiryTime()
        
        if self.SPXSNextExpiryTime is None:
            self.SPXSNextExpiryTime = UTCMIN

        self.SPXSRebalancingTime = self.SPXSRebalancingFunc(algorithm.UtcTime)
        
        return SPXSTargets
        
        
##-----------------Generates TQQQ targets separately----------------------------------------------------------------##

    def CreateTQQQPositions(self, algorithm, insights):
        
        TQQQTargets = []
        
        if (algorithm.UtcTime <= self.TQQQNextExpiryTime and algorithm.UtcTime <= self.TQQQRebalancingTime and len(insights) == Zero and self.RemovedSymbols is None):
            return TQQQTargets
        
        for insight in insights:
            if insight.SourceModel == self.TQQQSourceModel:
                self.TQQQInsightCollection.Add(insight) 
        
        # Get insight that haven't expired of each symbol that is still in the universe
        ActiveInsights = self.TQQQInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the last generated active insight
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])

        self.ErrorSymbols = {}
        for insight in LastActiveInsights:
            if insight in self.Percents:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, self.Percents[insight])
                if not target is None:
                    TQQQTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol
            else:
                self.ErrorSymbols[symbol] = symbol

        # Get expired insights and create flatten targets for each symbol
        ExpiredInsights = self.TQQQInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)

        for insight in ExpiredInsights:
            self.DictCleanUp.append(insight)
            
        ExpiredTargets = []
        for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
            if not self.TQQQInsightCollection.HasActiveInsights(symbol, algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                ExpiredTargets.append(PortfolioTarget(symbol, Zero))
                continue

        TQQQTargets.extend(ExpiredTargets)

        self.TQQQNextExpiryTime = self.TQQQInsightCollection.GetNextExpiryTime()
        
        if self.TQQQNextExpiryTime is None:
            self.TQQQNextExpiryTime = UTCMIN

        self.TQQQRebalancingTime = self.TQQQRebalancingFunc(algorithm.UtcTime)
        
        return TQQQTargets
        

##-----------------Generates SQQQ targets separately----------------------------------------------------------------##

    def CreateSQQQPositions(self, algorithm, insights):
        
        SQQQTargets = []
        
        if (algorithm.UtcTime <= self.SQQQNextExpiryTime and algorithm.UtcTime <= self.SQQQRebalancingTime and len(insights) == Zero and self.RemovedSymbols is None):
            return SQQQTargets
        
        for insight in insights:
            if insight.SourceModel == self.SQQQSourceModel:
                self.SQQQInsightCollection.Add(insight) 
        
        # Get insight that haven't expired of each symbol that is still in the universe
        ActiveInsights = self.SQQQInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the last generated active insight
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])

        self.ErrorSymbols = {}
        for insight in LastActiveInsights:
            if insight in self.Percents:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, self.Percents[insight])
                if not target is None:
                    SQQQTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol

            else:
                self.ErrorSymbols[symbol] = symbol
                
        # Get expired insights and create flatten targets for each symbol
        ExpiredInsights = self.SQQQInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)

        for insight in ExpiredInsights:
            self.DictCleanUp.append(insight)
            
        ExpiredTargets = []
        for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
            if not self.SQQQInsightCollection.HasActiveInsights(symbol, algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                ExpiredTargets.append(PortfolioTarget(symbol, Zero))
                continue

        SQQQTargets.extend(ExpiredTargets)

        self.SQQQNextExpiryTime = self.SQQQInsightCollection.GetNextExpiryTime()
        
        if self.SQQQNextExpiryTime is None:
            self.SQQQNextExpiryTime = UTCMIN

        self.SQQQRebalancingTime = self.SQQQRebalancingFunc(algorithm.UtcTime)
        
        return SQQQTargets        
        

##-----------------Generates Flat targets separately----------------------------------------------------------------##    

    def CreateFlatPositions(self, algorithm, insights):
        
        FlatTargets = []
        
        self.ErrorSymbols = {}
        for insight in insights:
            if insight.Direction == InsightDirection.Flat:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, Zero)
                if not target is None:
                    FlatTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol    
                
        return FlatTargets   


##-----------------Handles changes to the universe------------------------------------------------------------------##

    def OnSecuritiesChanged(self, algorithm, changes):
    
        # Get removed symbol and invalidate them in the insight collections
        self.RemovedSymbols = [x.Symbol for x in changes.RemovedSecurities]
        
        self.LongVolInsightCollection.Clear(self.RemovedSymbols)
        self.ShortVolInsightCollection.Clear(self.RemovedSymbols)
        self.FlatInsightCollection.Clear(self.RemovedSymbols)
        
        

##-----------------Annual Clean Up----------------------------------------------------------------------------------##

    def AnnualCleanUp(self, algorithm):
        
        self.ErrorSymbols = {}
        
        ActiveInsights = self.CummulativeInsightCollection.GetActiveInsights(algorithm.UtcTime)
        
        # Once per year update the VIX statistics with the previuos 4000 days data
        if algorithm.UtcTime.date() == self.GetNextWeekday(date(algorithm.UtcTime.year, 1, 3)):
            for insight in self.DictCleanUp:
                if insight not in ActiveInsights and insight in self.Percents:
                    self.Percents.pop(insight)
                

##-----------------Return the next weekday from specified date--------------------------------##

    def GetNextWeekday(algorithm, RandomDate):
        RandomDate += OneDay
        
        while RandomDate.weekday() > int(4): # Mon-Fri are 0-4
            RandomDate += OneDay
            
        return RandomDate
        
        
##-----------------Debugging----------------------------------------------------------------##

    def CreateDebugPositions(self, algorithm, insights):
        
        DebugTargets = []
        
        if (algorithm.UtcTime <= self.DebugNextExpiryTime and algorithm.UtcTime <= self.DebugRebalancingTime and len(insights) == Zero and self.RemovedSymbols is None):
            return DebugTargets
        
        for insight in insights:
            if insight.SourceModel == self.DebugSourceModel:
                self.DebugInsightCollection.Add(insight) 
        
        # Get insight that haven't expired of each symbol that is still in the universe
        ActiveInsights = self.DebugInsightCollection.GetActiveInsights(algorithm.UtcTime)

        # Get the last generated active insight
        LastActiveInsights = []
        for symbol, g in groupby(ActiveInsights, lambda x: x.Symbol):
            LastActiveInsights.append(sorted(g, key = lambda x: x.GeneratedTimeUtc)[-1])

        self.ErrorSymbols = {}
        for insight in LastActiveInsights:
            if insight in self.Percents:
                symbol = insight.Symbol
                target = PortfolioTarget.Percent(algorithm, symbol, self.Percents[insight])
                if not target is None:
                    DebugTargets.append(target)
                else:
                    self.ErrorSymbols[symbol] = symbol

            else:
                self.ErrorSymbols[symbol] = symbol
                
        # Get expired insights and create flatten targets for each symbol
        ExpiredInsights = self.DebugInsightCollection.RemoveExpiredInsights(algorithm.UtcTime)

        for insight in ExpiredInsights:
            self.DictCleanUp.append(insight)
            
        ExpiredTargets = []
        for symbol, f in groupby(ExpiredInsights, lambda x: x.Symbol):
            if not self.DebugInsightCollection.HasActiveInsights(symbol, algorithm.UtcTime) and not symbol in self.ErrorSymbols:
                ExpiredTargets.append(PortfolioTarget(symbol, Zero))
                continue

        DebugTargets.extend(ExpiredTargets)

        self.DebugNextExpiryTime = self.DebugInsightCollection.GetNextExpiryTime()
        
        if self.DebugNextExpiryTime is None:
            self.DebugNextExpiryTime = UTCMIN

        self.DebugRebalancingTime = self.DebugRebalancingFunc(algorithm.UtcTime)
        
        return DebugTargets