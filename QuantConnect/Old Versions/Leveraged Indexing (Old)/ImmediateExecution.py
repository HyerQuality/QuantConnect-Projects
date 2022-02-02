from clr import AddReference
AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Algorithm.Framework")

from System import *
from QuantConnect import *
from QuantConnect.Orders import *
from QuantConnect.Algorithm import *
from QuantConnect.Algorithm.Framework import *
from QuantConnect.Algorithm.Framework.Execution import *
from QuantConnect.Algorithm.Framework.Portfolio import *

class ImmediateExecutionModel(ExecutionModel):

    def __init__(self):
        self.targetsCollection = PortfolioTargetCollection()

    def Execute(self, algorithm, targets):

        # For performance we check count value, OrderByMarginImpact and ClearFulfilled are expensive to call
        self.targetsCollection.AddRange(targets)
        if self.targetsCollection.Count > 0:
            for target in self.targetsCollection.OrderByMarginImpact(algorithm):
                
                # Calculate remaining quantity to be ordered
                quantity = OrderSizing.GetUnorderedQuantity(algorithm, target)
                if quantity != 0:
                    algorithm.MarketOrder(target.Symbol, quantity)

            self.targetsCollection.ClearFulfilled(algorithm)