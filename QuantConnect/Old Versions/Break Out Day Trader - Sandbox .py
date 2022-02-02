from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Indicators")
AddReference("QuantConnect.Common")

from System import *
from QuantConnect import *
from datetime import timedelta
from QuantConnect.Data import *
from QuantConnect.Algorithm import *
from QuantConnect.Indicators import *
from System.Collections.Generic import List


class BreakoutDayTrader(QCAlgorithm):

    def Initialize(self):
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialized.'''

        stockPlot_1 = Chart('Active Securities')
        stockPlot_2 = Chart('VIX Close')
        
        
        self.SetStartDate(2009,1,1)  #Set Start Date
        #self.SetEndDate(datetime.now().date() - timedelta(1))        
        self.SetEndDate(2019,9,13)    #Set End Date
        self.SetCash(10000000)           #Set Strategy Cash

        self.UniverseSettings.Resolution = Resolution.Hour
        self.UniverseSettings.Leverage = int(2)

        self.coarse_count = int(50)
        self.__numberOfSymbolsFine = int(30)
        self.scaleLowExtreme = int(100)
        self.scaleHighExtreme = int(1000)
        self.lowVol = float(12)
        self.highVol = float(25)
        self.historyTimeFrame = 17
        self.targetPercent = float(0.005)
        self.Zero = int(0)
        self.startTime = int(11)
        self.minAvgVolume = int(1500000)
        self.minPrice = int(20)
        self.closingVIX = int(0)
        self.maxList = int(3)
        self.VixList = [self.Zero,self.Zero,self.Zero]
        self.selloff = False
        
        self.averages = { };

        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)
        self.AddData(Vix, "VIX", Resolution.Daily)
        
        self.SetSecurityInitializer(lambda security: security.SetFeeModel(ConstantFeeModel(0)))

        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.Every(timedelta(minutes=20)), self.SellFunc)
        
    def SellFunc(self):
        for security in self.Securities:
            if self.Portfolio[security.Key].Invested:
                    if self.Portfolio[security.Key].UnrealizedProfitPercent > 0.02:
                        self.Liquidate(security.Key)                
        
    def OnData(self, data):
        
        if data.ContainsKey("VIX"):
            self.closingVIX = data["VIX"].Close
            if len(self.VixList) < self.maxList:
                self.VixList.append(self.closingVIX)
            else:
                self.VixList[0] = self.VixList[1]
                self.VixList[1] = self.VixList[2]
                self.VixList[2] = self.closingVIX
                
                if self.VixList[2] > (self.VixList[1] * float(1.10)):
                    self.selloff = True
                else:
                    self.selloff = False
                    
            self.Plot('VIX Close', 'VIX Close', self.closingVIX)        
        
        if self.Time.hour < self.startTime: return
        
        for security in self.averages.values():
        
            if data.ContainsKey(security.symbol) and data[security.symbol] != None and str(data[security.symbol]) != "VIX":
                self.averages[security.symbol].update(data[security.symbol].EndTime, data[security.symbol].Close)
        
        for security in self.ActiveSecurities.Values:
            
            self.weighting = round( 1.0/(self.ActiveSecurities.Count+1), 2)
        
            if self.selloff:
                
                if self.Portfolio[security.Symbol].Invested and data.ContainsKey(security.Symbol) and data[security.Symbol] != None and str(security.Symbol) != "VIX":
                    
                    if abs(self.Portfolio[security.Symbol].UnrealizedProfitPercent) > self.targetPercent:
                        self.Liquidate(security.Symbol)
                        
                    else: continue
        
                if not self.Portfolio[security.Symbol].Invested and data.ContainsKey(security.Symbol) and data[security.Symbol] != None and str(security.Symbol) != "VIX":
                    
                    if self.averages[security.Symbol].scale <= self.scaleLowExtreme:
                        if self.averages[security.Symbol].is_uptrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, -self.weighting)
                        
                        elif self.averages[security.Symbol].is_downtrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, -self.weighting)
                            
                    elif self.scaleHighExtreme <= self.averages[security.Symbol].scale:
                        if self.averages[security.Symbol].is_downtrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, -self.weighting)
                        
                        elif self.averages[security.Symbol].is_uptrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, -self.weighting)
                            
            elif self.closingVIX >= self.lowVol and self.VixList[2] > (self.VixList[1] * float(0.90)) :
                
                if self.Portfolio[security.Symbol].Invested and data.ContainsKey(security.Symbol) and data[security.Symbol] != None and str(security.Symbol) != "VIX":
                    
                    if abs(self.Portfolio[security.Symbol].UnrealizedProfitPercent) > self.targetPercent:
                        self.Liquidate(security.Symbol)
                        
                    else: continue
        
                if not self.Portfolio[security.Symbol].Invested and data.ContainsKey(security.Symbol) and data[security.Symbol] != None and str(security.Symbol) != "VIX":
                    
                    if self.averages[security.Symbol].scale <= self.scaleLowExtreme:
                        if self.averages[security.Symbol].is_uptrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, self.weighting)
                            
                            self.LimitOrder(security.Symbol, -self.Portfolio[security.Symbol].Quantity, round( self.Portfolio[security.Symbol].AveragePrice * 1.025,2))
                        
                        elif self.averages[security.Symbol].is_downtrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, self.weighting)
                            
                    elif self.scaleHighExtreme <= self.averages[security.Symbol].scale:
                        if self.averages[security.Symbol].is_downtrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, -self.weighting)
                            
                            self.LimitOrder(security.Symbol, -self.Portfolio[security.Symbol].Quantity, round( self.Portfolio[security.Symbol].AveragePrice * 0.975,2))                            
                        
                        elif self.averages[security.Symbol].is_uptrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, -self.weighting)
                          
            else:
                
                if self.Portfolio[security.Symbol].Invested and data.ContainsKey(security.Symbol) and data[security.Symbol] != None and str(security.Symbol) != "VIX":
                    
                    if abs(self.Portfolio[security.Symbol].UnrealizedProfitPercent) > self.targetPercent:
                        self.Liquidate(security.Symbol)
                        
                    else: continue
        
                if not self.Portfolio[security.Symbol].Invested and data.ContainsKey(security.Symbol) and data[security.Symbol] != None and str(security.Symbol) != "VIX":
                    
                    if self.averages[security.Symbol].scale <= self.scaleLowExtreme:
                        if self.averages[security.Symbol].is_uptrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, self.weighting)
                        
                        elif self.averages[security.Symbol].is_downtrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, self.weighting)
                            
                    elif self.scaleHighExtreme <= self.averages[security.Symbol].scale:
                        if self.averages[security.Symbol].is_downtrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, self.weighting)
                        
                        elif self.averages[security.Symbol].is_uptrend and data[security.Symbol].Price > self.Zero:
                            self.Transactions.CancelOpenOrders(security.Symbol)
                            self.SetHoldings(security.Symbol, self.weighting)
               
        return
          
    # sort the data by daily dollar volume and take the top 'NumberOfSymbols'
    def CoarseSelectionFunction(self, coarse):

        filtered = [ x for x in coarse if (x.Volume >= self.minAvgVolume and x.Price >= self.minPrice and x.HasFundamentalData ) ]
        
    
        # We are going to use a dictionary to refer the object that will keep the moving averages
        for cf in filtered:
            if cf.Symbol not in self.averages:
                self.averages[cf.Symbol] = SymbolData(cf.Symbol)
                
                self.history = self.History(cf.Symbol, self.historyTimeFrame, Resolution.Hour)
                
                if not self.history.empty:
                    self.historySymbol = str(cf.Symbol) 
                    self.averages[cf.Symbol].WarmUpIndicators(self.history)                

            # Updates the SymbolData object with current EOD price
            avg = self.averages[cf.Symbol]
            avg.update(cf.EndTime, cf.AdjustedPrice)

        # Filter the values of the dict: we only want up-trending securities
        values = list(filter(lambda x: x.is_trending, self.averages.values()))

        # Sorts the values of the dict: we want those with greater difference between the moving averages
        values.sort(key=lambda x: x.scale, reverse=True)

        # we need to return only the symbol objects
        return [ x.symbol for x in values[:self.coarse_count] ]

            
    def FineSelectionFunction(self, fine):

        sortedByPERatio = sorted(fine, key=lambda x: x.ValuationRatios.PERatio, reverse=False)
        sortedByPBRatio = sorted(sortedByPERatio[:40], key=lambda x: x.ValuationRatios.PBRatio, reverse=False)
                
        sortedByPBRatio.sort(key=lambda x: self.averages[x.Symbol].scale, reverse=True)
            
        # take the top entries from our sorted collection
        return [ x.Symbol for x in sortedByPBRatio[:self.__numberOfSymbolsFine] ]
            
        
        
# Universe Changes
    def OnSecuritiesChanged(self, changes):
        
    #Securities Removed
        for security in changes.RemovedSecurities:
            self.Liquidate(security.Symbol)
            self.Plot('Active Securities', 'Number of Active Securities', self.ActiveSecurities.Count)  
    
    #Securities Added
        for security in changes.AddedSecurities:
            self.Plot('Active Securities', 'Number of Active Securities', self.ActiveSecurities.Count) 
            return
        
class SymbolData(object):
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast = ExponentialMovingAverage(2)
        self.slow = ExponentialMovingAverage(16)
        self.rsi = RelativeStrengthIndex(14)
        self.std = StandardDeviation(14)
        self.is_uptrend = False
        self.is_downtrend = False
        self.is_trending = False
        self.scale = int(0)
        self.confirm_uptrend = float(1.11)
        self.confirm_downtrend = float(0.89)

    def update(self, time, value):
        if self.fast.Update(time, value) and self.slow.Update(time, value) and self.std.Update(time, value) and self.rsi.Update(time, value):
            fast = self.fast.Current.Value
            slow = self.slow.Current.Value
            rsi = self.rsi.Current.Value
            std = self.std.Current.Value
            self.is_uptrend = ( (fast / slow) > self.confirm_uptrend)
            self.is_downtrend = ( (fast / slow) < self.confirm_downtrend)
            
            if self.is_uptrend or self.is_downtrend:
                self.is_trending = True
            else:
                self.is_trending = False

        if self.is_uptrend:
            self.scale = round( rsi / ( (fast - slow) / ((fast+slow) / 2.0) ), 3) * std
            
        if self.is_downtrend:
            self.scale = round( ( (slow - fast) / ((fast + slow) / 2.0) ) * (rsi/100), 3) * std

    def WarmUpIndicators(self, history):
        for index, row in history.loc[str(self.symbol)].iterrows():
            self.fast.Update(index, row["close"])
            self.slow.Update(index, row["close"])
            self.rsi.Update(index, row["close"])
            self.std.Update(index, row["close"]) 
            
            
class Vix(PythonData):
    '''New VIX Object'''

    def GetSource(self, config, date, isLiveMode):
        #if isLiveMode:
        return SubscriptionDataSource("http://www.cboe.com/publish/scheduledtask/mktdata/datahouse/vixcurrent.csv", SubscriptionTransportMedium.RemoteFile);

    def Reader(self, config, line, date, isLiveMode):
        
        # New VIX object
        index = Vix()
        index.Symbol = config.Symbol   
        
        #if isLiveMode:
        if not (line.strip() and line[0].isdigit()): return None


        try:
            # Example File Format:
            # Date,       Open       High        Low       Close     Volume      Turnover
            # 1/1/2008  7792.9    7799.9     7722.65    7748.7    116534670    6107.78
            data = line.split(',')
            index.Time = datetime.strptime(data[0], "%m/%d/%Y")
            index.Value = data[4]
            index["Close"] = float(data[4])


        except ValueError:
                # Do nothing
                return None

        return index