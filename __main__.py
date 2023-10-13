import requests
import pandas as pd
import base64
import csv
import os
import json
import time

# Constants
CLIENT_ID = 'CLIENT_ID'
CLIENT_SECRET = 'CLIENT_SECRET'
METAMAP_FLOW_ID = 'FLOW_ID'
DEFAULT_BACK_PHOTO = 'DEFAULT_PATH'  # idmeta1/4886023_doc_back.jpg
EXCEL_FILE_PATH = 'INPUT_PATH'


# Authorization
def get_access_token():
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f"Basic {base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()}"
    }
    data = {'grant_type': 'client_credentials'}
    response = requests.post(
        'https://api.getmati.com/oauth', headers=headers, data=data)
    print(response)
    return response.json()['access_token']


def start_verification(access_token, metadata):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {access_token}"
    }
    data = {
        "flowId": METAMAP_FLOW_ID,
        "metadata": metadata
    }
    response = requests.post(
        'https://api.getmati.com/v2/verifications', headers=headers, json=data)
    # Adjusted to retrieve 'identity' from response
    return response.json()['identity']

# Send Inputs


def send_inputs(access_token, identity_id, front, back, selfie):
    headers = {
        'Authorization': f"Bearer {access_token}"
    }

    # Join the current directory with the image path
    # front_path = os.path.join(os.getcwd(), front)
    # back_path = os.path.join(os.getcwd(), back)
    # selfie_path = os.path.join(os.getcwd(), selfie)

    # Define the 'inputs' as per your cURL structure.
    inputs = [
        {
            "inputType": "document-photo",
            "group": 0,
            "data": {
                "type": "national-id",
                "country": "PH",
                "page": "front",
                # Extract the filename from the path
                "filename": os.path.basename(front)
            }
        },
        {
            "inputType": "document-photo",
            "group": 0,
            "data": {
                "type": "national-id",
                "country": "PH",
                "page": "back",
                # Extract the filename from the path
                "filename": os.path.basename(back) if back else os.path.basename(DEFAULT_BACK_PHOTO)
            }
        },
        {
            "inputType": "selfie-photo",
            "data": {
                "type": "selfie-photo",
                # Extract the filename from the path
                "filename": os.path.basename(selfie)
            }
        }
    ]

    inputs_json_str = json.dumps(inputs)

    # print(front_path, back_path, selfie_path)

    # files =[('document': os.path.basename(front), open(front_path, 'rb')),('document': (os.path.basename(back), open(back_path, 'rb'))),('selfie': (os.path.basename(selfie), open(selfie_path, 'rb')))]
    files = [
        ('document', open(front, 'rb')),
        ('document', open(back if back else DEFAULT_BACK_PHOTO, 'rb')),
        ('selfie', open(selfie, 'rb'))
    ]

    print(files)

    url = f'https://api.getmati.com/v2/identities/{identity_id}/send-input'
    response = requests.post(url, headers=headers, data={
                             'inputs': inputs_json_str}, files=files)

    try:
        response_data = response.json()
        # print(response_data)
        # Check if all results are true
        if all(item.get("result", False) for item in response_data):
            return "Success"
        else:
            errors = [item.get("error", {}).get("code", "Unknown error")
                      for item in response_data if "error" in item]
            return "Errors: " + ", ".join(errors)
    except ValueError:
        return f"Failed to parse JSON from response: {response.text}"


def log_to_csv(filename, data):
    """Append data to a CSV file"""
    file_exists = os.path.isfile(filename)
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['Verification ID', 'Status', 'Metadata', 'Time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()  # If the file didn't exist, write the header
        writer.writerow(data)


def main():
    # Read Excel
    df = pd.read_excel(EXCEL_FILE_PATH, engine='openpyxl')

    # Initialize a counter for API calls and the starting time of the batch
    api_calls_count = 0
    start_time_of_batch = time.time()

    for _, row in df.iloc[1353:].iterrows():
        access_token = get_access_token()
        metadata = eval(row['MetaData'])
        identity_id = start_verification(access_token, metadata)
        print(row)
        if not identity_id:
            print("Failed to start verification for", metadata)
            log_to_csv('log.csv', {
                       'Verification ID': '', 'Status': 'Failed to Start Verification', 'Metadata': metadata})
            continue  # Skip the current iteration and move to the next row

        start_time = time.time()
        status = send_inputs(access_token, identity_id, row['Front Photo'], row['Back Photo'] if not pd.isna(
            row['Back Photo']) else None, row['Selfie Photo'])

        # Record the end time
        end_time = time.time()

        log_to_csv('log.csv', {'Verification ID': identity_id,
                   'Status': status, 'Metadata': metadata, 'Time': end_time})

        # Increment API call count
        api_calls_count += 1

        # Calculate the remaining sleep time for the current call
        time_taken_for_current_call = end_time - start_time
        sleep_time = 15 - time_taken_for_current_call
        if sleep_time > 0:
            time.sleep(sleep_time)

        # If 4 API calls have been made, check if the total time since the batch start is less than 60 seconds and sleep accordingly
        if api_calls_count >= 4:
            total_time_for_batch = end_time - start_time_of_batch
            remaining_time_for_batch = 60 - total_time_for_batch
            if remaining_time_for_batch > 0:
                print(f"Sleeping for {remaining_time_for_batch} seconds")
                time.sleep(remaining_time_for_batch)

            # Reset counters and timestamps
            api_calls_count = 0
            start_time_of_batch = time.time()

        if "Error" in status:
            print(f"Failed to send images for {metadata} due to {status}.")
        else:
            print(f"Successfully sent images for {metadata}.")


if __name__ == "__main__":
    main()
