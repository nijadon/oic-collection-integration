import boto3
import time
import logging
#import configparser
import os
import json

from common import oic_inventory_pkg
from common import sqs_services
from common import getCSPC
from dotenv import load_dotenv

from common import getDataType

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


queue_url_1= os.environ.get('Inventory_Service_Queue')
queue_url_2 = os.environ.get('Transport_Service_Queue')

def inventory_packaging_service():
    #Inventory Packaging Service
    logger.info('Inventory Packaging Service Started')
    # Create SQS client
    sqs = boto3.client('sqs')
    logger.info('Checking Inventory SQS queue')
    while True:
        # Receive message from SQS queue
        response = sqs.receive_message(
            QueueUrl=queue_url_1,
            AttributeNames=[
                'SentTimestamp'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )
        if(len(response)>1): #Checking if any message recieved or not
            logger.info('Found a message in Inventory SQS')
            message = response['Messages'][0]
            receipt_handle = message['ReceiptHandle']
            body=message['Body']
            formattedBody=json.loads(body)
            record=formattedBody['Records'][0]
            uri=record['s3']['object']['key']
            BUCKET=record['s3']['bucket']['name']
            uri=uri.replace("%3D","=")
            logger.info("URI: "+uri)
            PREFIX=uri[0:uri.rindex('/')+1]
            customerId=uri[uri.rindex("customerId="):].split('/')[0].split('=')[1]
            remoteNodeId=uri[uri.rindex("/")+1:].split('_')[0]
            datatype=getDataType.getDataType(logger,BUCKET,uri)
            if(datatype is not None):
                cspcId=getCSPC.get_CSPC_Id(logger,remoteNodeId,datatype)
            else:
                cspcId=None
            #cspcId="CSP0009056400"
            if(cspcId is not None):
                #if(True): #for every messagem, checks the CSPC ID to see if this customer eligible for L3 delievaravle
                logger.info("CSPC Id is available")
                logger.info("CSPC Id is eligible for inventory upload")
                transportSQSBody=oic_inventory_pkg.oic_inv_pkg(BUCKET,PREFIX,customerId,datatype)
                logger.info('Sending notification to Transport service SQS for file: '+transportSQSBody['s3prefix'])
                transportSQSBody['remotenodeid']=remoteNodeId
                transportSQSBody['datatype']="inventory/"+datatype
                sqs_services.send_notification(queue_url_2,transportSQSBody)
            sqs_services.delete_SQS_message(sqs,queue_url_1,receipt_handle)
            logger.info('Deleted the SQS message')
            time.sleep(2)
        else:
            time.sleep(60)

if __name__ == "__main__":
    logger.info('Starting Inventory Packaging Service')
    inventory_packaging_service()