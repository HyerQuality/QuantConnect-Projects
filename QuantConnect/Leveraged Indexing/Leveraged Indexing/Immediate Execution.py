from clr import AddReference

AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Algorithm.Framework")

from System import *
from QuantConnect import *
from QuantConnect.Orders import *
from QuantConnect.Algorithm import *
from Global import Global


class ImmediateExecutionModel(ExecutionModel):
    '''
    Solution 1: Store each order ticket in a dictionary and adjust the quantity of invalid orders until fulfilled
    '''

    def __init__(self):
        self.targetsCollection = PortfolioTargetCollection()
        self.tickets = {}
        self.today = None

    def Execute(self, algorithm, targets):

        # For performance we check count value, OrderByMarginImpact and ClearFulfilled are expensive to call
        self.targetsCollection.AddRange(targets)
        if self.targetsCollection.Count > 0:  # and Global.MarketIsOpen:
            for target in self.targetsCollection.OrderByMarginImpact(algorithm):
                symbol = target.Symbol

                # If the last ticket for this symbol was Invalid
                # We will redefine the target and update it in the collection
                ticket = self.tickets.pop(symbol, None)
                if ticket and ticket.Status == OrderStatus.Invalid:
                    target = PortfolioTarget(symbol, target.Quantity * 0.97)
                    Global.ShortUVXY = Global.ShortUVXY * 0.97
                    self.targetsCollection.Add(target)
                    algorithm.Log(
                        f'Initial margin requirements require a reduction in position size. Reducing current order for {symbol} by 3%.  Previous Short%: {Global.ShortUVXY / 0.97} - Current Short%: {Global.ShortUVXY}')

                # Calculate remaining quantity to be ordered. If the order is being dynamically adjusted do to broker margin constraints, remove the target as soon as the majority of the order fills.
                quantity = OrderSizing.GetUnorderedQuantity(algorithm, target)
                if quantity > 0 or algorithm.Shortable(target.Symbol, quantity):
                    self.tickets[symbol] = algorithm.MarketOrder(symbol, quantity)
                    if algorithm.LiveMode:
                        algorithm.Log(f'Order submitted for {target.Symbol} at {algorithm.Time.time()}')

                if not algorithm.Shortable(target.Symbol, quantity) and algorithm.Time.day != self.today:
                    algorithm.Log(f'Not enough shares of {symbol} available to short. Order not placed.')
                    self.today = algorithm.Time.day

            self.targetsCollection.ClearFulfilled(algorithm)

