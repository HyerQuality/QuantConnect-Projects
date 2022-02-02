import pandas as pd
import geocoder
import numpy as np
import matplotlib.pyplot as plt
import seaborn
import datetime
import joblib
from requests import Session
from sklearn import preprocessing

seaborn.set()


class PredictData:
    def __init__(self, filename, include_county=True, include_style=True, include_season=True):
        self.filename = str(filename)
        self.raw_data = pd.DataFrame()
        self.clean_data = pd.DataFrame()
        self.balanced_data = pd.DataFrame()
        self.include_county = include_county
        self.include_style = include_style
        self.include_season = include_season
        self.scaler_instance = None

    def preprocess_raw_data(self, needs_counties=True, numeric_data=True, show_plots=True, outlier_threshold=0.05):
        if needs_counties:
            self.get_counties()
        else:
            self.raw_data = pd.read_csv(self.filename, index_col=0)

        if numeric_data:
            self.scaler_instance = joblib.load('Numeric Targets Scaler Instance')
            self.preprocess_raw_numeric_data(show_plots=show_plots, outlier_threshold=outlier_threshold)
        else:
            self.scaler_instance = joblib.load('Categorical Targets Scaler Instance')
            self.preprocess_raw_categorical_data(show_plots=show_plots, outlier_threshold=outlier_threshold)

    def get_counties(self):
        raw_data = pd.read_csv(self.filename, index_col=0)
        raw_data['Full Street Address'] = raw_data['Full Street Address'] + ', MD'

        # Remove unneeded fields and get counties from street address. WARNING: This cell block is very slow
        data_removed_fields = raw_data.drop(['Listing ID', 'Structure Type', 'DOM', 'CDOM'], axis=1)
        streets = data_removed_fields.iloc[:, 1].tolist()

        # Collect the counties for each address. WARNING: This cell block is very slow
        counties = []
        for address in streets:
            g = geocoder.osm(address, session=Session())
            counties.append(g.county)

        data_removed_fields['Full Street Address'] = counties
        data_with_counties = data_removed_fields.rename(columns={'Full Street Address': 'County'})

        # Save a copy of the data with counties to save time in the future
        data_with_counties.to_csv('Out of Sample Data With Counties.csv')
        self.raw_data = data_with_counties

    def preprocess_raw_categorical_data(self, show_plots=False, outlier_threshold=0.05):
        relevant_data = self.raw_data

        # Replace NaN values with 0
        relevant_data = relevant_data.fillna(0)

        # Drop unneeded location fields
        relevant_data = relevant_data.drop(['Subdivision/Neighborhood', 'Status'], axis=1)

        # Collect individual styles
        primary_styles = []
        individual_styles = []
        styles = relevant_data['Style'].tolist()

        for item in styles:
            primary_styles.append(item.split(',')[0])

        for item in primary_styles:
            individual_styles.append(item.split('/')[0])

        data_simple_styles = relevant_data
        data_simple_styles['Style'] = individual_styles

        # Redefine the year build as the age of the home
        year_built = data_simple_styles['Year Built'].tolist()
        current_year = datetime.datetime.today().year
        home_age = []

        for ele in year_built:
            if ele == 0:
                home_age.append(0)
            else:
                home_age.append(current_year - ele)

        data_simple_styles = data_simple_styles.rename(columns={'Year Built': 'Home Age'})
        data_simple_styles['Home Age'] = home_age

        # Remap basement to 0-1
        data_simple_styles['Basement YN'] = data_simple_styles['Basement YN'].map({'Yes': 1, 'No': 0})

        # Trim and rearrange columns
        new_columns = ['Home Age', 'County', 'Style', 'Lot Size SqFt', 'Beds', 'Bathrooms Full', 'Bathrooms Half',
                       'Levels/Stories', 'Fireplaces Total', 'Basement YN', 'Close Date',
                       'List Price', 'Close Price', 'Concessions Amt '
                       ]

        data_simple_styles = data_simple_styles[new_columns]
        data_simple_styles = data_simple_styles.rename(columns={'Concessions Amt ': 'Concessions Amt'})

        # Convert prices to floats
        data_simple_styles['List Price'] = data_simple_styles['List Price'].astype(str)
        data_simple_styles['Close Price'] = data_simple_styles['Close Price'].astype(str)
        data_simple_styles['Concessions Amt'] = data_simple_styles['Concessions Amt'].astype(str)

        clean_list = [x.strip() for x in data_simple_styles['List Price'].tolist()]
        clean_close = [x.strip() for x in data_simple_styles['Close Price'].tolist()]
        clean_concessions = [x.strip() for x in data_simple_styles['Concessions Amt'].tolist()]

        clean_list = [x.replace('$', "") for x in clean_list]
        clean_close = [x.replace('$', "") for x in clean_close]
        clean_concessions = [x.replace('$', "") for x in clean_concessions]

        clean_list = [x.replace(',', "") for x in clean_list]
        clean_close = [x.replace(',', "") for x in clean_close]
        clean_concessions = [x.replace(',', "") for x in clean_concessions]

        clean_list = [str(0) if x == "" else x for x in clean_list]
        clean_close = [str(0) if x == "" else x for x in clean_close]
        clean_concessions = [str(0) if x == "" else x for x in clean_concessions]

        data_simple_styles['List Price'] = clean_list
        data_simple_styles['Close Price'] = clean_close
        data_simple_styles['Concessions Amt'] = clean_concessions

        data_simple_styles['List Price'] = data_simple_styles['List Price'].astype(float)
        data_simple_styles['Close Price'] = data_simple_styles['Close Price'].astype(float)
        data_simple_styles['Concessions Amt'] = data_simple_styles['Concessions Amt'].astype(float)

        # Remove outliers with exceptionally high or low difference between close price and list price
        data_less_outliers = data_simple_styles
        data_less_outliers['Change From List Price'] = (
                data_less_outliers['Close Price']
                + data_less_outliers['Concessions Amt']
                - data_less_outliers['List Price']
        )

        # Observe the boxplot
        if show_plots:
            plt.boxplot(data_less_outliers['Change From List Price'])
            plt.show()
            plt.plot(data_less_outliers['Change From List Price'])
            plt.show()
            plt.hist(sorted(data_less_outliers['Change From List Price']), bins=20)
            plt.show()

        # Combine the close price and concessions amount then subtract list price.
        # Map 0:"Reduced Price" and 1:"Increased Price"
        # Changes this model into a classification model rather than a regression model
        data_with_targets = data_less_outliers.rename(columns={'Change From List Price': 'Targets'})

        modified_targets = []
        for target in data_with_targets['Targets'].tolist():
            if target > 0:
                modified_targets.append(1)
            else:
                modified_targets.append(0)

        data_with_targets['Targets'] = modified_targets

        # Drop the list prices, close prices, and concession amounts
        data_with_targets = data_with_targets.drop(['List Price', 'Close Price', 'Concessions Amt'], axis=1)

        # Convert the sale date to the sale season
        close_dates = data_with_targets['Close Date'].tolist()
        close_seasons = []

        for ele in close_dates:
            month = datetime.datetime.strptime(ele, "%m/%d/%Y").month

            if month == 12 or month == 1 or month == 2:
                close_seasons.append("Winter")

            elif month == 3 or month == 4 or month == 5:
                close_seasons.append("Spring")

            elif month == 6 or month == 7 or month == 8:
                close_seasons.append("Summer")

            else:
                close_seasons.append("Fall")

        data_with_targets['Close Date'] = close_seasons
        data_with_targets = data_with_targets.rename(columns={'Close Date': 'Close Season'})

        if show_plots:
            plt.hist(close_seasons, bins=4)
            plt.show()

        # Scale numeric fields
        data_with_targets = data_with_targets.dropna()
        scaler = self.scaler_instance

        data_home_quality = data_with_targets

        numeric_columns = ['Home Age', 'Lot Size SqFt', 'Beds', 'Bathrooms Full', 'Bathrooms Half',
                           'Levels/Stories', 'Fireplaces Total']

        for col in numeric_columns:
            temp_array = np.array(data_home_quality[col]).reshape(-1, 1)
            scaled_array = scaler.fit_transform(temp_array)
            data_home_quality[col] = scaled_array

        # Create dummy variables for categorical fields
        categorical_columns = ['County', 'Style', 'Close Season']
        data_with_dummies = pd.get_dummies(data_home_quality, columns=categorical_columns)

        # Remove targets from list of columns then append it to the end
        feature_columns = []
        for col in data_with_dummies.columns:
            if col == 'Targets':
                continue
            else:
                feature_columns.append(col)

        feature_columns.append('Targets')

        # Rearrange columns to place targets at the end
        data_with_dummies = data_with_dummies[feature_columns]

        # Feature selection: choose which columns to drop and which to feed into the model
        if not self.include_style:
            data_with_dummies = data_with_dummies[data_with_dummies.columns.drop(
                list(data_with_dummies.filter(regex='Style')))]

        if not self.include_season:
            data_with_dummies = data_with_dummies[data_with_dummies.columns.drop(
                list(data_with_dummies.filter(regex='Season')))]

        if not self.include_county:
            data_with_dummies = data_with_dummies[data_with_dummies.columns.drop(
                list(data_with_dummies.filter(regex='County')))]

        self.clean_data = data_with_dummies
        print('Data samples: ' + str(self.clean_data.shape))
        print(self.clean_data.head().to_string())

        self.prepare_tensor_data()

    def preprocess_raw_numeric_data(self, show_plots=False, outlier_threshold=0.5):
        relevant_data = self.raw_data

        # Replace NaN values with 0
        relevant_data = relevant_data.fillna(0)

        # Drop unneeded location fields
        relevant_data = relevant_data.drop(['Subdivision/Neighborhood', 'Status'], axis=1)

        # Collect individual styles
        primary_styles = []
        individual_styles = []
        styles = relevant_data['Style'].tolist()

        for item in styles:
            primary_styles.append(item.split(',')[0])

        for item in primary_styles:
            individual_styles.append(item.split('/')[0])

        data_simple_styles = relevant_data
        data_simple_styles['Style'] = individual_styles

        # Redefine the year build as the age of the home
        year_built = data_simple_styles['Year Built'].tolist()
        current_year = datetime.datetime.today().year
        home_age = []

        for ele in year_built:
            if ele == 0:
                home_age.append(0)
            else:
                home_age.append(current_year - ele)

        data_simple_styles = data_simple_styles.rename(columns={'Year Built': 'Home Age'})
        data_simple_styles['Home Age'] = home_age

        # Remap basement to 0-1
        data_simple_styles['Basement YN'] = data_simple_styles['Basement YN'].map({'Yes': 1, 'No': 0})

        # Trim and rearrange columns
        new_columns = ['Home Age', 'County', 'Style', 'Lot Size SqFt', 'Beds', 'Bathrooms Full', 'Bathrooms Half',
                       'Levels/Stories', 'Fireplaces Total', 'Basement YN', 'Close Date',
                       'List Price', 'Close Price', 'Concessions Amt '
                       ]

        data_simple_styles = data_simple_styles[new_columns]
        data_simple_styles = data_simple_styles.rename(columns={'Concessions Amt ': 'Concessions Amt'})

        # Convert prices to floats
        data_simple_styles['List Price'] = data_simple_styles['List Price'].astype(str)
        data_simple_styles['Close Price'] = data_simple_styles['Close Price'].astype(str)
        data_simple_styles['Concessions Amt'] = data_simple_styles['Concessions Amt'].astype(str)

        clean_list = [x.strip() for x in data_simple_styles['List Price'].tolist()]
        clean_close = [x.strip() for x in data_simple_styles['Close Price'].tolist()]
        clean_concessions = [x.strip() for x in data_simple_styles['Concessions Amt'].tolist()]

        clean_list = [x.replace('$', "") for x in clean_list]
        clean_close = [x.replace('$', "") for x in clean_close]
        clean_concessions = [x.replace('$', "") for x in clean_concessions]

        clean_list = [x.replace(',', "") for x in clean_list]
        clean_close = [x.replace(',', "") for x in clean_close]
        clean_concessions = [x.replace(',', "") for x in clean_concessions]

        clean_list = [str(0) if x == "" else x for x in clean_list]
        clean_close = [str(0) if x == "" else x for x in clean_close]
        clean_concessions = [str(0) if x == "" else x for x in clean_concessions]

        data_simple_styles['List Price'] = clean_list
        data_simple_styles['Close Price'] = clean_close
        data_simple_styles['Concessions Amt'] = clean_concessions

        data_simple_styles['List Price'] = data_simple_styles['List Price'].astype(float)
        data_simple_styles['Close Price'] = data_simple_styles['Close Price'].astype(float)
        data_simple_styles['Concessions Amt'] = data_simple_styles['Concessions Amt'].astype(float)

        # Remove outliers with exceptionally high or low difference between close price and list price
        data_less_outliers = data_simple_styles

        # Observe the boxplot
        if show_plots:
            plt.boxplot(data_less_outliers['List Price'])
            plt.show()
            plt.plot(data_less_outliers['List Price'])
            plt.show()
            plt.hist(sorted(data_less_outliers['List Price']), bins=10)
            plt.show()

        # Drop the list prices, close prices, and concession amounts
        data_less_outliers = data_less_outliers.drop(['List Price', 'Close Price', 'Concessions Amt'], axis=1)

        # Convert the sale date to the sale season
        close_dates = data_less_outliers['Close Date'].tolist()
        close_seasons = []

        for ele in close_dates:
            month = datetime.datetime.strptime(ele, "%m/%d/%Y").month

            if month == 12 or month == 1 or month == 2:
                close_seasons.append("Winter")

            elif month == 3 or month == 4 or month == 5:
                close_seasons.append("Spring")

            elif month == 6 or month == 7 or month == 8:
                close_seasons.append("Summer")

            else:
                close_seasons.append("Fall")

        data_less_outliers['Close Date'] = close_seasons
        data_less_outliers = data_less_outliers.rename(columns={'Close Date': 'Close Season'})

        if show_plots:
            plt.hist(close_seasons, bins=4)
            plt.show()

        # Scale numeric fields
        data_less_outliers = data_less_outliers.dropna()
        scaler = self.scaler_instance

        data_home_quality = data_less_outliers

        numeric_columns = ['Home Age', 'Lot Size SqFt', 'Beds', 'Bathrooms Full', 'Bathrooms Half',
                           'Levels/Stories', 'Fireplaces Total']

        for col in numeric_columns:
            temp_array = np.array(data_home_quality[col]).reshape(-1, 1)
            scaled_array = scaler.fit_transform(temp_array)
            data_home_quality[col] = scaled_array

        # Create dummy variables for categorical fields
        categorical_columns = ['County', 'Style', 'Close Season']
        data_with_dummies = pd.get_dummies(data_home_quality, columns=categorical_columns)

        # Feature selection: choose which columns to drop and which to feed into the model
        if not self.include_style:
            data_with_dummies = data_with_dummies[data_with_dummies.columns.drop(
                list(data_with_dummies.filter(regex='Style')))]

        if not self.include_season:
            data_with_dummies = data_with_dummies[data_with_dummies.columns.drop(
                list(data_with_dummies.filter(regex='Season')))]

        if not self.include_county:
            data_with_dummies = data_with_dummies[data_with_dummies.columns.drop(
                list(data_with_dummies.filter(regex='County')))]

        self.clean_data = data_with_dummies.dropna()
        print('Data samples: ' + str(self.clean_data.shape))
        print(self.clean_data.head().to_string(), self.clean_data.shape[0])

        self.prepare_tensor_data()

    def prepare_tensor_data(self):
        predictions_x = self.clean_data

        # Save the datasets as npz files so they are compatible with tensorflow
        np.savez('Predictions Data', inputs=predictions_x)
