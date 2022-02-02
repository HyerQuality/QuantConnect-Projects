import numpy as np


class Portfolio:
    """
    Portfolio class will store a portfolio's metrics and performance
        Parameters:

            cagr: The compounded annual growth rate of the portfolio
            std: The standard deviation of annual returns
            starting_capital: The initial investment into the portfolio
            annual_withdrawals: Amount of annual outflows from the portfolio
            capacity: The maximum amount of capital the strategy can or is allowed to operate at
    """

    def __init__(self, cagr, std, starting_capital, annual_withdrawals, capacity=np.inf):
        self.CGR = float(cagr)
        self.StandardDeviation = float(std)
        self.InitialInvestment = float(starting_capital)
        self.Withdrawals = float(annual_withdrawals)
        self.Capacity = float(capacity)
        self.Deductions = float(6800)
        self.PortfolioValue = float(starting_capital)
        self.TaxLiability = float(0)
        self.CarryOverLosses = float(0)
        self.RemovedFunds = float(0)

    def performance(self, years, compound_frequency):
        """
        Calculate the portfolio performance over the given time frame
            Parameters:

                years: How many years to extrapolate estimated performance
                compound_frequency: Relates to portfolio turnover. Annual, Semi-Annual, Monthly, Weekly, or Daily
        """
        frequency_map = {'Annual': 1,
                         'Semi-Annual': 2,
                         'Monthly': 12,
                         'Weekly': 52,
                         'Daily': 252
                         }

        frequency = float(frequency_map[compound_frequency])
        epochs = frequency * years
        gains = 0
        self.CGR, self.StandardDeviation = self.derive_growth_rate(years=7.63,
                                                                   cagr=self.CGR,
                                                                   standard_deviation=self.StandardDeviation,
                                                                   frequency=frequency)

        for i in np.arange(1, epochs + 1, 1):
            expected_return = np.asscalar(np.random.normal(self.CGR, self.StandardDeviation, 1))
            if i == 1:
                self.PortfolioValue = round(self.InitialInvestment * (1 + (expected_return / frequency)), 2)
                gains += self.InitialInvestment * (expected_return / frequency)

            else:
                gains += self.PortfolioValue * (expected_return / frequency)
                self.PortfolioValue = round(self.PortfolioValue * (1 + (expected_return / frequency)), 2)
                self.PortfolioValue = self.PortfolioValue - self.portfolio_limitations()

            if i % frequency == 0:
                self.PortfolioValue = round(self.PortfolioValue - self.taxes_and_withdrawals(capital_gains=gains), 2)
                self.PortfolioValue = self.PortfolioValue - self.portfolio_limitations()
                gains = 0

    def taxes_and_withdrawals(self, capital_gains):
        """
        Calculate year end taxes on short term gains and apply any other withdrawals at year end
            Parameters:

                capital_gains: Gains to apply taxes to. Losses will be passed forward as tax deductions
        """
        tax_brackets = {0: 0,
                        9950: 0.1,
                        40525: 0.12,
                        86375: 0.22,
                        164925: 0.24,
                        209425: 0.32,
                        523600: 0.35,
                        np.inf: 0.37}

        tax_levels = list(tax_brackets.keys())
        taxable_income = []
        tax_rate = []

        if capital_gains >= 0:
            for index, value in enumerate(tax_levels):
                if index == 0:
                    continue

                elif capital_gains >= value:
                    taxable_income.append((value - tax_levels[index - 1]))
                    tax_rate.append(tax_brackets[value])

                else:
                    taxable_income.append(capital_gains - tax_levels[index - 1])
                    tax_rate.append(tax_brackets[value])
                    break

            tax_burden = np.asscalar(np.dot(taxable_income, tax_rate))
            if self.CarryOverLosses > 0:
                tax_burden -= min(self.Deductions, self.CarryOverLosses)
                self.CarryOverLosses -= min(self.Deductions, self.CarryOverLosses)

            self.TaxLiability += round(tax_burden, 2)

        else:
            tax_burden = max(-self.Deductions, capital_gains)

            if abs(capital_gains) > self.Deductions:
                self.CarryOverLosses += abs(capital_gains) - self.Deductions

            self.TaxLiability += round(tax_burden, 2)

        self.RemovedFunds += self.Withdrawals

        return tax_burden + self.Withdrawals

    def portfolio_limitations(self):
        """Consider portfolio limitations like capacity or maximum investment caps. Returns a withdrawal amount."""
        if self.PortfolioValue >= self.Capacity:
            portfolio_reduction = self.Capacity / 2
            self.RemovedFunds += round(portfolio_reduction, 2)
            return round(portfolio_reduction, 2)
        else:
            return 0

    def monte_carlo(self, years, compound_frequency):
        """Run many iterations of the performance and return a statistical analysis of the results
            Parameters:

                years: How many years to extrapolate estimated performance
                compound_frequency: Relates to portfolio turnover. Annual, Semi-Annual, Monthly, Weekly, or Daily
        """
        self.performance(years, compound_frequency)

    @staticmethod
    def derive_growth_rate(years, cagr, standard_deviation, frequency):
        """Static method to derive the compounded growth rate for the given compounding frequency
            Parameters:

                years: How many years the portfolio was back tested or live. Used to calculate the CAGR
                cagr: The annual compounded growth rate of the portfolio
                standard_deviation: The standard deviation of the portfolio returns
                frequency: Relates to portfolio turnover. Passed as a numeric value representing compounding frequency
        """
        net_return = (1 + cagr) ** years
        cgr = frequency * (net_return ** (1 / (years * frequency)) - 1)
        std = standard_deviation * (cgr / cagr)
        return round(cgr, 6), round(std, 6)
