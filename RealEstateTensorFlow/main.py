import tensorflow as tf
import pandas as pd
import numpy as np
import joblib
from NumericRegression import EstimatedClosingPrice
from LogisticRegression import LogOdds
from OutOfSample import PredictData

stored_models = {}


def develop_models():
    categorical_model = LogOdds(new_data=False, include_county=False, include_style=False, include_season=False)

    numerical_model = EstimatedClosingPrice(new_data=False, include_county=False,
                                            include_style=False, include_season=False)

    numerical_model.preprocess_raw_data(show_plots=False, outlier_threshold=0.01)
    numerical_model.build_model(show_plots=True)


def construct_models():
    if not stored_models:
        # stored_models['categorical_model'] = LogOdds(new_data=False, include_county=False,
        #                                              include_style=False, include_season=False)

        stored_models['closing_price_model'] = EstimatedClosingPrice(new_data=False, include_county=False,
                                                                     include_style=False, include_season=False)

    for i in range(50):
        # stored_models['categorical_model'].preprocess_raw_data(show_plots=False, outlier_threshold=0.01)
        # stored_models['categorical_model'].build_model(show_plots=False)

        stored_models['closing_price_model'].preprocess_raw_data(show_plots=False, outlier_threshold=0.01)
        stored_models['closing_price_model'].build_model(show_plots=False)

    print("Closing Price Model Lowest Loss: {:5.2f}%".format(100 * stored_models['closing_price_model'].lowest_loss))
    # print("Categorical Model Highest Accuracy: {:5.2f}%".format
          # (100 * stored_models['categorical_model'].highest_accuracy))


def test_models():
    categorical_model = tf.keras.models.load_model('Categorical Model')
    closing_price_model = tf.keras.models.load_model('Closing Price Model')

    npz = np.load('Categorical Test Data.npz')
    test_inputs, test_targets = npz['inputs'].astype(np.float), npz['targets'].astype(np.int)
    loss, acc = categorical_model.evaluate(test_inputs, test_targets, verbose=2)
    print('Categorical Model Accuracy: {:5.2f}%'.format(100 * acc))

    npz = np.load('Numeric Test Data.npz')
    test_inputs, test_targets = npz['inputs'].astype(np.float), npz['targets'].astype(np.float)
    loss = closing_price_model.evaluate(test_inputs, test_targets, verbose=2)
    print('Closing Price Model Loss: {:5.2f}'.format(100 * loss))


def make_predictions(numeric_data: bool):
    predictions = PredictData(filename='Active Listings.csv', include_style=False,
                              include_county=False, include_season=False)

    predictions.preprocess_raw_data(needs_counties=False, numeric_data=numeric_data, show_plots=True, outlier_threshold=0.01)
    npz = np.load('Predictions Data.npz')
    inputs = npz['inputs'].astype(np.float)
    closing_price_model = tf.keras.models.load_model('Closing Price Model')
    estimated_closing_prices = closing_price_model.predict(x=inputs, verbose=1)
    scaler = joblib.load('Numeric Targets Scaler Instance')
    estimated_closing_prices = scaler.inverse_transform(estimated_closing_prices)
    predicted_closing_prices = pd.DataFrame(estimated_closing_prices.round(2),
                                            columns={'Estimated Closing Price'})

    predicted_closing_prices.to_csv(path_or_buf=r'Predictions.csv', index=True)
    print(predicted_closing_prices.apply(lambda x: '%.2f' % x, axis=1))


def main():
    # develop_models()
    # construct_models()
    # test_models()
    make_predictions(numeric_data=True)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
