##-------------------Class to store passable variables---------------------------------------------##
class Global(Object):
    MarginMultiplier = float(1.33)
    ShortUVXY = float(0.78)
    OpenClose = {}
    Tickets = {}
    TradeTriggers = {}
    PortfolioHigh = 0
    PortfolioDrawdown = 0
    PortfolioGains = 0
    InitialDrawdown = 0
    MarketIsOpen = False
    NoSharesAvailable = False


##-------------------Class to hold VIX data and calculations---------------------------------------##
class VixHandler(Object):
    Symbol = None
    PreviousVixClose = Identity("VIX")
    vixPercentMove = float(0)
    FiveDayVixPercentMoveSTD = float(0)
    SixDayVixAverage = float(0)
    PreviousMonthAverage = float(0)
    vixList = []
    vixPercentMoveList = []
    DeviationVix = []
    DeviationVixChange = []


##-------------------Resets all class attributes to their default values----------------------------##
class DefaultValues:
    def __init__(self):
        pass

    def ResetGlobal():
        Global.MarginMultiplier = float(1.33)
        Global.ShortUVXY = float(0.78)
        Global.OpenClose = {}
        Global.Tickets = {}
        Global.TradeTriggers = {}
        Global.PortfolioHigh = 0
        Global.PortfolioDrawdown = 0
        Global.MarketIsOpen = False
        Global.NoSharesAvailable = False

    def ResetVixHandler():
        VixHandler.Symbol = None
        VixHandler.PreviousVixClose = Identity("VIX")
        VixHandler.vixPercentMove = float(0)
        VixHandler.FiveDayVixPercentMoveSTD = float(0)
        VixHandler.SixDayVixAverage = float(0)
        VixHandler.PreviousMonthAverage = float(0)
        VixHandler.vixList = []
        VixHandler.vixPercentMoveList = []
        VixHandler.DeviationVix = []
        VixHandler.DeviationVixChange = []