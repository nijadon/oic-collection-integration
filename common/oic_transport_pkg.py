import boto3
import time
import os
import botocore.exceptions
import logging


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def oic_transport_pkg(formattedBody):
    logger.info("downloading in transport service")
    BUCKET=formattedBody['s3bucket']
    PREFIX=formattedBody['s3prefix']
    #customerId=formattedBody['customerId']
    st_time = int(time.time())
    s3 = boto3.resource('s3')

    fileName = PREFIX[PREFIX.rindex('/')+1:]
    local_file_path= './files/OIC_Transport/'
    local_file_name = local_file_path+fileName
    if os.path.isdir(os.path.dirname(local_file_name)):
        logger.info(local_file_name)
    else:
        os.makedirs(os.path.dirname(local_file_path))
     
    #download the file
    try:
        logger.info('Zip file is downloading in Transport Service')
        s3.Bucket(BUCKET).download_file(PREFIX, local_file_name)

    except botocore.exceptions.ClientError as e:
        logger.error(e.response)
    
    end_time = int(time.time())
    logger.info(f"Total Executin Time >> {(end_time - st_time)}")
    return local_file_name

