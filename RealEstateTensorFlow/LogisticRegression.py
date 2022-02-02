import pandas as pd
import geocoder
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
import seaborn
import datetime
import joblib
from requests import Session
from sklearn import preprocessing
from tensorflow.keras.optimizers import SGD

seaborn.set()


class LogOdds:
    def __init__(self, new_data=False, include_county=True, include_style=True, include_season=True):
        self.is_new_data = new_data
        self.raw_data = pd.DataFrame()
        self.clean_data = pd.DataFrame()
        self.balanced_data = pd.DataFrame()
        self.include_county = include_county
        self.include_style = include_style
        self.include_season = include_season
        self.highest_accuracy = float(0)
        self.scaler_instance = None
        self.model = None

    def get_counties(self):
        if self.is_new_data:
            raw_data = pd.read_csv('Default Export.csv')
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
            data_with_counties.to_csv('Raw Data With Counties.csv')
            return data_with_counties

        else:
            data_with_counties = pd.read_csv('Raw Data With Counties.csv')
            return data_with_counties

    def preprocess_raw_data(self, show_plots=False, outlier_threshold=0.5):
        self.raw_data = self.get_counties()

        # Separate out closed homes.  These will make up the training data.
        separation_criteria = ['Closed']
        data_closed = self.raw_data[self.raw_data['Status'].isin(separation_criteria)].reset_index(drop=True)
        data_not_closed = self.raw_data[~self.raw_data['Status'].isin(separation_criteria)].reset_index(drop=True)
        relevant_data = data_closed

        # Replace NaN values with 0
        relevant_data = relevant_data.fillna(0)

        # Drop unneeded location fields
        relevant_data = relevant_data.drop(['Subdivision/Neighborhood', 'Status'], axis=1)
        data_not_closed = data_not_closed.drop(['Subdivision/Neighborhood', 'Status'], axis=1)
        data_not_closed.to_csv('Active Listings.csv')

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

        top_percent = data_less_outliers['Change From List Price'].quantile(q=1 - outlier_threshold,
                                                                            interpolation='nearest'
                                                                            )

        data_less_outliers = data_less_outliers[data_less_outliers['Change From List Price'] < top_percent]
        bot_percent = data_less_outliers['Change From List Price'].quantile(q=outlier_threshold,
                                                                            interpolation='nearest'
                                                                            )

        data_less_outliers = data_less_outliers[data_less_outliers['Change From List Price'] > bot_percent]

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
        scaler = preprocessing.MinMaxScaler()
        self.scaler_instance = scaler

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

        self.balance_clean_data(show_plots=show_plots)
        self.prepare_tensor_data(train_portion=0.85, validation_portion=0.10)

    def balance_clean_data(self, show_plots=False):
        zero_targets = self.clean_data[self.clean_data['Targets'] == 0]
        one_targets = self.clean_data[self.clean_data['Targets'] == 1].iloc[:zero_targets.shape[0]]
        self.balanced_data = pd.concat([zero_targets, one_targets], axis=0)
        self.balanced_data = self.balanced_data.dropna()

        if show_plots:
            plt.hist(self.balanced_data['Targets'])
            plt.show()

    def prepare_tensor_data(self, train_portion=0.80, validation_portion=0.15):
        # Shuffle the balanced dataset
        self.balanced_data = self.balanced_data.iloc[np.random.permutation(len(self.balanced_data))]

        # Split the data in training, validation, and test chunks
        data_length = len(self.balanced_data)
        training_proportion = train_portion
        validation_proportion = validation_portion

        training_rows = int(round(data_length * training_proportion, 0))
        validation_rows = int(round(data_length * (training_proportion + validation_proportion), 0))
        test_rows = int(data_length)

        train_x, train_y = self.balanced_data.iloc[:training_rows, :-1], self.balanced_data.iloc[:training_rows, -1:]

        val_x, val_y = self.balanced_data.iloc[training_rows:validation_rows, :-1], self.balanced_data.iloc[
                                                                                    training_rows:validation_rows, -1:]

        test_x, test_y = self.balanced_data.iloc[validation_rows:test_rows, :-1], self.balanced_data.iloc[
                                                                                  validation_rows:test_rows, -1:]

        # Save the datasets as npz files so they are compatible with tensorflow
        np.savez('Categorical Training Data', inputs=train_x, targets=train_y)
        np.savez('Categorical Validation Data', inputs=val_x, targets=val_y)
        np.savez('Categorical Test Data', inputs=test_x, targets=test_y)

    def build_model(self, show_plots=False):
        # Load the data to be used in the ML model
        npz = np.load('Categorical Training Data.npz')
        train_inputs, train_targets = npz['inputs'].astype(np.float), npz['targets'].astype(np.int)

        npz = np.load('Categorical Validation Data.npz')
        validation_inputs, validation_targets = npz['inputs'].astype(np.float), npz['targets'].astype(np.int)

        # Global variables for the ML model
        batch_size = int(train_inputs.shape[0] / 250)
        epochs = 500
        hidden_layers = 25
        patience = 10

        # Set the input and output sizes
        input_size = train_inputs.shape[1]
        output_size = 1

        # Define how the model will look like
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(hidden_layers, input_shape=(input_size,), activation='relu'),  # Hidden layer
            tf.keras.layers.Dense(hidden_layers / 4, activation='relu'),  # Hidden layer
            # tf.keras.layers.Dense(3, activation='relu'),  # Hidden layer
            tf.keras.layers.Dense(output_size, activation='sigmoid')  # Output layer
        ])

        # Choose the optimizer and the loss function
        opt = tf.keras.optimizers.Adam(learning_rate=0.0002)
        # opt = SGD(lr=0.002, momentum=0.24)
        model.compile(optimizer=opt, loss='binary_crossentropy', metrics=['accuracy'])

        # Training
        # Set an early stopping mechanism
        early_stopping = tf.keras.callbacks.EarlyStopping(patience=patience)

        # Fit the model
        history = model.fit(train_inputs,  # train inputs
                            train_targets,  # train targets
                            batch_size=batch_size,  # batch size
                            epochs=epochs,  # epochs that we will train for (assuming early stopping doesn't kick in)

                            # callbacks are functions called by a task when a task is completed
                            # task here is to check if val_loss is increasing
                            callbacks=[early_stopping],  # early stopping
                            validation_data=(validation_inputs, validation_targets),  # validation data
                            verbose=2  # making sure we get enough information about the training process
                            )

        if show_plots:
            fig, ax = plt.subplots()
            ax.plot(history.history['accuracy'])
            ax.plot(history.history['val_accuracy'])
            plt.show()

        if history.history['val_accuracy'][-1] > self.highest_accuracy:
            self.highest_accuracy = history.history['val_accuracy'][-1]
            model.save('Categorical Model')
            self.model = tf.keras.models.load_model('Categorical Model')
            joblib.dump(self.scaler_instance, 'Categorical Targets Scaler Instance')
            print(round(self.highest_accuracy, 4))

    def test_model(self):
        npz = np.load('Categorical Test Data.npz')
        test_inputs, test_targets = npz['inputs'].astype(np.float), npz['targets'].astype(np.int)
        loss, acc = self.model.evaluate(test_inputs, test_targets, verbose=2)
        print('Model Accuracy: {:5.2f}%'.format(100 * acc))
