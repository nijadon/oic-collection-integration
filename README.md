# OIC Collection Integration

OIC Collection Microservice consistes two services - Inventory Packaging Service and Transport Packaging Service, which upload the data file from given s3 bucket to OIC tool for IBES reporting for NextGen Cloud Agent 2.0 customers.

## Services

### Inventory Packaging Service

Inventory Packaging Service checks the given SQS queue and checks the CSPC ID to see if this customer eligible for L3 delievaravle, if yes, then calls the method to downloads the files from S3 bucket as per SQS message, archive them in a single file and upload it to another S3 bucket and notify the Transport Packaging Service SQS queue.

### Transport Packaging Service

Transport Packaging Service checks its SQS queue and download the single file as per the message from SQS and upload it to OIC with CSPS ID and upload token.

