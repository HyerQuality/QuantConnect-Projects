##-------------------Class to hold VIX data and calculations---------------------------------------##        
class VixHandler(Object):
    Symbol = None
    PreviousVixClose = Identity("VIX")
    vixPercentMove = 0
    FiveDayVixPercentMoveSTD = 0
    UVXYGap = 0
    vixList = []
    vixPercentMoveList = []
    DeviationVix = []
    DeviationVixChange = []