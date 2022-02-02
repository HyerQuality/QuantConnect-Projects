from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Indicators")
AddReference("QuantConnect.Common")

from System import *
from QuantConnect import *
from QuantConnect.Data import *
from QuantConnect.Algorithm import *
from QuantConnect.Indicators import *
from System.Collections.Generic import List


class EmaCrossUniverseSelectionAlgorithm(QCAlgorithm):

    def Initialize(self):
        '''If the filter returns nothing, keep 60% invested in SPY.  Maximium drawdown allowed is 2.5% per investment, check every minute.  Liquidate end of day to avoid overnight risk.
            Filter stocks such that all entries are liquid, breaking out, and of the selected breakouts the top 24 breaking out the hardest. '''

        stockPlot_1 = Chart('Universe Size')
        stockPlot_2 = Chart('Margin')
        
        
        self.SetStartDate(2012,1,1)  #Set Start Date
        self.SetEndDate(datetime.now().date() - timedelta(1)) #Set End Date
        #self.SetEndDate(2018,1,1)    #Set End Date
        self.SetCash(240000)           #Set Strategy Cash

        self.UniverseSettings.Resolution = Resolution.Hour

        self.marginRemaining = self.Portfolio.MarginRemaining
        #self.coarse_count = 24
        self.weighting = 0.10
        self.maximumDrawdownPercent = 0.025
        self.averages = { };

        # this add universe method accepts two parameters:
        # - coarse selection function: accepts an IEnumerable<CoarseFundamental> and returns an IEnumerable<Symbol>
        self.AddEquity("SPY", Resolution.Hour)   
        self.AddUniverse(self.CoarseSelectionFunction)
        
        #self.SetAlpha(ConstantAlphaModel(InsightType.Price, InsightDirection.Up, timedelta(days = 2)))        

        for y in range (1,390,1):    
            self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", y), self.CheckDailyLosses)
            
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 15), self.Chart)            
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 15), self.BuyFunc)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 15), self.SellFunc) 
        
        self.SetWarmup(30)
        
#Charts
    def Chart(self):
        self.Plot('Universe Size', 'Asset Count', self.ActiveSecurities.Count)
        self.Plot('Margin', 'Margin Remaining', self.marginRemaining)
#OnData 
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.'''
        '''Arguments:
            data: Slice object keyed by symbol containing the stock data'''
            
        if self.ActiveSecurities.Count > 1:
            self.weighting = 1.0 / self.ActiveSecurities.Count
            
            
    # sort the data by daily dollar volume and take the top 'NumberOfSymbols'
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
        
        #self.Log("Buy Function Has Fired.")
        
        #Used to control leverage
        self.OpenOrders = self.Transactions.GetOpenOrders()
        
        for security in self.Securities.Values:
            if not self.Securities[security.Symbol].Invested and self.Securities[security.Symbol] not in self.OpenOrders:
                self.SetHoldings(security.Symbol, self.weighting) 
                
#Sell
    def SellFunc(self):
        
        #self.Log("Sell Function Has Fired.")
        
        self.Liquidate()
            
        return    
    
#CheckLosses            
    #Check intraday losses gains      
    def CheckDailyLosses(self):
        
        for security in self.Securities.Values:
            pnl = security.Holdings.UnrealizedProfitPercent
            
            if pnl < -self.maximumDrawdownPercent:
                self.SetHoldings(security.Symbol, -self.weighting)
                self.Log("{0} exceeded drawdown".format(str(security.Symbol)))
                
            else:    
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