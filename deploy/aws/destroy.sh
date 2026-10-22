#!/usr/bin/env bash
# Tear down what the 0x scripts created. Interactive confirmation; RDS has deletion protection which is removed first.
. "$(dirname "$0")/common.sh"
read -r -p "Destroy $PROJECT/$ENV_NAME EC2 + RDS (bucket $RAW_BUCKET is KEPT)? type 'destroy': " ans; [ "$ans" = "destroy" ] || exit 1
IID=$(aws_ ec2 describe-instances --filters Name=tag:Name,Values="$PROJECT-$ENV_NAME" Name=instance-state-name,Values=running,stopped --query 'Reservations[0].Instances[0].InstanceId' 2>/dev/null || true)
[ -n "$IID" ] && [ "$IID" != "None" ] && { log "terminating $IID"; aws_ ec2 terminate-instances --instance-ids "$IID" >/dev/null; aws_ ec2 wait instance-terminated --instance-ids "$IID"; }
if aws_ rds describe-db-instances --db-instance-identifier "$RDS_IDENTIFIER" >/dev/null 2>&1; then
  aws_ rds modify-db-instance --db-instance-identifier "$RDS_IDENTIFIER" --no-deletion-protection --apply-immediately >/dev/null
  aws_ rds delete-db-instance --db-instance-identifier "$RDS_IDENTIFIER" --final-db-snapshot-identifier "$RDS_IDENTIFIER-final-$(date +%Y%m%d%H%M)" >/dev/null
  log "RDS deleting (final snapshot taken)"
fi
log "done; security groups, IAM role and the S3 bucket were left in place on purpose"
