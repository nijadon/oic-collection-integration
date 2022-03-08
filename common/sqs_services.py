import boto3
import json

def send_notification(queue_url,singleZipFileName):
    sqs = boto3.client('sqs')

    # Send message to SQS queue
    response = sqs.send_message(
        QueueUrl=queue_url,
        DelaySeconds=10,
        #MessageAttributes={
            #Message Attribute
        #},
        MessageBody=(
            json.dumps(singleZipFileName)
        )
    )

    print(response['MessageId'])

def delete_SQS_message(sqs,queue_url,receipt_handle):
    #deleting SQS message
    sqs.delete_message(
    QueueUrl=queue_url,
    ReceiptHandle=receipt_handle
    )