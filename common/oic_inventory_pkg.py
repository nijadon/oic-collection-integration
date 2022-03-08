import boto3
import os
import botocore.exceptions
import tarfile
import shutil
import gzip
import time
import threading
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

#BUCKET = cparser.get("S3_Bucket", "DNAC_BUCKET")
#PREFIX = 'CXCA/devices/date=20211006/customerId=07071952/controllerId=2328bf68-f614-4cff-85a9-f110b23e9b3f/'
DEST_BUCKET = os.environ.get('DEST_BUCKET')

#BUCKET = 'cx-cloud-agent-inventory-uploads-usw2-cx-nprd-test'
#PREFIX = 'CXCA/devices/date=20211018/customerId=vishnutest206/controllerId=4d0d176e-302a-11ec-8d3d-0242ac130003/'

#DEST_BUCKET = 'oic-data-source-usw2-cx-nprd-test'

def gunzip(file_path,output_path):
    with gzip.open(file_path,"rb") as f_in, open(output_path,"wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

def deleting_inventory_files(local_file_path,singleLocalZipFile):
    shutil.rmtree(local_file_path)
    os.remove(singleLocalZipFile)

def createMetadeta(fileName, customerId, inventoryType):
    file = open(fileName,'a+')
    logger.info("Creating Metadata.json file")
    if(inventoryType=="DNAC"):
        inventoryType="dnac_inventory"
    elif(inventoryType=="NO_CONTROLLER"):
        inventoryType="ddc_inventory"
    inp='{\n\t\t"collectorless_connector_name": "cxcloud_cxagent",\n\t\t"collectorless_connector_version": "0.0.1",\n\t\t"nms_version": "2.0.0",\n\t\t"collector_metadata": {\n\t\t\t"customer_id": "'+customerId+'",\n\t\t\t"data_type": "'+inventoryType+'"\n\t}\n}'
    file.write(inp)
    file.close()
    logger.info("Metadata.json file is created")

def oic_inv_pkg(BUCKET,PREFIX,customerId,inventoryType):
    logger.info("in OIC Inventory Service for Bucket: "+BUCKET+"\nPREFIX: "+PREFIX)
    st_time = int(time.time())
    s3 = boto3.resource('s3')
    s3_client = boto3.client('s3')

    keys = []

    kwargs = {'Bucket': BUCKET, 'Prefix' : PREFIX}
    logger.info('Downloading json.gz files')
    while True:
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp['Contents']:
            keys.append(obj['Key'])
            
            KEY = str(obj['Key'])

            fileName = KEY.split("/")
            local_file_path= './files/OIC_Inventory/'+str(st_time)+'/'
            local_file_name = local_file_path+fileName[len(fileName)-1]
            local_file_path=local_file_path.strip()
            if os.path.isdir(os.path.dirname(local_file_name)):
                logger.info(local_file_name)
            else:
                os.makedirs(os.path.dirname(local_file_path))
        
            #download the file
            try:
                s3.Bucket(BUCKET).download_file(KEY, local_file_name)

                if local_file_name.endswith('.gz'):
                    gunzip(local_file_name, local_file_name.replace(".gz",""))
                    if os.path.exists(local_file_name):
                        os.remove(local_file_name)

            except botocore.exceptions.ClientError as e:
                logger.error(e.response)

        try:
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        except KeyError:
            break
    
    #Creating Metadata File
    createMetadeta(local_file_path+'metadata.json',customerId,inventoryType)

    # create .tar.gz file
    logger.info('Zipping json.gz files')
    localZipFile='./files/OIC_InvData_raw_'+str(st_time)+'.tar.gz'
    with tarfile.open(localZipFile, "w:gz") as tar:
        tar.add(local_file_path, arcname=os.path.basename(local_file_path))    

    #upload to S3 bucket
    logger.info('uploading zip file to another S3 bucket')
    singleZipFileName='oic_inventory_'+ str(int(time.time())) +'.tar.gz'
    DEST_PREFIX='OIC/inventory/'
    s3.meta.client.upload_file(localZipFile, DEST_BUCKET, DEST_PREFIX+singleZipFileName)

    t1 = threading.Thread(target=deleting_inventory_files, args=(local_file_path,localZipFile))
    t1.start()

    end_time = int(time.time())
    
    logger.info(f'No of Devices {len(keys)}')
    logger.info(f"Total Executin Time >> {(end_time - st_time)}")
    response={'s3bucket':DEST_BUCKET, 's3prefix':DEST_PREFIX+singleZipFileName}
    return response

#oic_inv_pkg()

##s3_json_tar_transform()
