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
        '''If the filter returns nothing, keep 60% invested in SPY.  Maximium drawdown allowed is 1.2% per investment. Liquidate end of day to avoid overnight risk.
            Filter stocks such that all entries are liquid, breaking out, and of the selected breakouts the top 24 breaking out the hardest. '''
            
        stockPlot_1 = Chart('Weight per Active Security')
        stockPlot_2 = Chart('Margin Remaining')
        stockPlot_3 = Chart('Active Securities')
        
        self.SetStartDate(2012,1,1)  #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1)) #Set End Date
        #self.SetEndDate(2013,1,1)    #Set End Date
        self.SetCash(200000)      #Set Strategy Cash

        self.UniverseSettings.Resolution = Resolution.Hour
        self.AddRiskManagement( MaximumDrawdownPercentPerSecurity() )

        self.marginRemaining = self.Portfolio.MarginRemaining
        self.averages = { };

        # this add universe method accepts two parameters:
        # - coarse selection function: accepts an IEnumerable<CoarseFundamental> and returns an IEnumerable<Symbol>
        self.AddEquity("SPY", Resolution.Hour)   
        self.AddUniverse(self.CoarseSelectionFunction)
        
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.At(9,45), self.BuyFunc)
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.At(15,45), self.SellFunc)
        
        self.SetWarmUp(16)
        
#OnData 
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.'''
        '''Arguments:
            data: Slice object keyed by symbol containing the stock data'''
            
        #Constantly update the universe moving averages and if a slice does not contain any data for the security, remove it from the universe
        if self.IsMarketOpen("SPY"): 
            
            if bool(self.averages):   
                
                for x in self.Securities.Values:
                    
                    if data.ContainsKey(x.Symbol):
                        
                        if data[x.Symbol] is None:
                            continue 
                        
                        avg = self.averages[x.Symbol]
                        avg.update(data[x.Symbol].EndTime, data[x.Symbol].Open)
    
                    else:
                        self.RemoveSecurity(x.Symbol)
#Universe Filter            
    # sort the data by volume and price, apply the moving average crossver, and take the top 24 sorted results based on breakout magnitude
    def CoarseSelectionFunction(self, coarse):
        
        filtered = [ x for x in coarse if (x.Volume > 5000000 and x.Price > 60) ]  
        
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
        
        for x in values[:10]:
            self.Log('symbol: ' + str(x.symbol.Value) + '  scale: ' + str(x.scale))        
            
        # we need to return only the symbol objects
        return [ x.symbol for x in values[:10] ]
        

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
        
        #Maintain weight proportion based on active securities in the universe        
        self.weighting = 1.21 / (self.ActiveSecurities.Count+1)         
        
        self.Plot('Weight per Active Security', 'Weight per Security', self.weighting)
        
        for security in self.ActiveSecurities.Values:
            if not self.ActiveSecurities[security.Symbol].Invested and self.ActiveSecurities[security.Symbol] not in self.OpenOrders:
                self.SetHoldings(security.Symbol, self.weighting) 
        
        self.marginRemaining = self.Portfolio.MarginRemaining
        
        self.Plot('Margin Remaining', 'Margin', self.marginRemaining)
        self.Plot('Active Securities', 'Number of Active Securities', self.ActiveSecurities.Count)
                
#Sell
    def SellFunc(self):
        
        self.Liquidate()
            
        return    
    

#EMA Crossover Class
class SymbolData(object):
    
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast = ExponentialMovingAverage(2)
        self.slow = ExponentialMovingAverage(15)
        self.is_uptrend = False
        self.scale = None

    def update(self, time, value):
        if self.fast.Update(time, value) and self.slow.Update(time, value):
            fast = self.fast.Current.Value
            slow = self.slow.Current.Value
            self.is_uptrend = (fast / slow) > 1.05

        if self.is_uptrend:
            self.scale = (fast - slow) / ((fast + slow) / 2.0)
            
            
#Risk Management            
class MaximumDrawdownPercentPerSecurity(RiskManagementModel):
    '''Provides an implementation of IRiskManagementModel that limits the drawdown per holding to the specified percentage'''

    def __init__(self, maximumDrawdownPercent = 0.012):
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
                targets.append(PortfolioTarget(security.Symbol, 0))

        return targets