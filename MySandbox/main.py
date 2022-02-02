import pandas as pd
from datetime import date


def sandbox():
    # long_list = [32, 8, 4, 45, 31, 1, 5, 7]
    # target = 12
    # short_dict = {x: x for x in long_list if x < target}
    # results = []
    #
    # for x in short_dict.keys():
    #     if (target - x in short_dict) and ((target - x) != x) and ((target - x, x) not in results):
    #         results.append((x, target - x))
    #         print(x, target - x)
    #
    # if results:
    #     print(results)
    # else:
    #     print('No combinations')

    # string = 'aaaabbbbcdddde'
    # counter_dict = {}
    # for s in string:
    #     if s not in counter_dict:
    #         counter_dict[s] = 1
    #
    #     elif counter_dict[s] > 1:
    #         continue
    #
    #     else:
    #         counter_dict[s] += 1
    #
    # for letter in counter_dict:
    #     if counter_dict[letter] == 1:
    #         print(letter)
    #         break

    user = pd.DataFrame(columns={'Patient ID', 'Patient DOB'})
    user['Patient ID'] = [1, 2, 3, 4]
    user['Patient DOB'] = ['1-1-1970', '1-1-1975', '1-1-1980', '1-1-1990']
    user['Patient DOB'] = pd.to_datetime(user['Patient DOB'])

    invoice = pd.DataFrame({'Patient_ID': [1, 2, 3, 4], 'Invoice Amount': [10, 30, 40, 50]})
    payment = pd.DataFrame({'Patient_id': [1, 2, 3, 4], 'Payment': [10, 30, 0, 50]})

    # Calculate Patient Age
    user['Patient Age'] = (pd.to_datetime('now') - user['Patient DOB']).astype('<m8[Y]')

    # Calculate difference between invoice and payment
    payment_tracking = invoice.set_index('Patient_ID').join(payment.set_index('Patient_id'))
    payment_tracking['Receivable'] = payment_tracking['Invoice Amount'] - payment_tracking['Payment']

    # Determine payment rate
    paid_in_full = payment_tracking[payment_tracking['Receivable'] == 0]
    print(paid_in_full.shape[0] / payment_tracking.shape[0])


if __name__ == '__main__':
    sandbox()
