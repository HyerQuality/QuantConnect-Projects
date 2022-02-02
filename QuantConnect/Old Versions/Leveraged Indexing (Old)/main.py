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
from QuantConnect.Algorithm.Framework.Execution import *
from QuantConnect.Data.UniverseSelection import *
from QuantConnect.Data.Custom.CBOE import *
from Selection.FundamentalUniverseSelectionModel import FundamentalUniverseSelectionModel
from QuantConnect.Algorithm.Framework.Selection import *

##-------------------Alpha Files and Objects--------------------------------------------------##

from Vix import VixHandler
from DynamicWeight import Weights

from LongUVXYAlpha import LongVol
from ShortUVXYAlpha import ShortVol
from SPXLAlpha import SPXL
from SPXSAlpha import SPXS
from TQQQAlpha import TQQQ
from SQQQAlpha import SQQQ
from DebugAlpha import Debug


##-------------------Portfolio Construction Files---------------------------------------------##

from SourceModelPortfolioConstruction import SourceModelPortfolioConstructionModel


##-------------------Execution Files---------------------------------------------##

from ImmediateExecution import ImmediateExecutionModel


##-------------------Risk Management Files----------------------------------------------------##

from RiskManagement import ManageRisk


##-------------------Global variables---------------------------------------------------------##

Zero = int(0)
One = int(1)
OneDay = timedelta(days=1)
resolution = Resolution.Minute

##-------------------Framework Parameters-----------------------------------------------------##

StatPeriod = timedelta(days=365)


class AdvancedIndexing(QCAlgorithm):

##-------------------Initialize variables, lists, asset subscriptions, etc--------------------##

    def Initialize(self):
        # Set Start Date so that backtest has 5+ years of data
        self.SetStartDate(2014, 1, 1)

        # Set Cash
        self.SetCash(1000000)
        
        #Variables
        self.Zero = int(0)

        #Lists
        self.TimeBounds = [time(9,30), time(9,31)]
        
        # VIX Data
        self.VIX = self.AddData(Vix, "VIX", Resolution.Daily).Symbol
        self.AddData(CBOE, "VIX")

        # Selected Securitites
        self.Assets = [
                self.AddEquity("QQQ", Resolution = resolution),
                self.AddEquity("UVXY", Resolution = resolution),
                self.AddEquity("SPXL", Resolution = resolution),
                self.AddEquity("SPXS", Resolution = resolution),
                self.AddEquity("TQQQ", Resolution = resolution),
                self.AddEquity("SQQQ", Resolution = resolution)]
        
        # Booleans
        self.VixReset = True
        self.OnStartUp = True
        
        ManualSymbols = []
        SymbolList = []
        
        for x in self.Assets:
            #ManualSymbols.append(Symbol.Create(x.Symbol, SecurityType.Equity, Market.USA))
            ManualSymbols.append(x.Symbol)
            SymbolList.append(x.Symbol)

##-------------------Construct Alpha Model----------------------------------------------------##

        # Universe Selection
        self.AddUniverseSelection(ManualUniverseSelectionModel(ManualSymbols))
        
        # Alpha Models
        self.AddAlpha(LongVol(StatPeriod))
        self.AddAlpha(ShortVol(StatPeriod))
        self.AddAlpha(SPXL())
        self.AddAlpha(SPXS())
        self.AddAlpha(TQQQ())
        self.AddAlpha(SQQQ())
        
    #    self.AddAlpha(Debug(StatPeriod))
        
        # Portfolio Construction
        self.SetPortfolioConstruction(SourceModelPortfolioConstructionModel(SymbolList))
        
        # Execution
        self.SetExecution(ImmediateExecutionModel())
        
        # Risk Management
        self.SetRiskManagement(ManageRisk())
        
        # Brokerage Model
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
    #    self.SetBrokerageModel(AlphaStreamsBrokerageModel())
    

##-------------------On Data------------------------------------------------------------------##

    def OnData(self, data):
        
##-------------------Manage and plot VIX data-------------------------------------------------##   

        if self.LiveMode: 
            
            if self.OnStartUp:
                self.Log("Live Mode!")
                
                VixHandler.Symbol = self.VIX
                
                VixHandler.vixList = []
                VixHistory = self.VixHistory(6, self.VIX)
    
                VixHandler.vixList = VixHistory.values.flatten().tolist()
                VixHandler.vixPercentMoveList = VixHistory.pct_change().dropna().apply(lambda x: x*float(100)).values.flatten().round(3).tolist()
            
                VixHandler.PreviousVixClose.Update(self.Time, VixHandler.vixList[5])
                VixHandler.vixPercentMove = VixHandler.vixPercentMoveList[4]
                VixHandler.FiveDayVixSpotSTD = np.std(VixHandler.vixList)
                VixHandler.FiveDayVixPercentMoveSTD = np.std(VixHandler.vixPercentMoveList)
                
                self.Log("At {0} the VIX list Populated. The current lists are: Spot - {1} | %Change - {2}".format(self.Time, VixHandler.vixList, VixHandler.vixPercentMoveList))
                
            
            elif data.ContainsKey(self.VIX):
                VixHandler.Symbol = self.VIX
                
                VixHandler.vixList = []
                VixHistory = self.VixHistory(6, self.VIX)
    
                VixHandler.vixList = VixHistory.values.flatten().tolist()
                VixHandler.vixPercentMoveList = VixHistory.pct_change().dropna().apply(lambda x: x*float(100)).values.flatten().round(3).tolist()
            
                VixHandler.PreviousVixClose.Update(self.Time, VixHandler.vixList[5])
                VixHandler.vixPercentMove = VixHandler.vixPercentMoveList[4]
                VixHandler.FiveDayVixSpotSTD = np.std(VixHandler.vixList)
                VixHandler.FiveDayVixPercentMoveSTD = np.std(VixHandler.vixPercentMoveList)
                
                self.Plot('Proportions', 'Max UVXY Short Proportion', Weights.ShortUVXY*100)
                self.Plot('VIX Spot', 'VixPercentMove', VixHandler.vixPercentMove)
                self.Plot('VIX Spot', 'Previous Day Closing VIX', VixHandler.PreviousVixClose.Current.Value)
                self.Plot('VIX Standard Dev', 'FiveDayVixPercentMoveSTD', VixHandler.FiveDayVixPercentMoveSTD)
                
                self.Log("At {0} the VIX list Populated. The current lists are: Spot - {1} | %Change - {2}".format(self.Time, VixHandler.vixList, VixHandler.vixPercentMoveList))
            
            self.AnnualRecalc(self.VIX)
            
        else:
 
            VIX = SymbolCache.GetSymbol("VIX.CBOE")
            
            if self.OnStartUp:
                self.Log("Backtest Mode!")
                
                VixHandler.Symbol = VIX
                    
                if not VixHandler.vixList:

                    VixHistory = self.VixHistory(7, VIX)
                    AdjVixHistory = VixHistory[:-1]
                    
                    VixHandler.vixList = AdjVixHistory.values.flatten().tolist()
                    VixHandler.vixPercentMoveList = AdjVixHistory.pct_change().dropna().apply(lambda x: x*float(100)).values.flatten().round(3).tolist()
                    VixHandler.PreviousVixClose.Update(self.Time, VixHandler.vixList[5])
                    
                else:
                
                    VixHandler.PreviousVixClose.Update(self.Time, self.Securities["VIX.CBOE"].Close)
    
                    for i in range(6):
                        if i == int(5):
                            VixHandler.vixList[i] = VixHandler.PreviousVixClose.Current.Value
                        else:
                            VixHandler.vixList[i] = VixHandler.vixList[i+1]
                            
                    for i in range(5):
                        VixHandler.vixPercentMoveList[i] = (round(float( ((VixHandler.vixList[i+1]/VixHandler.vixList[i])-1)*100 ),2))
                
                VixHandler.vixPercentMove = VixHandler.vixPercentMoveList[4]
                VixHandler.FiveDayVixPercentMoveSTD = np.std(VixHandler.vixPercentMoveList)
         
                self.Log("At {0} the VIX list Populated. The current lists are: Spot - {1} | %Change - {2}".format(self.Time, VixHandler.vixList, VixHandler.vixPercentMoveList))
                

            elif data.ContainsKey("VIX.CBOE"):
                VixHandler.Symbol = VIX
                    
                if not VixHandler.vixList:

                    VixHistory = self.VixHistory(7, VIX)
                    AdjVixHistory = VixHistory[:-1]
                    
                    VixHandler.vixList = AdjVixHistory.values.flatten().tolist()
                    VixHandler.vixPercentMoveList = AdjVixHistory.pct_change().dropna().apply(lambda x: x*float(100)).values.flatten().round(3).tolist()
                    VixHandler.PreviousVixClose.Update(self.Time, VixHandler.vixList[5])
                    
                else:
                
                    VixHandler.PreviousVixClose.Update(self.Time, self.Securities["VIX.CBOE"].Close)
    
                    for i in range(6):
                        if i == int(5):
                            VixHandler.vixList[i] = VixHandler.PreviousVixClose.Current.Value
                        else:
                            VixHandler.vixList[i] = VixHandler.vixList[i+1]
                            
                    for i in range(5):
                        VixHandler.vixPercentMoveList[i] = (round(float( ((VixHandler.vixList[i+1]/VixHandler.vixList[i])-1)*100 ),2))
                
                VixHandler.vixPercentMove = VixHandler.vixPercentMoveList[4]
                VixHandler.FiveDayVixPercentMoveSTD = np.std(VixHandler.vixPercentMoveList)
                
                self.Plot('Proportions', 'Max UVXY Short Proportion', Weights.ShortUVXY*100)
                self.Plot('VIX Spot', 'VixPercentMove', VixHandler.vixPercentMove)
                self.Plot('VIX Spot', 'Previous Day Closing VIX', VixHandler.PreviousVixClose.Current.Value)
                self.Plot('VIX Standard Dev', 'FiveDayVixPercentMoveSTD', VixHandler.FiveDayVixPercentMoveSTD)
         
                self.Log("At {0} the VIX list Populated. The current lists are: Spot - {1} | %Change - {2}".format(self.Time, VixHandler.vixList, VixHandler.vixPercentMoveList))
            
            self.AnnualRecalc(VIX)
        
##-----------------Annual recalculation of various statistics----------------------------------##
    
    def AnnualRecalc(self, symbol):
        
        # Once per year update the VIX statistics with the previuos 4000 days data
        if self.Time.date() == self.GetNextWeekday(date(self.Time.year, 1, 3)) and self.TimeBounds[0] <= self.Time.time() <= self.TimeBounds[1]:
            self.VixReset = True

        if (self.VixReset and self.Time.date() == self.GetNextWeekday(date(self.Time.year, 1, 3)) + OneDay) or self.OnStartUp:
            
            # Base Data
            if symbol == self.VIX:
                vix_history = self.History(symbol, 4000, Resolution.Daily).reset_index(level=0, drop=True)
                vix_percent_change = vix_history.pct_change().dropna()
            else:
                vix_history = self.History(symbol, 4000, Resolution.Daily).reset_index(level=0, drop=True)
                vix_percent_change = vix_history["close"].pct_change()            
            
            # Stat levels
            if symbol == self.VIX:
                AverageVix = np.mean(vix_history.values)
                STDVix = np.std(vix_history.values)
                AverageChange = np.mean(vix_percent_change.values)
                STDChange = np.std(vix_percent_change.values)
                
            else:
                AverageVix = np.mean(vix_history["close"])
                STDVix = np.std(vix_history["close"])
                AverageChange = np.mean(vix_percent_change)
                STDChange = np.std(vix_percent_change)
            
            VixHandler.DeviationVix = []
            VixHandler.DeviationVixChange = []
            
            for i in np.arange(-1, 4, 0.5):
                VixHandler.DeviationVix.append( round(AverageVix + (STDVix * i) ,2) )
                
            for i in range(-3, 5):
                VixHandler.DeviationVixChange.append( round(AverageChange + (STDChange * i) ,2)*100 )
            
            self.VixReset = False
            self.OnStartUp = False

            self.Log("VOL: VIX Spot Deviations: {0} || VIX Change Deviations: {1}".format(VixHandler.DeviationVix, VixHandler.DeviationVixChange))
    
    
##-------------------Method to capture the desired amount of VIX history-------------------------##  

    def VixHistory(self, Days, symbol):
        startingDays = Days
        history = self.History(symbol, Days, Resolution.Daily)
        
        while len(history) < Days:
            startingDays = startingDays + 1
            history = self.History(symbol, startingDays, Resolution.Daily)
        
        if self.LiveMode:    
            return history
        else:
            return history["close"]
        

##-----------------Return the next weekday from specified date------------------------------------##

    def GetNextWeekday(self, RandomDate):
        RandomDate += OneDay
        
        while RandomDate.weekday() > int(4): # Mon-Fri are 0-4
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
            requests.append(SubmitOrderRequest(order.OrderType, order.SecurityType, order.Symbol, newQuantity, order.StopPrice, order.LimitPrice, self.Time, "OnMarginCall"))
        
        return requests 


##-----------------Handles broker specfic issues--------------------------------------------------## 

    def OnBrokerageMessage(self, messageEvent):
        message = messageEvent.Message
        
        if re.search("Brokerage Warning: Contract is not available for trading. Origin: IBPlaceOrder: STK UVXY USD Smart", message):
            self.Log("No shares of UVXY are currently available for trading")
            
        if re.search("Brokerage Warning: Contract is not available for trading. Origin: IBPlaceOrder: STK SPXL USD Smart", message):
            self.Log("No shares of SPXL are currently available for trading")
            
        if re.search("Brokerage Warning: Contract is not available for trading. Origin: IBPlaceOrder: STK SPXS USD Smart", message):
            self.Log("No shares of SPXS are currently available for trading")    
            
        if re.search("IN ORDER TO OBTAIN THE DESIRED POSITION", message):
            Weights.ShortUVXY = Weights.ShortUVXY * float(0.985)
            self.Log("Initial margin requirements require a reduction in positions size. Current short weight: {0}".format(Weights.ShortUVXY))
            
            
##-------------------Class to pull VIX data from the CBOE website---------------------------------##    

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
            index.Value = float(data[4])

        except ValueError:
                # Do nothing
                return None

        return index