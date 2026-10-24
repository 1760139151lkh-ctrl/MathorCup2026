

# HeadObject
<a name="API_HeadObject"></a>

The `HEAD` operation retrieves metadata from an object without returning the object itself. This operation is useful if you're interested only in an object's metadata.

**Note**  
A `HEAD` request has the same options as a `GET` operation on an object. The response is identical to the `GET` response except that there is no response body. Because of this, if the `HEAD` request generates an error, it returns a generic code, such as `400 Bad Request`, `403 Forbidden`, `404 Not Found`, `405 Method Not Allowed`, `412 Precondition Failed`, or `304 Not Modified`. It's not possible to retrieve the exact exception of these error codes.

Request headers are limited to 8 KB in size. For more information, see [Common Request Headers](https://docs.aws.amazon.com/AmazonS3/latest/API/RESTCommonRequestHeaders.html).

Permissions  
  
+  **General purpose bucket permissions** - To use `HEAD`, you must have the `s3:GetObject` permission. You need the relevant read object (or version) permission for this operation. For more information, see [Actions, resources, and condition keys for Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/dev/list_amazons3.html) in the *Amazon S3 User Guide*. For more information about the permissions to S3 API operations by S3 resource types, see [Required permissions for Amazon S3 API operations](/AmazonS3/latest/userguide/using-with-s3-policy-actions.html) in the *Amazon S3 User Guide*.

  If the object you request doesn't exist, the error that Amazon S3 returns depends on whether you also have the `s3:ListBucket` permission.
  + If you have the `s3:ListBucket` permission on the bucket, Amazon S3 returns an HTTP status code `404 Not Found` error.
  + If you don’t have the `s3:ListBucket` permission, Amazon S3 returns an HTTP status code `403 Forbidden` error.
+  **Directory bucket permissions** - To grant access to this API operation on a directory bucket, we recommend that you use the [`CreateSession`](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateSession.html) API operation for session-based authorization. Specifically, you grant the `s3express:CreateSession` permission to the directory bucket in a bucket policy or an IAM identity-based policy. Then, you make the `CreateSession` API call on the bucket to obtain a session token. With the session token in your request header, you can make API requests to this operation. After the session token expires, you make another `CreateSession` API call to generate a new session token for use. AWS CLI or SDKs create session and refresh the session token automatically to avoid service interruptions when a session expires. For more information about authorization, see [`CreateSession`](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateSession.html).

  If you enable `x-amz-checksum-mode` in the request and the object is encrypted with AWS Key Management Service (AWS KMS), you must also have the `kms:GenerateDataKey` and `kms:Decrypt` permissions in IAM identity-based policies and AWS KMS key policies for the AWS KMS key to retrieve the checksum of the object.

Encryption  
Encryption request headers, like `x-amz-server-side-encryption`, should not be sent for `HEAD` requests if your object uses server-side encryption with AWS Key Management Service (AWS KMS) keys (SSE-KMS), dual-layer server-side encryption with AWS KMS keys (DSSE-KMS), or server-side encryption with Amazon S3 managed encryption keys (SSE-S3). The `x-amz-server-side-encryption` header is used when you `PUT` an object to S3 and want to specify the encryption method. If you include this header in a `HEAD` request for an object that uses these types of keys, you’ll get an HTTP `400 Bad Request` error. It's because the encryption method can't be changed when you retrieve the object.
If you encrypt an object by using server-side encryption with customer-provided encryption keys (SSE-C) when you store the object in Amazon S3, then when you retrieve the metadata from the object, you must use the following headers to provide the encryption key for the server to be able to retrieve the object's metadata. The headers are:   
+  `x-amz-server-side-encryption-customer-algorithm` 
+  `x-amz-server-side-encryption-customer-key` 
+  `x-amz-server-side-encryption-customer-key-MD5` 
For more information about SSE-C, see [Server-Side Encryption (Using Customer-Provided Encryption Keys)](https://docs.aws.amazon.com/AmazonS3/latest/dev/ServerSideEncryptionCustomerKeys.html) in the *Amazon S3 User Guide*.  
 **Directory bucket ** - For directory buckets, there are only two supported options for server-side encryption: SSE-S3 and SSE-KMS. SSE-C isn't supported. For more information, see [Protecting data with server-side encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-express-serv-side-encryption.html) in the *Amazon S3 User Guide*. 

Versioning  
+ If the current version of the object is a delete marker, Amazon S3 behaves as if the object was deleted and includes `x-amz-delete-marker: true` in the response.
+ If the specified version is a delete marker, the response returns a `405 Method Not Allowed` error and the `Last-Modified: timestamp` response header.
+  **Directory buckets** - Delete marker is not supported for directory buckets.
+  **Directory buckets** - S3 Versioning isn't enabled and supported for directory buckets. For this API operation, only the `null` value of the version ID is supported by directory buckets. You can only specify `null` to the `versionId` query parameter in the request.

HTTP Host header syntax  
 **Directory buckets ** - The HTTP Host header syntax is ` Bucket-name.s3express-zone-id.region-code.amazonaws.com`.  
For directory buckets, you must make requests for this API operation to the Zonal endpoint. These endpoints support virtual-hosted-style requests in the format `https://amzn-s3-demo-bucket.s3express-zone-id.region-code.amazonaws.com/key-name `. Path-style requests are not supported. For more information about endpoints in Availability Zones, see [Regional and Zonal endpoints for directory buckets in Availability Zones](https://docs.aws.amazon.com/AmazonS3/latest/userguide/endpoint-directory-buckets-AZ.html) in the *Amazon S3 User Guide*. For more information about endpoints in Local Zones, see [Concepts for directory buckets in Local Zones](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-lzs-for-directory-buckets.html) in the *Amazon S3 User Guide*.

The following actions are related to `HeadObject`:
+  [GetObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html) 
+  [GetObjectAttributes](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObjectAttributes.html) 

**Important**  
You must URL encode any signed header values that contain spaces. For example, if your header value is `my file.txt`, containing two spaces after `my`, you must URL encode this value to `my%20%20file.txt`.

## Request Syntax
<a name="API_HeadObject_RequestSyntax"></a>

```
HEAD /{{Key+}}?partNumber={{PartNumber}}&response-cache-control={{ResponseCacheControl}}&response-content-disposition={{ResponseContentDisposition}}&response-content-encoding={{ResponseContentEncoding}}&response-content-language={{ResponseContentLanguage}}&response-content-type={{ResponseContentType}}&response-expires={{ResponseExpires}}&versionId={{VersionId}} HTTP/1.1
Host: {{Bucket}}.s3.amazonaws.com
If-Match: {{IfMatch}}
If-Modified-Since: {{IfModifiedSince}}
If-None-Match: {{IfNoneMatch}}
If-Unmodified-Since: {{IfUnmodifiedSince}}
Range: {{Range}}
x-amz-server-side-encryption-customer-algorithm: {{SSECustomerAlgorithm}}
x-amz-server-side-encryption-customer-key: {{SSECustomerKey}}
x-amz-server-side-encryption-customer-key-MD5: {{SSECustomerKeyMD5}}
x-amz-request-payer: {{RequestPayer}}
x-amz-expected-bucket-owner: {{ExpectedBucketOwner}}
x-amz-checksum-mode: {{ChecksumMode}}
```

## URI Request Parameters
<a name="API_HeadObject_RequestParameters"></a>

The request uses the following URI parameters.

 ** [Bucket](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-Bucket"></a>
The name of the bucket that contains the object.  
 **Directory buckets** - When you use this operation with a directory bucket, you must use virtual-hosted-style requests in the format ` Bucket-name.s3express-zone-id.region-code.amazonaws.com`. Path-style requests are not supported. Directory bucket names must be unique in the chosen Zone (Availability Zone or Local Zone). Bucket names must follow the format ` bucket-base-name--zone-id--x-s3` (for example, ` amzn-s3-demo-bucket--usw2-az1--x-s3`). For information about bucket naming restrictions, see [Directory bucket naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/directory-bucket-naming-rules.html) in the *Amazon S3 User Guide*.  
 **Access points** - When you use this action with an access point for general purpose buckets, you must provide the alias of the access point in place of the bucket name or specify the access point ARN. When you use this action with an access point for directory buckets, you must provide the access point name in place of the bucket name. When using the access point ARN, you must direct requests to the access point hostname. The access point hostname takes the form *AccessPointName*-*AccountId*.s3-accesspoint.*Region*.amazonaws.com. When using this action with an access point through the AWS SDKs, you provide the access point ARN in place of the bucket name. For more information about access point ARNs, see [Using access points](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-access-points.html) in the *Amazon S3 User Guide*.  
Object Lambda access points are not supported by directory buckets.
 **S3 on Outposts** - When you use this action with S3 on Outposts, you must direct requests to the S3 on Outposts hostname. The S3 on Outposts hostname takes the form ` AccessPointName-AccountId.outpostID.s3-outposts.Region.amazonaws.com`. When you use this action with S3 on Outposts, the destination bucket must be the Outposts access point ARN or the access point alias. For more information about S3 on Outposts, see [What is S3 on Outposts?](https://docs.aws.amazon.com/AmazonS3/latest/userguide/S3onOutposts.html) in the *Amazon S3 User Guide*.  
Required: Yes

 ** [If-Match](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-IfMatch"></a>
Return the object only if its entity tag (ETag) is the same as the one specified; otherwise, return a 412 (precondition failed) error.  
If both of the `If-Match` and `If-Unmodified-Since` headers are present in the request as follows:  
+  `If-Match` condition evaluates to `true`, and;
+  `If-Unmodified-Since` condition evaluates to `false`;
Then Amazon S3 returns `200 OK` and the data requested.  
For more information about conditional requests, see [RFC 7232](https://tools.ietf.org/html/rfc7232).

 ** [If-Modified-Since](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-IfModifiedSince"></a>
Return the object only if it has been modified since the specified time; otherwise, return a 304 (not modified) error.  
If both of the `If-None-Match` and `If-Modified-Since` headers are present in the request as follows:  
+  `If-None-Match` condition evaluates to `false`, and;
+  `If-Modified-Since` condition evaluates to `true`;
Then Amazon S3 returns the `304 Not Modified` response code.  
For more information about conditional requests, see [RFC 7232](https://tools.ietf.org/html/rfc7232).

 ** [If-None-Match](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-IfNoneMatch"></a>
Return the object only if its entity tag (ETag) is different from the one specified; otherwise, return a 304 (not modified) error.  
If both of the `If-None-Match` and `If-Modified-Since` headers are present in the request as follows:  
+  `If-None-Match` condition evaluates to `false`, and;
+  `If-Modified-Since` condition evaluates to `true`;
Then Amazon S3 returns the `304 Not Modified` response code.  
For more information about conditional requests, see [RFC 7232](https://tools.ietf.org/html/rfc7232).

 ** [If-Unmodified-Since](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-IfUnmodifiedSince"></a>
Return the object only if it has not been modified since the specified time; otherwise, return a 412 (precondition failed) error.  
If both of the `If-Match` and `If-Unmodified-Since` headers are present in the request as follows:  
+  `If-Match` condition evaluates to `true`, and;
+  `If-Unmodified-Since` condition evaluates to `false`;
Then Amazon S3 returns `200 OK` and the data requested.  
For more information about conditional requests, see [RFC 7232](https://tools.ietf.org/html/rfc7232).

 ** [Key](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-uri-Key"></a>
The object key.  
Length Constraints: Minimum length of 1.  
Required: Yes

 ** [partNumber](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-PartNumber"></a>
Part number of the object being read. This is a positive integer between 1 and 10,000. Effectively performs a 'ranged' HEAD request for the part specified. Useful querying about the size of the part and the number of parts in this object.

 ** [Range](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-Range"></a>
HeadObject returns only the metadata for an object. If the Range is satisfiable, only the `ContentLength` is affected in the response. If the Range is not satisfiable, S3 returns a `416 - Requested Range Not Satisfiable` error.

 ** [response-cache-control](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-ResponseCacheControl"></a>
Sets the `Cache-Control` header of the response.

 ** [response-content-disposition](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-ResponseContentDisposition"></a>
Sets the `Content-Disposition` header of the response.

 ** [response-content-encoding](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-ResponseContentEncoding"></a>
Sets the `Content-Encoding` header of the response.

 ** [response-content-language](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-ResponseContentLanguage"></a>
Sets the `Content-Language` header of the response.

 ** [response-content-type](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-ResponseContentType"></a>
Sets the `Content-Type` header of the response.

 ** [response-expires](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-ResponseExpires"></a>
Sets the `Expires` header of the response.

 ** [versionId](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-uri-querystring-VersionId"></a>
Version ID used to reference a specific version of the object.  
For directory buckets in this API operation, only the `null` value of the version ID is supported.

 ** [x-amz-checksum-mode](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-ChecksumMode"></a>
To retrieve the checksum, this parameter must be enabled.  
 **General purpose buckets** - If you enable checksum mode and the object is uploaded with a [checksum](https://docs.aws.amazon.com/AmazonS3/latest/API/API_Checksum.html) and encrypted with an AWS Key Management Service (AWS KMS) key, you must have permission to use the `kms:Decrypt` action to retrieve the checksum.  
 **Directory buckets** - If you enable `ChecksumMode` and the object is encrypted with AWS Key Management Service (AWS KMS), you must also have the `kms:GenerateDataKey` and `kms:Decrypt` permissions in IAM identity-based policies and AWS KMS key policies for the AWS KMS key to retrieve the checksum of the object.  
Valid Values: `ENABLED` 

 ** [x-amz-expected-bucket-owner](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-ExpectedBucketOwner"></a>
The account ID of the expected bucket owner. If the account ID that you provide does not match the actual owner of the bucket, the request fails with the HTTP status code `403 Forbidden` (access denied).

 ** [x-amz-request-payer](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-RequestPayer"></a>
Confirms that the requester knows that they will be charged for the request. Bucket owners need not specify this parameter in their requests. If either the source or destination S3 bucket has Requester Pays enabled, the requester will pay for the corresponding charges. For information about downloading objects from Requester Pays buckets, see [Downloading Objects in Requester Pays Buckets](https://docs.aws.amazon.com/AmazonS3/latest/dev/ObjectsinRequesterPaysBuckets.html) in the *Amazon S3 User Guide*.  
This functionality is not supported for directory buckets.
Valid Values: `requester` 

 ** [x-amz-server-side-encryption-customer-algorithm](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-SSECustomerAlgorithm"></a>
Specifies the algorithm to use when encrypting the object (for example, AES256).  
This functionality is not supported for directory buckets.

 ** [x-amz-server-side-encryption-customer-key](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-SSECustomerKey"></a>
Specifies the customer-provided encryption key for Amazon S3 to use in encrypting data. This value is used to store the object and then it is discarded; Amazon S3 does not store the encryption key. The key must be appropriate for use with the algorithm specified in the `x-amz-server-side-encryption-customer-algorithm` header.  
This functionality is not supported for directory buckets.

 ** [x-amz-server-side-encryption-customer-key-MD5](#API_HeadObject_RequestSyntax) **   <a name="AmazonS3-HeadObject-request-header-SSECustomerKeyMD5"></a>
Specifies the 128-bit MD5 digest of the encryption key according to RFC 1321. Amazon S3 uses this header for a message integrity check to ensure that the encryption key was transmitted without error.  
This functionality is not supported for directory buckets.

## Request Body
<a name="API_HeadObject_RequestBody"></a>

The request does not have a request body.

## Response Syntax
<a name="API_HeadObject_ResponseSyntax"></a>

```
HTTP/1.1 200
x-amz-delete-marker: {{DeleteMarker}}
accept-ranges: {{AcceptRanges}}
x-amz-expiration: {{Expiration}}
x-amz-restore: {{Restore}}
x-amz-archive-status: {{ArchiveStatus}}
Last-Modified: {{LastModified}}
Content-Length: {{ContentLength}}
x-amz-checksum-crc32: {{ChecksumCRC32}}
x-amz-checksum-crc32c: {{ChecksumCRC32C}}
x-amz-checksum-crc64nvme: {{ChecksumCRC64NVME}}
x-amz-checksum-sha1: {{ChecksumSHA1}}
x-amz-checksum-sha256: {{ChecksumSHA256}}
x-amz-checksum-sha512: {{ChecksumSHA512}}
x-amz-checksum-md5: {{ChecksumMD5}}
x-amz-checksum-xxhash64: {{ChecksumXXHASH64}}
x-amz-checksum-xxhash3: {{ChecksumXXHASH3}}
x-amz-checksum-xxhash128: {{ChecksumXXHASH128}}
x-amz-checksum-type: {{ChecksumType}}
ETag: {{ETag}}
x-amz-missing-meta: {{MissingMeta}}
x-amz-version-id: {{VersionId}}
Cache-Control: {{CacheControl}}
Content-Disposition: {{ContentDisposition}}
Content-Encoding: {{ContentEncoding}}
Content-Language: {{ContentLanguage}}
Content-Type: {{ContentType}}
Content-Range: {{ContentRange}}
Expires: {{Expires}}
x-amz-website-redirect-location: {{WebsiteRedirectLocation}}
x-amz-server-side-encryption: {{ServerSideEncryption}}
x-amz-server-side-encryption-customer-algorithm: {{SSECustomerAlgorithm}}
x-amz-server-side-encryption-customer-key-MD5: {{SSECustomerKeyMD5}}
x-amz-server-side-encryption-aws-kms-key-id: {{SSEKMSKeyId}}
x-amz-server-side-encryption-bucket-key-enabled: {{BucketKeyEnabled}}
x-amz-storage-class: {{StorageClass}}
x-amz-request-charged: {{RequestCharged}}
x-amz-replication-status: {{ReplicationStatus}}
x-amz-mp-parts-count: {{PartsCount}}
x-amz-tagging-count: {{TagCount}}
x-amz-object-lock-mode: {{ObjectLockMode}}
x-amz-object-lock-retain-until-date: {{ObjectLockRetainUntilDate}}
x-amz-object-lock-legal-hold: {{ObjectLockLegalHoldStatus}}
x-amz-object-lock-event-hold: {{ObjectLockEventHold}}
x-amz-object-lock-event-hold-duration-days: {{ObjectLockEventHoldDurationDays}}
x-amz-object-lock-event-hold-duration-years: {{ObjectLockEventHoldDurationYears}}
```

## Response Elements
<a name="API_HeadObject_ResponseElements"></a>

If the action is successful, the service sends back an HTTP 200 response.

The response returns the following HTTP headers.

 ** [accept-ranges](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-AcceptRanges"></a>
Indicates that a range of bytes was specified.

 ** [Cache-Control](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-CacheControl"></a>
Specifies caching behavior along the request/reply chain.

 ** [Content-Disposition](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ContentDisposition"></a>
Specifies presentational information for the object.

 ** [Content-Encoding](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ContentEncoding"></a>
Indicates what content encodings have been applied to the object and thus what decoding mechanisms must be applied to obtain the media-type referenced by the Content-Type header field.

 ** [Content-Language](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ContentLanguage"></a>
The language the content is in.

 ** [Content-Length](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ContentLength"></a>
Size of the body in bytes.

 ** [Content-Range](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ContentRange"></a>
The portion of the object returned in the response for a `GET` request.

 ** [Content-Type](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ContentType"></a>
A standard MIME type describing the format of the object data.

 ** [ETag](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ETag"></a>
An entity tag (ETag) is an opaque identifier assigned by a web server to a specific version of a resource found at a URL.

 ** [Expires](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-Expires"></a>
The date and time at which the object is no longer cacheable.

 ** [Last-Modified](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-LastModified"></a>
Date and time when the object was last modified.

 ** [x-amz-archive-status](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ArchiveStatus"></a>
The archive state of the head object.  
This functionality is not supported for directory buckets.
Valid Values: `ARCHIVE_ACCESS | DEEP_ARCHIVE_ACCESS` 

 ** [x-amz-checksum-crc32](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumCRC32"></a>
The Base64 encoded, 32-bit `CRC32 checksum` of the object. This checksum is only present if the checksum was uploaded with the object. When you use an API operation on an object that was uploaded using multipart uploads, this value may not be a direct checksum value of the full object. Instead, it's a calculation based on the checksum values of each individual part. For more information about how checksums are calculated with multipart uploads, see [ Checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html#large-object-checksums) in the *Amazon S3 User Guide*.

 ** [x-amz-checksum-crc32c](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumCRC32C"></a>
The Base64 encoded, 32-bit `CRC32C` checksum of the object. This checksum is only present if the checksum was uploaded with the object. When you use an API operation on an object that was uploaded using multipart uploads, this value may not be a direct checksum value of the full object. Instead, it's a calculation based on the checksum values of each individual part. For more information about how checksums are calculated with multipart uploads, see [ Checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html#large-object-checksums) in the *Amazon S3 User Guide*.

 ** [x-amz-checksum-crc64nvme](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumCRC64NVME"></a>
The Base64 encoded, 64-bit `CRC64NVME` checksum of the object. For more information, see [Checking object integrity in the Amazon S3 User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html).

 ** [x-amz-checksum-md5](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumMD5"></a>
The Base64 encoded, 128-bit `MD5` digest of the object. For more information, see [Checking object integrity in the Amazon S3 User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html).

 ** [x-amz-checksum-sha1](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumSHA1"></a>
The Base64 encoded, 160-bit `SHA1` digest of the object. This checksum is only present if the checksum was uploaded with the object. When you use the API operation on an object that was uploaded using multipart uploads, this value may not be a direct checksum value of the full object. Instead, it's a calculation based on the checksum values of each individual part. For more information about how checksums are calculated with multipart uploads, see [ Checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html#large-object-checksums) in the *Amazon S3 User Guide*.

 ** [x-amz-checksum-sha256](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumSHA256"></a>
The Base64 encoded, 256-bit `SHA256` digest of the object. This checksum is only present if the checksum was uploaded with the object. When you use an API operation on an object that was uploaded using multipart uploads, this value may not be a direct checksum value of the full object. Instead, it's a calculation based on the checksum values of each individual part. For more information about how checksums are calculated with multipart uploads, see [ Checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html#large-object-checksums) in the *Amazon S3 User Guide*.

 ** [x-amz-checksum-sha512](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumSHA512"></a>
The Base64 encoded, 512-bit `SHA512` digest of the object. For more information, see [Checking object integrity in the Amazon S3 User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html).

 ** [x-amz-checksum-type](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumType"></a>
The checksum type, which determines how part-level checksums are combined to create an object-level checksum for multipart objects. You can use this header response to verify that the checksum type that is received is the same checksum type that was specified in `CreateMultipartUpload` request. For more information, see [Checking object integrity in the Amazon S3 User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html).  
Valid Values: `COMPOSITE | FULL_OBJECT` 

 ** [x-amz-checksum-xxhash128](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumXXHASH128"></a>
The Base64 encoded, 128-bit `XXHASH128` checksum of the object. For more information, see [Checking object integrity in the Amazon S3 User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html).

 ** [x-amz-checksum-xxhash3](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumXXHASH3"></a>
The Base64 encoded, 64-bit `XXHASH3` checksum of the object. For more information, see [Checking object integrity in the Amazon S3 User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html).

 ** [x-amz-checksum-xxhash64](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ChecksumXXHASH64"></a>
The Base64 encoded, 64-bit `XXHASH64` checksum of the object. For more information, see [Checking object integrity in the Amazon S3 User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html).

 ** [x-amz-delete-marker](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-DeleteMarker"></a>
Specifies whether the object retrieved was (true) or was not (false) a Delete Marker. If false, this response header does not appear in the response.  
This functionality is not supported for directory buckets.

 ** [x-amz-expiration](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-Expiration"></a>
If the object expiration is configured (see [`PutBucketLifecycleConfiguration`](https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutBucketLifecycleConfiguration.html)), the response includes this header. It includes the `expiry-date` and `rule-id` key-value pairs providing object expiration information. The value of the `rule-id` is URL-encoded.  
Object expiration information is not returned in directory buckets and this header returns the value "`NotImplemented`" in all responses for directory buckets.

 ** [x-amz-missing-meta](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-MissingMeta"></a>
This is set to the number of metadata entries not returned in `x-amz-meta` headers. This can happen if you create metadata using an API like SOAP that supports more flexible metadata than the REST API. For example, using SOAP, you can create metadata whose values are not legal HTTP headers.  
This functionality is not supported for directory buckets.

 ** [x-amz-mp-parts-count](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-PartsCount"></a>
The count of parts this object has. This value is only returned if you specify `partNumber` in your request and the object was uploaded as a multipart upload.

 ** [x-amz-object-lock-event-hold](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ObjectLockEventHold"></a>
The event hold status for this object. This header is only returned if the requester has the `s3:GetObjectRetention` permission.  
This functionality is not supported for directory buckets.
Valid Values: `ON | OFF` 

 ** [x-amz-object-lock-event-hold-duration-days](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ObjectLockEventHoldDurationDays"></a>
The event hold duration in days for this object. Only returned when the event hold is enabled.  
This functionality is not supported for directory buckets.

 ** [x-amz-object-lock-event-hold-duration-years](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ObjectLockEventHoldDurationYears"></a>
The event hold duration in years for this object. Only returned when the event hold is enabled.  
This functionality is not supported for directory buckets.

 ** [x-amz-object-lock-legal-hold](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ObjectLockLegalHoldStatus"></a>
Specifies whether a legal hold is in effect for this object. This header is only returned if the requester has the `s3:GetObjectLegalHold` permission. This header is not returned if the specified version of this object has never had a legal hold applied. For more information about S3 Object Lock, see [Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/dev/object-lock.html).  
This functionality is not supported for directory buckets.
Valid Values: `ON | OFF` 

 ** [x-amz-object-lock-mode](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ObjectLockMode"></a>
The Object Lock mode, if any, that's in effect for this object. This header is only returned if the requester has the `s3:GetObjectRetention` permission. For more information about S3 Object Lock, see [Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/dev/object-lock.html).   
This functionality is not supported for directory buckets.
Valid Values: `GOVERNANCE | COMPLIANCE` 

 ** [x-amz-object-lock-retain-until-date](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ObjectLockRetainUntilDate"></a>
The date and time when the Object Lock retention period expires. This header is only returned if the requester has the `s3:GetObjectRetention` permission.  
This functionality is not supported for directory buckets.

 ** [x-amz-replication-status](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ReplicationStatus"></a>
Amazon S3 can return this header if your request involves a bucket that is either a source or a destination in a replication rule.  
In replication, you have a source bucket on which you configure replication and destination bucket or buckets where Amazon S3 stores object replicas. When you request an object (`GetObject`) or object metadata (`HeadObject`) from these buckets, Amazon S3 will return the `x-amz-replication-status` header in the response as follows:  
+  **If requesting an object from the source bucket**, Amazon S3 will return the `x-amz-replication-status` header if the object in your request is eligible for replication.

   For example, suppose that in your replication configuration, you specify object prefix `TaxDocs` requesting Amazon S3 to replicate objects with key prefix `TaxDocs`. Any objects you upload with this key name prefix, for example `TaxDocs/document1.pdf`, are eligible for replication. For any object request with this key name prefix, Amazon S3 will return the `x-amz-replication-status` header with value PENDING, COMPLETED or FAILED indicating object replication status.
+  **If requesting an object from a destination bucket**, Amazon S3 will return the `x-amz-replication-status` header with value REPLICA if the object in your request is a replica that Amazon S3 created and there is no replica modification replication in progress.
+  **When replicating objects to multiple destination buckets**, the `x-amz-replication-status` header acts differently. The header of the source object will only return a value of COMPLETED when replication is successful to all destinations. The header will remain at value PENDING until replication has completed for all destinations. If one or more destinations fails replication the header will return FAILED. 
For more information, see [Replication](https://docs.aws.amazon.com/AmazonS3/latest/dev/NotificationHowTo.html).  
This functionality is not supported for directory buckets.
Valid Values: `COMPLETE | PENDING | FAILED | REPLICA | COMPLETED` 

 ** [x-amz-request-charged](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-RequestCharged"></a>
If present, indicates that the requester was successfully charged for the request. For more information, see [Using Requester Pays buckets for storage transfers and usage](https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html) in the *Amazon Simple Storage Service user guide*.  
This functionality is not supported for directory buckets.
Valid Values: `requester` 

 ** [x-amz-restore](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-Restore"></a>
If the object is an archived object (an object whose storage class is GLACIER), the response includes this header if either the archive restoration is in progress (see [RestoreObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_RestoreObject.html) or an archive copy is already restored.  
 If an archive copy is already restored, the header value indicates when Amazon S3 is scheduled to delete the object copy. For example:  
 `x-amz-restore: ongoing-request="false", expiry-date="Fri, 21 Dec 2012 00:00:00 GMT"`   
If the object restoration is in progress, the header returns the value `ongoing-request="true"`.  
For more information about archiving objects, see [Transitioning Objects: General Considerations](https://docs.aws.amazon.com/AmazonS3/latest/dev/object-lifecycle-mgmt.html#lifecycle-transition-general-considerations).  
This functionality is not supported for directory buckets. Directory buckets only support `EXPRESS_ONEZONE` (the S3 Express One Zone storage class) in Availability Zones and `ONEZONE_IA` (the S3 One Zone-Infrequent Access storage class) in Dedicated Local Zones.

 ** [x-amz-server-side-encryption](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-ServerSideEncryption"></a>
The server-side encryption algorithm used when you store this object in Amazon S3 or Amazon FSx.  
When accessing data stored in Amazon FSx file systems using S3 access points, the only valid server side encryption option is `aws:fsx`.
Valid Values: `AES256 | aws:fsx | aws:backup | aws:kms | aws:kms:dsse` 

 ** [x-amz-server-side-encryption-aws-kms-key-id](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-SSEKMSKeyId"></a>
If present, indicates the ID of the KMS key that was used for object encryption.

 ** [x-amz-server-side-encryption-bucket-key-enabled](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-BucketKeyEnabled"></a>
Indicates whether the object uses an S3 Bucket Key for server-side encryption with AWS Key Management Service (AWS KMS) keys (SSE-KMS).

 ** [x-amz-server-side-encryption-customer-algorithm](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-SSECustomerAlgorithm"></a>
If server-side encryption with a customer-provided encryption key was requested, the response will include this header to confirm the encryption algorithm that's used.  
This functionality is not supported for directory buckets.

 ** [x-amz-server-side-encryption-customer-key-MD5](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-SSECustomerKeyMD5"></a>
If server-side encryption with a customer-provided encryption key was requested, the response will include this header to provide the round-trip message integrity verification of the customer-provided encryption key.  
This functionality is not supported for directory buckets.

 ** [x-amz-storage-class](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-StorageClass"></a>
Provides storage class information of the object. Amazon S3 returns this header for all objects except for S3 Standard storage class objects.  
For more information, see [Storage Classes](https://docs.aws.amazon.com/AmazonS3/latest/dev/storage-class-intro.html).  
 **Directory buckets ** - Directory buckets only support `EXPRESS_ONEZONE` (the S3 Express One Zone storage class) in Availability Zones and `ONEZONE_IA` (the S3 One Zone-Infrequent Access storage class) in Dedicated Local Zones.
Valid Values: `STANDARD | REDUCED_REDUNDANCY | STANDARD_IA | ONEZONE_IA | INTELLIGENT_TIERING | GLACIER | DEEP_ARCHIVE | OUTPOSTS | GLACIER_IR | SNOW | EXPRESS_ONEZONE | FSX_OPENZFS | FSX_ONTAP | AWS_BACKUP_WARM | AWS_BACKUP_LOW_COST_WARM` 

 ** [x-amz-tagging-count](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-TagCount"></a>
The number of tags, if any, on the object, when you have the relevant permission to read object tags.  
You can use [GetObjectTagging](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObjectTagging.html) to retrieve the tag set associated with an object.  
This functionality is not supported for directory buckets.

 ** [x-amz-version-id](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-VersionId"></a>
Version ID of the object.  
This functionality is not supported for directory buckets.

 ** [x-amz-website-redirect-location](#API_HeadObject_ResponseSyntax) **   <a name="AmazonS3-HeadObject-response-header-WebsiteRedirectLocation"></a>
If the bucket is configured as a website, redirects requests for this object to another object in the same bucket or to an external URL. Amazon S3 stores the value of this header in the object metadata.  
This functionality is not supported for directory buckets.

## Errors
<a name="API_HeadObject_Errors"></a>

 ** NoSuchKey **   
The specified key does not exist.  
HTTP Status Code: 404

## Examples
<a name="API_HeadObject_Examples"></a>

### Sample Request for general purpose buckets
<a name="API_HeadObject_Example_1"></a>

The following request returns the metadata of an object.

```
            HEAD /my-image.jpg HTTP/1.1
            Host: bucket.s3.<Region>.amazonaws.com
            Date: Wed, 28 Oct 2009 22:32:00 GMT
            Authorization: AWS AKIAIOSFODNN7EXAMPLE:02236Q3V0RonhpaBX5sCYVf1bNRuU=
```

### Sample Response for general purpose buckets
<a name="API_HeadObject_Example_2"></a>

This example illustrates one usage of HeadObject.

```
            HTTP/1.1 200 OK
            x-amz-id-2: ef8yU9AS1ed4OpIszj7UDNEHGran
            x-amz-request-id: 318BC8BC143432E5
            x-amz-version-id: 3HL4kqtJlcpXroDTDmjVBH40Nrjfkd
            Date: Wed, 28 Oct 2009 22:32:00 GMT
            Last-Modified: Sun, 1 Jan 2006 12:00:00 GMT
            ETag: "fba9dede5f27731c9771645a39863328"
            Content-Length: 434234
            Content-Type: text/plain
            Connection: close
            Server: AmazonS3
```

### Sample Response for general purpose buckets: With an expiration tag
<a name="API_HeadObject_Example_3"></a>

If the object is scheduled to expire according to a lifecycle configuration set on the bucket, the response returns the `x-amz-expiration` tag with information about when Amazon S3 will delete the object. For more information, see [Transitioning Objects: General Considerations](https://docs.aws.amazon.com/AmazonS3/latest/dev/object-lifecycle-mgmt.html#lifecycle-transition-general-considerations). 

```
            HTTP/1.1 200 OK
            x-amz-id-2: azQRZtQJ2m1P8R+TIsG9h0VuC/DmiSJmjXUMq7snk+LKSJeurtmfzSlGhR46GzSJ
            x-amz-request-id: 0EFF61CCE3F24A26
            Date: Mon, 17 Dec 2012 02:26:39 GMT
            Last-Modified: Mon, 17 Dec 2012 02:14:10 GMT
            x-amz-expiration: expiry-date="Fri, 21 Dec 2012 00:00:00 GMT", rule-id="Rule for testfile.txt"
            ETag: "54b0c58c7ce9f2a8b551351102ee0938"
            Accept-Ranges: bytes
            Content-Type: text/plain
            Content-Length: 14
            Server: AmazonS3
```

### Sample Request for general purpose buckets: Getting metadata from a specified version of an object
<a name="API_HeadObject_Example_4"></a>

The following request returns the metadata of the specified version of an object.

```
            HEAD /my-image.jpg?versionId=3HL4kqCxf3vjVBH40Nrjfkd HTTP/1.1
            Host: bucket.s3.<Region>.amazonaws.com
            Date: Wed, 28 Oct 2009 22:32:00 GMT
            Authorization: AWS AKIAIOSFODNN7EXAMPLE:02236Q3V0WpaBX5sCYVf1bNRuU=
```

### Sample Response for general purpose buckets: To a versioned HEAD request
<a name="API_HeadObject_Example_5"></a>

This example illustrates one usage of HeadObject.

```
            HTTP/1.1 200 OK
            x-amz-id-2: eftixk72aD6Ap51TnqcoF8epIszj7UDNEHGran
            x-amz-request-id: 318BC8BC143432E5
            x-amz-version-id: 3HL4kqtJlcpXrof3vjVBH40Nrjfkd
            Date: Wed, 28 Oct 2009 22:32:00 GMT
            Last-Modified: Sun, 1 Jan 2006 12:00:00 GMT
            ETag: "fba9dede5f27731c9771645a39863328"
            Content-Length: 434234
            Content-Type: text/plain
            Connection: close
            Server: AmazonS3
```

### Sample Request for general purpose buckets: For an S3 Glacier object
<a name="API_HeadObject_Example_6"></a>

For an archived object, the `x-amz-restore` header provides the date when the restored copy expires, as shown in the following response. Even if the object is stored in S3 Glacier, all object metadata is still available.

```
            HEAD /my-image.jpg HTTP/1.1
            Host: bucket.s3.<Region>.amazonaws.com
            Date: 13 Nov 2012 00:28:38 GMT
            Authorization: AWS AKIAIOSFODNN7EXAMPLE:02236Q3V0RonhpaBX5sCYVf1bNRuU=
```

### Sample Response for general purpose buckets: S3 Glacier object
<a name="API_HeadObject_Example_7"></a>

If the object is already restored, the `x-amz-restore` header provides the date when the restored copy will expire, as shown in the following response.

```
            HTTP/1.1 200 OK
            x-amz-id-2: FSVaTMjrmBp3Izs1NnwBZeu7M19iI8UbxMbi0A8AirHANJBo+hEftBuiESACOMJp
            x-amz-request-id: E5CEFCB143EB505A
            Date: Tue, 13 Nov 2012 00:28:38 GMT
            Last-Modified: Mon, 15 Oct 2012 21:58:07 GMT
            x-amz-restore: ongoing-request="false", expiry-date="Wed, 07 Nov 2012 00:00:00 GMT"
            ETag: "1accb31fcf202eba0c0f41fa2f09b4d7"
            Accept-Ranges: bytes
            Content-Type: binary/octet-stream
            Content-Length: 300
            Server: AmazonS3
```

### Sample Response for general purpose buckets: In-progress restoration
<a name="API_HeadObject_Example_8"></a>

If the restoration is in progress, the `x-amz-restore` header returns a message accordingly.

```
            HTTP/1.1 200 OK
            x-amz-id-2: b+V2mDiMHTdy1myoUBpctvmJl95H9U/OSUm/jRtHxjh0+pCk5SvByL4xu2TDv4GM
            x-amz-request-id: E2E7B6AEE4E9BD2B
            Date: Tue, 13 Nov 2012 00:43:32 GMT
            Last-Modified: Sat, 20 Oct 2012 21:28:27 GMT
            x-amz-restore: ongoing-request="true"
            ETag: "1accb31fcf202eba0c0f41fa2f09b4d7"
            Accept-Ranges: bytes
            Content-Type: binary/octet-stream
            Content-Length: 300
            Server: AmazonS3
```

### Sample Response for general purpose buckets: Object archived using S3 Intelligent-Tiering
<a name="API_HeadObject_Example_9"></a>

If an object is stored using the S3 Intelligent-Tiering storage class and is currently in one of the archive tiers, then this action shows the current tier using the `x-amz-archive-status` header. 

```
            HTTP/1.1 200 OK
            x-amz-id-2: FSVaTMjrmBp3Izs1NnwBZeu7M19iI8UbxMbi0A8AirHANJBo+hEftBuiESACOMJp
            x-amz-request-id: E5CEFCB143EB505A
            Date: Fri, 13 Nov 2020 00:28:38 GMT
            Last-Modified: Mon, 15 Oct 2012 21:58:07 GMT
            ETag: "1accb31fcf202eba0c0f41fa2f09b4d7"
	    x-amz-storage-class: 'INTELLIGENT_TIERING'
            x-amz-archive-status: 'ARCHIVE_ACCESS'
            Accept-Ranges: bytes
            Content-Type: binary/octet-stream
            Content-Length: 300
            Server: AmazonS3
```

### Sample Response for general purpose buckets: Object archived using S3 Intelligent-Tiering with restore in progress
<a name="API_HeadObject_Example_10"></a>

If an object is stored using the S3 Intelligent-Tiering storage class and is currently in the process of being restored from one of the archive tiers, then this action shows the current tier using the `x-amz-archive-status` header and the current restore status using the `x-amz-restore` header. 

```
            HTTP/1.1 200 OK
            x-amz-id-2: FSVaTMjrmBp3Izs1NnwBZeu7M19iI8UbxMbi0A8AirHANJBo+hEftBuiESACOMJp
            x-amz-request-id: E5CEFCB143EB505A
            Date: Fri, 13 Nov 2020 00:28:38 GMT
            Last-Modified: Mon, 15 Oct 2012 21:58:07 GMT
            ETag: "1accb31fcf202eba0c0f41fa2f09b4d7"
	    x-amz-storage-class: 'INTELLIGENT_TIERING'
	    x-amz-archive-status: 'ARCHIVE_ACCESS'
	    x-amz-restore: 'ongoing-request="true"'
            x-amz-restore-request-date: 'Fri, 13 Nov 2020 00:20:00 GMT'
            Accept-Ranges: bytes
            Content-Type: binary/octet-stream
            Content-Length: 300
            Server: AmazonS3
```

## See Also
<a name="API_HeadObject_SeeAlso"></a>

For more information about using this API in one of the language-specific AWS SDKs, see the following:
+  [AWS Command Line Interface V2](https://docs.aws.amazon.com/goto/cli2/s3-2006-03-01/HeadObject) 
+  [AWS SDK for .NET V4](https://docs.aws.amazon.com/goto/DotNetSDKV4/s3-2006-03-01/HeadObject) 
+  [AWS SDK for C\+\+](https://docs.aws.amazon.com/goto/SdkForCpp/s3-2006-03-01/HeadObject) 
+  [AWS SDK for Go v2](https://docs.aws.amazon.com/goto/SdkForGoV2/s3-2006-03-01/HeadObject) 
+  [AWS SDK for Java V2](https://docs.aws.amazon.com/goto/SdkForJavaV2/s3-2006-03-01/HeadObject) 
+  [AWS SDK for JavaScript V3](https://docs.aws.amazon.com/goto/SdkForJavaScriptV3/s3-2006-03-01/HeadObject) 
+  [AWS SDK for Kotlin](https://docs.aws.amazon.com/goto/SdkForKotlin/s3-2006-03-01/HeadObject) 
+  [AWS SDK for PHP V3](https://docs.aws.amazon.com/goto/SdkForPHPV3/s3-2006-03-01/HeadObject) 
+  [AWS SDK for Python (Boto3)](https://docs.aws.amazon.com/goto/boto3/s3-2006-03-01/HeadObject) 
+  [AWS SDK for Ruby V3](https://docs.aws.amazon.com/goto/SdkForRubyV3/s3-2006-03-01/HeadObject) 