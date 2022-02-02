from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Indicators")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm.Framework")

from System import *
from QuantConnect import *
from QuantConnect.Data import *
from QuantConnect.Algorithm import *
from QuantConnect.Indicators import *
from System.Collections.Generic import List
from QuantConnect.Algorithm.Framework.Portfolio import PortfolioTarget
from QuantConnect.Algorithm.Framework.Risk import RiskManagementModel


class EmaCrossUniverseSelectionAlgorithm(QCAlgorithm):

    def Initialize(self):
        '''If the filter returns nothing, keep 60% invested in SPY.  Maximium drawdown allowed is 2.5% per investment, check every minute.  Liquidate end of day to avoid overnight risk.
            Filter stocks such that all entries are liquid, breaking out, and of the selected breakouts the top 24 breaking out the hardest. '''

        stockPlot_1 = Chart('Universe Size')
        stockPlot_2 = Chart('Margin')
        
        
        self.SetStartDate(2019,1,1)  #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1)) #Set End Date
        #self.SetEndDate(2018,1,1)    #Set End Date
        #self.SetCash(200000)      #Set Strategy Cash

        self.UniverseSettings.Resolution = Resolution.Hour

        self.marginRemaining = self.Portfolio.MarginRemaining
        self.orderTiming = 15
        self.averages = { };

        # this add universe method accepts two parameters:
        # - coarse selection function: accepts an IEnumerable<CoarseFundamental> and returns an IEnumerable<Symbol>
        self.AddEquity("SPY", Resolution.Hour)   
        self.AddUniverse(self.CoarseSelectionFunction)
            
        #self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 15), self.Chart)            
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", self.orderTiming), self.BuyFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", self.orderTiming), self.SellFunc) 
        
        self.SetWarmUp(16)
        
#Charts
    def Chart(self):
        self.Plot('Universe Size', 'Asset Count', self.ActiveSecurities.Count)
        self.Plot('Margin', 'Margin Remaining', self.marginRemaining)
#OnData 
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.'''
        '''Arguments:
            data: Slice object keyed by symbol containing the stock data'''
            
        self.weighting = 1.196 / (self.ActiveSecurities.Count+1)

#Universe Filter            
    # sort the data by volume and price, apply the moving average crossver, and take the top 24 sorted results based on breakout magnitude'
    def CoarseSelectionFunction(self, coarse):
        
        filtered = [ x for x in coarse if (x.Volume > 2000000 and x.Price > 20) ]  
        
        # We are going to use a dictionary to refer the object that will keep the moving averages
        for cf in filtered:
            if cf.Symbol not in self.averages:
                self.averages[cf.Symbol] = SymbolData(cf.Symbol)

            # Updates the SymbolData object with current EOD price
            avg = self.averages[cf.Symbol]
            avg.update(cf.EndTime, cf.AdjustedPrice)

        # Filter the values of the dict: we only want up-trending securities
        values = list(filter(lambda x: x.is_uptrend, self.averages.values()))

        # Sorts the values of the dict: we want those with greater difference between the moving averages
        values.sort(key=lambda x: x.scale, reverse=True)
            
        # we need to return only the symbol objects
        return [ x.symbol for x in values[:24] ]
        

    # this event fires whenever we have changes to our universe
    def OnSecuritiesChanged(self, changes):
        self.changes = changes
        
        # liquidate removed securities
        for security in changes.RemovedSecurities:
            if security.Invested:
                self.Liquidate(security.Symbol)
                
            self.RemoveSecurity(security.Symbol)
            
#Buy       
    def BuyFunc(self):
        
        #Used to control leverage
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        #Update weighting
        #self.weighting = 2.0 / (self.ActiveSecurities.Count+13)
        
        for security in self.Securities.Values:
            if not self.Securities[security.Symbol].Invested and self.Securities[security.Symbol] not in self.OpenOrders:
                self.SetHoldings(security.Symbol, self.weighting) 
                
#Sell
    def SellFunc(self):
        
        self.Liquidate()
            
        return    


class SymbolData(object):
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast = ExponentialMovingAverage(2)
        self.slow = ExponentialMovingAverage(15)
        self.is_uptrend = False
        self.scale = 0

    def update(self, time, value):
        if self.fast.Update(time, value) and self.slow.Update(time, value):
            fast = self.fast.Current.Value
            slow = self.slow.Current.Value
            self.is_uptrend = ((fast / slow)) > 1.05

        if self.is_uptrend:
            self.scale = (fast - slow) / ((fast + slow) / 2.0)
            
            
class MaximumDrawdownPercentPerSecurity(RiskManagementModel):
    '''Provides an implementation of IRiskManagementModel that limits the drawdown per holding to the specified percentage'''

    def __init__(self, maximumDrawdownPercent = 0.025):
        '''Initializes a new instance of the MaximumDrawdownPercentPerSecurity class'''
 
        self.maximumDrawdownPercent = -abs(maximumDrawdownPercent)

    def ManageRisk(self, algorithm, targets):
        '''Manages the algorithm's risk at each time step
        Args:
            algorithm: The algorithm instance
            targets: The current portfolio targets to be assessed for risk'''
        targets = []
        for kvp in algorithm.Securities:
            security = kvp.Value

            if not security.Invested:
                continue

            pnl = security.Holdings.UnrealizedProfitPercent
            if pnl < self.maximumDrawdownPercent:
                # liquidate
                targets.append(PortfolioTarget(security.Symbol, -self.weighting))

        return targets