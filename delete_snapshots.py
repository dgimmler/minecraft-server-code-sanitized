import boto3
import os
import json


MAX_AGE = int(os.environ.get('MAX_AGE', 14))
VOLUME_ID = os.environ.get('VOLUME_ID', '<volume id>')


def get_snapshots(client):
    """ Return a list of snapshots for the given VOLUME_ID older than the
        MAX_AGE
    """
    response = client.describe_snapshots(
        Filters=[{
            'Name': 'volume-id',
            'Values': [VOLUME_ID]
        }]
    )
    return sorted(
        response.get("Snapshots", []),
        key=lambda x: x['StartTime'].timestamp(),
        reverse=True)[MAX_AGE:]


def delete_snapshot(client, snapshot):
    """ Try to delete a snapshot. Just ignore any errors.
    """
    try:
        response = client.delete_snapshot(
            SnapshotId=snapshot['SnapshotId'])
        print(response)
        return 1
    except Exception as err:
        print(err)
        return 0


def main():
    client = boto3.client("ec2")
    snapshots = get_snapshots(client)

    # delete snapshots and track how many deleted
    deleted = 0
    total = 0
    for snapshot in snapshots:
        total += 1
        deleted += delete_snapshot(client, snapshot)
    print(
        f"Deleted {deleted} out of {total} snapshots older than {MAX_AGE} days")


def lambda_handler(event, context):
    """ Primary lambda entry function. Return valide response so it can be used
        by API if needed.
    """
    main()
    headers = {"Access-Control-Allow-Origin": os.environ.get("CloudfrontOrigin"),
               "Access-Control-Allow-Headers:": "*"}
    return {"statusCode": 200, "body": "success", "headers": json.dumps(headers)}
