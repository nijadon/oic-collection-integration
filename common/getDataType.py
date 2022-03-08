import boto3
import os
import botocore
import json

def download_the_file(logger,BUCKET,PREFIX):
    
    s3 = boto3.resource('s3')

    fileName = PREFIX[PREFIX.rindex('/')+1:]
    local_file_path= './files/manifestFiles/'
    local_file_name = local_file_path+fileName
    if os.path.isdir(os.path.dirname(local_file_name)):
        logger.info("Manifest Dir available")
    else:
        os.makedirs(os.path.dirname(local_file_path))
    
    #download the file
    try:
        logger.info('Manifest file is downloading')
        s3.Bucket(BUCKET).download_file(PREFIX, local_file_name)
        return local_file_name

    except botocore.exceptions.ClientError as e:
        logger.error(e.response)
        return None

def get_data_type(logger,fileName):

    try:
        f = open(fileName)

        # returns JSON object as
        # a dictionary
        data = json.load(f)
        checkSum=data['metadata']['InvType']
        logger.info(f"Inventory type is {checkSum}")
        f.close()
        os.remove(fileName)
        logger.info(f"Metadata file is deleted")
        return checkSum
    except Exception as e:
        f.close()
        os.remove(fileName)
        logger.error("Inventory type is not found")
        return None

def getDataType(logger,bucketname,uri):
    fileName=download_the_file(logger,bucketname,uri)
    #print(f"File Name {fileName}")
    return get_data_type(logger,fileName)

#getDataType('cx-cloud-agent-dnac-uploads','CXCA/CXCA/devices/date=20211207/customerId=07071952/1cd94b56-5b15-466e-a3fd-0aa5b4bbcf63_1638835616556_cxdl-ingestion-manifest.json')