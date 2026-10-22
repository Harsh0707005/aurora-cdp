#!/usr/bin/env bash
# S3 raw landing bucket: versioned, encrypted, private, 90-day transition to IA. Feeds are uploaded here and
# pulled by the job runner (see deploy/aws/sync_feeds.sh).
. "$(dirname "$0")/common.sh"; require RAW_BUCKET
if aws_ s3api head-bucket --bucket "$RAW_BUCKET" 2>/dev/null; then log "bucket $RAW_BUCKET exists"; else
  log "creating bucket $RAW_BUCKET"
  if [ "$AWS_REGION" = "us-east-1" ]; then aws_ s3api create-bucket --bucket "$RAW_BUCKET"; else
    aws_ s3api create-bucket --bucket "$RAW_BUCKET" --create-bucket-configuration LocationConstraint="$AWS_REGION"; fi
fi
aws_ s3api put-public-access-block --bucket "$RAW_BUCKET" --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws_ s3api put-bucket-versioning --bucket "$RAW_BUCKET" --versioning-configuration Status=Enabled
aws_ s3api put-bucket-encryption --bucket "$RAW_BUCKET" --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws_ s3api put-bucket-lifecycle-configuration --bucket "$RAW_BUCKET" --lifecycle-configuration '{"Rules":[{"ID":"raw-to-ia","Status":"Enabled","Filter":{"Prefix":"raw/"},"Transitions":[{"Days":90,"StorageClass":"STANDARD_IA"}]}]}'
aws_ s3api put-bucket-tagging --bucket "$RAW_BUCKET" --tagging "TagSet=[{Key=Project,Value=$PROJECT},{Key=Env,Value=$ENV_NAME}]"
log "landing bucket ready: s3://$RAW_BUCKET/raw/<source>/<feed>/<yyyy-mm-dd>/file.csv"
