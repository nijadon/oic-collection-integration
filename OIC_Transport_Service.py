import boto3
import time
import logging
import os
import json

from common import oic_transport_pkg
from common import collectorless_client_upload
from common import sqs_services
from common import getCSPC
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info('Logger for '+__name__)

queue_url_2 = os.environ.get('Transport_Service_Queue')

def transport_service():
    #Transport Service
    logger.info("Transport Service is started")
    # Create SQS client
    sqs = boto3.client('sqs')
    logger.info("Checking SQS in the queue")
    while True:
        # Receive message from SQS queue
        response = sqs.receive_message(
            QueueUrl=queue_url_2,
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
            logger.info('Found a message in Transport SQS')
            message = response['Messages'][0]
            receipt_handle = message['ReceiptHandle']
            body=message['Body']
            formattedBody=json.loads(body)
            remoteNodeId=formattedBody['remotenodeid']
            datatype=formattedBody['datatype'].split('/')[1]
            cspcId=getCSPC.get_CSPC_Id(logger,remoteNodeId,datatype)
            if(cspcId is not None):
                local_file_name=oic_transport_pkg.oic_transport_pkg(formattedBody)#download the tar.gz file into local location
                logger.info("local File is downloaded in transport service")
                #call fuctions for 3-6 steps in transport service list of OIC details document
                try:
                    cco_Credentials = collectorless_client_upload.CCOCredentials(os.environ.get('CCO_USERNAME'),os.environ.get('CCO_PASSWORD'))
                    api_M_Config = collectorless_client_upload.ApiMConfig.load_env()
                    cx_Drive_Config =collectorless_client_upload.CxDriveConfig(cspcId,'https',None)
                    uploder=collectorless_client_upload.Uploader(cco_Credentials,cx_Drive_Config,api_M_Config)
                    #access_token=uploder._get_cxd_access_token()
                    #logger.info("Access token id: "+access_token)
                    uploder.upload(local_file_name, "Inventory")

                    sqs_services.delete_SQS_message(sqs,queue_url_2,receipt_handle)
                    os.remove(local_file_name)
                    logger.info('deleted the local file and Transport queue message')
                except Exception as err:
                    logger.error(f'Recieved an exception while trying to upload the file. Retrying in 60 sec\n{err}')
            else:
                sqs_services.delete_SQS_message(sqs,queue_url_2,receipt_handle)
                logger.info('CSPC Id was not found for Remote Node Id: '+remoteNodeId+' and data Type: '+datatype+'\nDeleted the SQS message')        
            time.sleep(2)
        else:
            time.sleep(60)

if __name__ == "__main__":
    logger.info('Starting Transport Service')
    transport_service()